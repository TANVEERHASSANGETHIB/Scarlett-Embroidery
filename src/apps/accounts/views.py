from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.utils import get_client_ip, rate_limited, reset_rate_limit
from apps.orders.models import Order

from .forms import LoginForm, ProfileForm, SignupForm, VerifyCodeForm
from .models import User
from .services import issue_verification_code, seconds_until_resend, verify_code

PENDING_SESSION_KEY = "pending_verification_user_id"
AUTH_PERKS = [
    "Every delivered file, re-downloadable forever",
    "Live order status and sew-out proofs",
    "Saved fabric, size and format defaults",
    "One invoice history for your accountant",
]


def _safe_next(request):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return ""


def _customer_home(user):
    return reverse("console:index") if user.is_staff else reverse("accounts:dashboard")


@require_http_methods(["GET", "POST"])
def auth_view(request, mode="login"):
    """Combined log in / create account screen from the design."""
    if request.user.is_authenticated:
        return redirect(_customer_home(request.user))

    login_form = LoginForm(
        request, data=request.POST if mode == "login" and request.method == "POST" else None
    )
    signup_form = SignupForm(request.POST if mode == "signup" and request.method == "POST" else None)
    nxt = _safe_next(request)

    if request.method == "POST" and mode == "login":
        ip = get_client_ip(request.META)
        email = (request.POST.get("email") or "").strip().lower()
        throttle_key = f"login:{ip}:{email}"
        if rate_limited(throttle_key, limit=10, window_seconds=900):
            messages.error(request, "Too many sign-in attempts. Wait 15 minutes and try again.")
        elif login_form.is_valid():
            user = login_form.user
            reset_rate_limit(throttle_key)
            if not user.email_verified and not user.is_staff:
                request.session[PENDING_SESSION_KEY] = user.pk
                if seconds_until_resend(user) == 0:
                    issue_verification_code(user)
                messages.info(request, "Verify your email to finish signing in. We sent a 6-digit code.")
                return redirect(
                    f"{reverse('accounts:verify')}?next={nxt}" if nxt else reverse("accounts:verify")
                )
            login(request, user)
            return redirect(nxt or _customer_home(user))

    if request.method == "POST" and mode == "signup":
        ip = get_client_ip(request.META)
        if rate_limited(f"signup:{ip}", limit=10, window_seconds=3600):
            messages.error(request, "Too many sign-ups from your connection. Please try again later.")
        elif signup_form.is_valid():
            user = signup_form.save()
            request.session[PENDING_SESSION_KEY] = user.pk
            issue_verification_code(user)
            messages.success(request, f"Account created. We sent a 6-digit code to {user.email}.")
            return redirect(f"{reverse('accounts:verify')}?next={nxt}" if nxt else reverse("accounts:verify"))

    return render(
        request,
        "accounts/auth.html",
        {
            "mode": mode,
            "login_form": login_form,
            "signup_form": signup_form,
            "perks": AUTH_PERKS,
            "next": nxt,
        },
    )


def _pending_user(request):
    user_id = request.session.get(PENDING_SESSION_KEY)
    if not user_id:
        return None
    return User.objects.filter(pk=user_id, is_active=True).first()


@require_http_methods(["GET", "POST"])
def verify_email(request):
    user = _pending_user(request)
    if user is None:
        messages.info(request, "Log in to verify your email.")
        return redirect("accounts:login")
    if user.email_verified:
        request.session.pop(PENDING_SESSION_KEY, None)
        login(request, user)
        return redirect("accounts:dashboard")

    form = VerifyCodeForm(request.POST or None)
    nxt = _safe_next(request)
    if request.method == "POST" and form.is_valid():
        result = verify_code(user, form.cleaned_data["code"])
        if result.ok:
            request.session.pop(PENDING_SESSION_KEY, None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Email verified. Welcome to Scarlett Embroidery.")
            return redirect(nxt or "accounts:dashboard")
        form.add_error("code", result.error)

    return render(
        request,
        "accounts/verify.html",
        {
            "form": form,
            "pending_user": user,
            "resend_wait": seconds_until_resend(user),
            "next": nxt,
        },
    )


@require_POST
def resend_code(request):
    user = _pending_user(request)
    if user is None:
        return redirect("accounts:login")
    wait = seconds_until_resend(user)
    if wait:
        messages.error(request, f"Please wait {wait} seconds before requesting another code.")
    else:
        issue_verification_code(user)
        messages.success(request, f"A new code is on its way to {user.email}.")
    return redirect("accounts:verify")


@login_required
def dashboard(request):
    orders = Order.objects.filter(customer=request.user).select_related("tier")
    query = request.GET.get("q", "").strip()
    listing = orders
    if query:
        listing = listing.filter(Q(number__icontains=query) | Q(design_name__icontains=query))

    month_start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_spend = (
        orders.filter(created_at__gte=month_start)
        .exclude(status=Order.Status.CANCELLED)
        .aggregate(total=Sum(Coalesce("final_price", "estimate")))["total"]
        or 0
    )
    stats = [
        ("Open orders", orders.filter(status__in=Order.OPEN_STATUSES).count()),
        ("In review", orders.filter(status=Order.Status.AWAITING_APPROVAL).count()),
        ("Delivered", orders.filter(status=Order.Status.DELIVERED).count()),
        ("This month", f"${month_spend:,.2f}"),
    ]
    show_all = request.resolver_match.url_name == "orders"
    return render(
        request,
        "accounts/dashboard.html",
        {
            "stats": stats,
            "orders": listing if (show_all or query) else listing[:10],
            "query": query,
            "show_all": show_all,
            "nav": "orders" if show_all else "dash",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    form = ProfileForm(request.POST if request.POST.get("form") == "profile" else None, instance=request.user)
    password_form = PasswordChangeForm(
        request.user, request.POST if request.POST.get("form") == "password" else None
    )

    if request.method == "POST":
        if request.POST.get("form") == "profile" and form.is_valid():
            email_changed = "email" in form.changed_data
            user = form.save(commit=False)
            if email_changed and not user.is_staff:
                user.email_verified = False
            user.save()
            if email_changed and not user.is_staff:
                request.session[PENDING_SESSION_KEY] = user.pk
                issue_verification_code(user)
                logout(request)
                request.session[PENDING_SESSION_KEY] = user.pk
                messages.info(request, "Email changed. Verify the new address with the code we just sent.")
                return redirect("accounts:verify")
            messages.success(request, "Profile saved.")
            return redirect("accounts:profile")
        if request.POST.get("form") == "password" and password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed.")
            return redirect("accounts:profile")

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "password_form": password_form,
            "nav": "profile",
            "show_password": request.POST.get("form") == "password",
        },
    )


@require_http_methods(["GET", "POST"])
def logout_view(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "You're logged out. Your orders and files stay exactly where they are.")
        return redirect("core:home")
    if not request.user.is_authenticated:
        return redirect("core:home")
    return render(request, "accounts/logout.html", {"nav": "logout"})
