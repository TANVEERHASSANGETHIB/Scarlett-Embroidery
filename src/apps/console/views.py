import os

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.models import User
from apps.blog.models import Post
from apps.chat import services as chat_services
from apps.chat.models import BlockedIP, ChatSession
from apps.core.models import (
    BeforeAfter,
    ContactMessage,
    PortfolioCategory,
    PortfolioItem,
    ServiceImage,
    SewOut,
    SiteImage,
    SiteSettings,
    Testimonial,
)
from apps.core.utils import get_client_ip, rate_limited, reset_rate_limit, send_templated_email
from apps.orders.models import Order, OrderEvent, OrderFile
from apps.orders.services import attach_files, change_status, order_url
from apps.orders.validators import validate_upload

from .decorators import staff_required
from .forms import (
    AdminPasswordChangeForm,
    BeforeAfterForm,
    ConsoleLoginForm,
    InviteAdminForm,
    NotificationSettingsForm,
    OrderFileUploadForm,
    OrderNoteForm,
    OrderUpdateForm,
    PatchCategoryFormSet,
    PortfolioCategoryForm,
    PortfolioItemForm,
    PortfolioUploadForm,
    PostForm,
    PricingTierFormSet,
    ServiceImageUploadForm,
    SewOutForm,
    SiteImageForm,
    SiteSettingsForm,
    SocialLinksForm,
    TestimonialForm,
    TurnaroundFormSet,
)


# ── Auth ─────────────────────────────────────────────────
@require_http_methods(["GET", "POST"])
def console_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("console:index")
    form = ConsoleLoginForm(request.POST or None)
    nxt = request.GET.get("next") or request.POST.get("next") or ""
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = ""
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        key = f"console-login:{get_client_ip(request.META)}"
        if rate_limited(key, limit=8, window_seconds=900):
            form.add_error(None, "Too many attempts. Wait 15 minutes and try again.")
        else:
            user = authenticate(request, email=email, password=form.cleaned_data["password"])
            if user is None or not user.is_staff:
                form.add_error(None, "Those credentials don't match an admin account.")
            else:
                reset_rate_limit(key)
                login(request, user)
                return redirect(nxt or "console:index")
    return render(request, "console/login.html", {"form": form, "next": nxt})


@require_POST
def console_logout(request):
    logout(request)
    return redirect("console:login")


@staff_required
def index(request):
    return redirect("console:chat")


@staff_required
@require_POST
def set_theme(request):
    """Remember this admin's console theme (dark or light)."""
    theme = request.POST.get("theme", "")
    if theme not in User.ConsoleTheme.values:
        return JsonResponse({"error": "unknown theme"}, status=400)

    request.user.console_theme = theme
    request.user.save(update_fields=["console_theme"])

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"theme": theme})

    nxt = request.POST.get("next") or ""
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = reverse("console:index")
    return redirect(nxt)


# ── Live chat ────────────────────────────────────────────
PER_PAGE_OPTIONS = [10, 20, 50]


@staff_required
def chat(request):
    status = request.GET.get("status", "")
    try:
        per_page = int(request.GET.get("per_page", 20))
    except ValueError:
        per_page = 20
    if per_page not in PER_PAGE_OPTIONS:
        per_page = 20

    sessions = ChatSession.objects.select_related("user", "assigned_to").annotate(msg_count=Count("messages"))
    sessions = sessions.filter(msg_count__gt=0).order_by("-last_message_at")
    if status in ChatSession.Status.values:
        sessions = sessions.filter(status=status)
    total = sessions.count()
    page = Paginator(sessions, per_page).get_page(request.GET.get("page"))

    active = None
    active_id = request.GET.get("s")
    if active_id:
        active = ChatSession.objects.select_related("user", "assigned_to").filter(pk=active_id).first()
    if active is None and page.object_list:
        active = page.object_list[0]

    thread = []
    visitor_rows = []
    if active:
        thread = list(active.messages.select_related("staff_user"))
        visitor_rows = [
            ("Name", active.display_name if active.name or active.user_id else "Guest (not provided)"),
            ("Email", active.contact_email or "—"),
            ("Account", active.user.company or "Registered customer" if active.user_id else "Guest"),
            ("IP address", active.ip_address or "—"),
            ("Country", active.country or "—"),
            ("Device", active.device or "—"),
            ("Current page", active.current_page or "—"),
            ("Referrer", active.referrer or "direct"),
            ("Session", f"{active.pages_viewed} page(s) · started {active.created_at:%d %b %H:%M}"),
            ("Status", active.get_status_display()),
            ("Assigned", active.assigned_to.get_full_name() if active.assigned_to_id else "Unassigned"),
        ]
    is_blocked = bool(
        active and active.ip_address and BlockedIP.objects.filter(ip_address=active.ip_address).exists()
    )

    return render(
        request,
        "console/chat.html",
        {
            "nav": "chat",
            "page": page,
            "total": total,
            "per_page": per_page,
            "per_page_options": PER_PAGE_OPTIONS,
            "status": status,
            "statuses": ChatSession.Status.choices,
            "active": active,
            "thread": thread,
            "visitor_rows": visitor_rows,
            "is_blocked": is_blocked,
            "waiting": ChatSession.objects.filter(status=ChatSession.Status.WAITING).count(),
        },
    )


@staff_required
@require_POST
def chat_action(request, pk):
    session = get_object_or_404(ChatSession, pk=pk)
    action = request.POST.get("action")
    if action == "assign":
        chat_services.assign_session(session, request.user)
        messages.success(request, "Conversation assigned to you.")
    elif action == "close":
        chat_services.set_session_status(session, ChatSession.Status.RESOLVED)
        messages.success(request, "Conversation closed.")
    elif action == "reopen":
        chat_services.set_session_status(session, ChatSession.Status.OPEN)
    elif action == "block" and session.ip_address:
        BlockedIP.objects.get_or_create(
            ip_address=session.ip_address,
            defaults={"created_by": request.user, "reason": f"Chat #{session.pk}"},
        )
        chat_services.set_session_status(session, ChatSession.Status.RESOLVED)
        messages.success(request, f"{session.ip_address} blocked from live chat.")
    elif action == "unblock" and session.ip_address:
        BlockedIP.objects.filter(ip_address=session.ip_address).delete()
        messages.success(request, f"{session.ip_address} unblocked.")
    elif action == "reply":
        body = request.POST.get("body", "")
        if body.strip():
            chat_services.post_staff_message(session, request.user, body)
    else:
        raise Http404
    return redirect(f"{reverse('console:chat')}?s={session.pk}")


@staff_required
def chat_transcript(request, pk):
    session = get_object_or_404(ChatSession, pk=pk)
    response = HttpResponse(chat_services.transcript_text(session), content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="chat-{session.pk}-transcript.txt"'
    return response


# ── Orders ───────────────────────────────────────────────
@staff_required
def orders(request):
    qs = Order.objects.select_related("customer", "assigned_to", "tier")
    status = request.GET.get("status", "open")
    service = request.GET.get("service", "")
    query = request.GET.get("q", "").strip()
    if status == "open":
        qs = qs.filter(status__in=Order.OPEN_STATUSES)
    elif status == "quotes":
        qs = qs.filter(is_quote=True)
    elif status in Order.Status.values:
        qs = qs.filter(status=status)
    if service:
        qs = qs.filter(service=service)
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(design_name__icontains=query)
            | Q(customer__email__icontains=query)
            | Q(customer__company__icontains=query)
            | Q(customer__full_name__icontains=query)
        )
    qs = qs.order_by("-created_at")
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "console/orders.html",
        {
            "nav": "orders",
            "page": page,
            "status": status,
            "service": service,
            "query": query,
            "statuses": Order.Status.choices,
            "services": Order._meta.get_field("service").choices,
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def order_detail(request, number):
    order = get_object_or_404(
        Order.objects.select_related("customer", "tier", "turnaround", "assigned_to", "patch__category"),
        number=number,
    )
    update_form = OrderUpdateForm(instance=order, prefix="upd")
    note_form = OrderNoteForm(prefix="note")
    upload_form = OrderFileUploadForm(prefix="up")

    if request.method == "POST":
        section = request.POST.get("section")
        if section == "update":
            old = {"status": order.status, "final_price": order.final_price, "payment": order.payment_status}
            update_form = OrderUpdateForm(request.POST, instance=Order.objects.get(pk=order.pk), prefix="upd")
            if update_form.is_valid():
                with transaction.atomic():
                    new_status = update_form.cleaned_data["status"]
                    updated = update_form.save(commit=False)
                    updated.status = old["status"]
                    updated.save()
                    if updated.final_price != old["final_price"] and updated.final_price is not None:
                        OrderEvent.objects.create(
                            order=updated,
                            actor=request.user,
                            kind=OrderEvent.Kind.PRICE,
                            message=f"Final price set to ${updated.final_price}",
                        )
                    if updated.payment_status != old["payment"]:
                        OrderEvent.objects.create(
                            order=updated,
                            actor=request.user,
                            kind=OrderEvent.Kind.PAYMENT,
                            message=f"Payment marked {updated.get_payment_status_display()}",
                        )
                    change_status(updated, new_status, request.user)
                messages.success(request, "Order updated.")
                return redirect("console:order_detail", number=order.number)
        elif section == "note":
            note_form = OrderNoteForm(request.POST, prefix="note")
            if note_form.is_valid():
                internal = note_form.cleaned_data["internal"]
                OrderEvent.objects.create(
                    order=order,
                    actor=request.user,
                    kind=OrderEvent.Kind.NOTE if internal else OrderEvent.Kind.MESSAGE,
                    message=note_form.cleaned_data["message"],
                    is_internal=internal,
                )
                if not internal:
                    send_templated_email(
                        f"Update on order {order.number}",
                        "order_status",
                        {
                            "order": order,
                            "message": note_form.cleaned_data["message"],
                            "url": order_url(order),
                        },
                        order.contact_email,
                    )
                messages.success(request, "Note added." if internal else "Message sent to the customer.")
                return redirect("console:order_detail", number=order.number)
        elif section == "upload":
            upload_form = OrderFileUploadForm(request.POST, request.FILES, prefix="up")
            if upload_form.is_valid():
                kind = upload_form.cleaned_data["kind"]
                files = attach_files(order, upload_form.cleaned_data["files"], kind, request.user)
                OrderEvent.objects.create(
                    order=order,
                    actor=request.user,
                    kind=OrderEvent.Kind.FILE,
                    message=f"Uploaded {len(files)} {'proof' if kind == OrderFile.Kind.PROOF else 'final'} file(s).",
                )
                if upload_form.cleaned_data["mark_status"]:
                    target = (
                        Order.Status.AWAITING_APPROVAL
                        if kind == OrderFile.Kind.PROOF
                        else Order.Status.DELIVERED
                    )
                    change_status(order, target, request.user)
                messages.success(request, "Files uploaded.")
                return redirect("console:order_detail", number=order.number)
        elif section == "delete_file":
            OrderFile.objects.filter(order=order, pk=request.POST.get("file_id")).exclude(
                kind=OrderFile.Kind.ARTWORK
            ).delete()
            messages.success(request, "File removed.")
            return redirect("console:order_detail", number=order.number)
        messages.error(request, "Please fix the errors below.")

    files = list(order.files.select_related("uploaded_by"))
    return render(
        request,
        "console/order_detail.html",
        {
            "nav": "orders",
            "order": order,
            "update_form": update_form,
            "note_form": note_form,
            "upload_form": upload_form,
            "events": order.events.select_related("actor"),
            "artwork": [f for f in files if f.kind == OrderFile.Kind.ARTWORK],
            "proofs": [f for f in files if f.kind == OrderFile.Kind.PROOF],
            "deliverables": [f for f in files if f.kind == OrderFile.Kind.DELIVERABLE],
        },
    )


# ── Customers ────────────────────────────────────────────
@staff_required
def customers(request):
    query = request.GET.get("q", "").strip()
    qs = User.objects.customers().annotate(
        order_count=Count("orders", distinct=True),
        spend=Sum(Coalesce("orders__final_price", "orders__estimate")),
    )
    if query:
        qs = qs.filter(
            Q(email__icontains=query) | Q(full_name__icontains=query) | Q(company__icontains=query)
        )
    page = Paginator(qs.order_by("-date_joined"), 25).get_page(request.GET.get("page"))
    return render(request, "console/customers.html", {"nav": "customers", "page": page, "query": query})


@staff_required
@require_http_methods(["GET", "POST"])
def customer_detail(request, pk):
    customer = get_object_or_404(User.objects.customers(), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "toggle_active":
            customer.is_active = not customer.is_active
            customer.save(update_fields=["is_active"])
            messages.success(request, "Account " + ("enabled." if customer.is_active else "disabled."))
        elif action == "verify":
            customer.email_verified = True
            customer.save(update_fields=["email_verified"])
            messages.success(request, "Email marked as verified.")
        return redirect("console:customer_detail", pk=customer.pk)
    return render(
        request,
        "console/customer_detail.html",
        {
            "nav": "customers",
            "customer": customer,
            "orders": customer.orders.select_related("tier").all(),
            "chats": customer.chat_sessions.all()[:10],
        },
    )


# ── Inbox (contact form) ─────────────────────────────────
@staff_required
@require_http_methods(["GET", "POST"])
def inbox(request):
    if request.method == "POST":
        msg = get_object_or_404(ContactMessage, pk=request.POST.get("id"))
        action = request.POST.get("action")
        if action == "delete":
            msg.delete()
            messages.success(request, "Message deleted.")
        elif action == "toggle_read":
            msg.is_read = not msg.is_read
            msg.save(update_fields=["is_read"])
        return redirect(request.POST.get("return_to") or "console:inbox")

    page = Paginator(ContactMessage.objects.all(), 20).get_page(request.GET.get("page"))
    active = None
    if request.GET.get("m"):
        active = ContactMessage.objects.filter(pk=request.GET["m"]).first()
        if active and not active.is_read:
            active.is_read = True
            active.save(update_fields=["is_read"])
    return render(request, "console/inbox.html", {"nav": "inbox", "page": page, "active": active})


# ── Blogs ────────────────────────────────────────────────
@staff_required
@require_http_methods(["GET", "POST"])
def blogs(request, pk=None):
    post = get_object_or_404(Post, pk=pk) if pk else None
    editor_open = post is not None or request.GET.get("new") == "1" or request.method == "POST"
    form = PostForm(request.POST or None, request.FILES or None, instance=post)

    if request.method == "POST":
        if request.POST.get("action") == "delete" and post:
            post.delete()
            messages.success(request, "Post deleted.")
            return redirect("console:blogs")
        if form.is_valid():
            saved = form.save(commit=False)
            if request.POST.get("action") == "draft":
                saved.status = Post.Status.DRAFT
            elif request.POST.get("action") == "publish":
                saved.status = Post.Status.PUBLISHED
            if saved.author_id is None:
                saved.author = request.user
            saved.save()
            messages.success(
                request, "Post published." if saved.status == Post.Status.PUBLISHED else "Draft saved."
            )
            return redirect("console:blog_edit", pk=saved.pk)
        messages.error(request, "Please fix the errors in the editor.")

    posts = Post.objects.select_related("category").order_by("-updated_at")
    return render(
        request,
        "console/blogs.html",
        {
            "nav": "blogs",
            "posts": posts,
            "form": form,
            "post": post,
            "editor_open": editor_open,
            "published_count": posts.filter(status=Post.Status.PUBLISHED).count(),
            "draft_count": posts.filter(status=Post.Status.DRAFT).count(),
        },
    )


@staff_required
@require_POST
def blog_image(request):
    """Upload one picture from the blog editor; returns its URL so it can be inserted into the article."""
    upload = request.FILES.get("image")
    if not upload:
        return JsonResponse({"error": "No file received."}, status=400)
    try:
        validate_upload(upload, django_settings.IMAGE_EXTENSIONS, django_settings.PORTFOLIO_IMAGE_MAX_BYTES)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    name = default_storage.save(f"blog/inline/{upload.name}", upload)
    return JsonResponse({"url": default_storage.url(name)})


# ── Portfolio ────────────────────────────────────────────
@staff_required
@require_http_methods(["GET", "POST"])
def portfolio(request, pk=None):
    """Upload sew-out photos, file them under a category, edit or delete them."""
    item = get_object_or_404(PortfolioItem, pk=pk) if pk else None
    upload_form = PortfolioUploadForm()
    item_form = PortfolioItemForm(instance=item)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "upload":
            upload_form = PortfolioUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                data = upload_form.cleaned_data
                images = data["images"]
                start = (PortfolioItem.objects.aggregate(top=Max("sort_order"))["top"] or 0) + 1
                for offset, image in enumerate(images):
                    fallback = os.path.splitext(image.name)[0].replace("-", " ").replace("_", " ").strip()
                    name = data["name"] or fallback.title()
                    if data["name"] and len(images) > 1:
                        name = f"{data['name']} {offset + 1}"
                    PortfolioItem.objects.create(
                        name=name[:120],
                        category=data["category"],
                        image=image,
                        meta=data["meta"],
                        show_on_home=data["show_on_home"],
                        is_published=data["is_published"],
                        sort_order=start + offset,
                    )
                messages.success(
                    request, f"Added {len(images)} photo{'s' if len(images) != 1 else ''} to the portfolio."
                )
                return redirect("console:portfolio")
            messages.error(request, "Please check the upload below.")

        elif action == "save" and item is not None:
            item_form = PortfolioItemForm(request.POST, request.FILES, instance=item)
            if item_form.is_valid():
                item_form.save()
                messages.success(request, "Portfolio piece updated.")
                return redirect("console:portfolio")
            messages.error(request, "Please fix the highlighted fields.")

        elif action == "category_add":
            cat_form = PortfolioCategoryForm(request.POST)
            if cat_form.is_valid():
                top = PortfolioCategory.objects.aggregate(top=Max("sort_order"))["top"] or 0
                cat = cat_form.save(commit=False)
                cat.sort_order = top + 1
                cat.save()
                messages.success(request, f"Category “{cat.name}” added.")
            else:
                messages.error(request, "That category name is empty or already used.")
            return redirect("console:portfolio")

        elif action == "category_rename":
            cat = get_object_or_404(PortfolioCategory, pk=request.POST.get("id"))
            cat_form = PortfolioCategoryForm(request.POST, instance=cat)
            if cat_form.is_valid():
                cat_form.save()
                messages.success(request, "Category renamed.")
            else:
                messages.error(request, "That category name is empty or already used.")
            return redirect("console:portfolio")

        elif action == "category_delete":
            cat = get_object_or_404(PortfolioCategory, pk=request.POST.get("id"))
            in_use = PortfolioItem.objects.filter(category=cat.slug).count()
            if in_use:
                messages.error(
                    request,
                    f"“{cat.name}” still has {in_use} photo{'s' if in_use != 1 else ''}. "
                    "Move or delete them first.",
                )
            else:
                cat.delete()
                messages.success(request, f"Category “{cat.name}” deleted.")
            return redirect("console:portfolio")

        elif action == "delete":
            target = get_object_or_404(PortfolioItem, pk=request.POST.get("id"))
            name = target.name
            target.image.delete(save=False)  # drop the file, not just the row
            target.delete()
            messages.success(request, f"“{name}” deleted.")
            return redirect("console:portfolio")

        elif action in {"toggle_published", "toggle_home"}:
            target = get_object_or_404(PortfolioItem, pk=request.POST.get("id"))
            field = "is_published" if action == "toggle_published" else "show_on_home"
            setattr(target, field, not getattr(target, field))
            target.save(update_fields=[field])
            return redirect(request.POST.get("return_to") or "console:portfolio")

    categories = list(PortfolioCategory.objects.all())
    category = request.GET.get("category", "")
    items = PortfolioItem.objects.all()
    if category in {c.slug for c in categories}:
        items = items.filter(category=category)
    else:
        category = ""
    items = list(items)
    by_slug = {c.slug: c for c in categories}
    for entry in items:
        entry.cached_category = by_slug.get(entry.category)

    tallies = dict(
        PortfolioItem.objects.values_list("category").annotate(n=Count("pk")).values_list("category", "n")
    )
    category_filters = [(c.slug, c.name, tallies.get(c.slug, 0)) for c in categories]
    category_rows = [(c, tallies.get(c.slug, 0)) for c in categories]
    return render(
        request,
        "console/portfolio.html",
        {
            "nav": "portfolio",
            "items": items,
            "item": item,
            "upload_form": upload_form,
            "item_form": item_form,
            "category_filters": category_filters,
            "category_rows": category_rows,
            "category_form": PortfolioCategoryForm(),
            "category": category,
            "total": PortfolioItem.objects.count(),
            "on_home": PortfolioItem.objects.filter(show_on_home=True, is_published=True).count(),
            "max_image_bytes": django_settings.PORTFOLIO_IMAGE_MAX_BYTES,
        },
    )


# ── Testimonials ─────────────────────────────────────────
@staff_required
@require_http_methods(["GET", "POST"])
def testimonials(request, pk=None):
    """Add, edit, hide or delete the quotes shown in the home page carousel."""
    item = get_object_or_404(Testimonial, pk=pk) if pk else None
    form = TestimonialForm(instance=item)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "delete":
            target = get_object_or_404(Testimonial, pk=request.POST.get("id"))
            name = target.name
            target.delete()
            messages.success(request, f"Quote from {name} deleted.")
            return redirect("console:testimonials")

        if action == "toggle_published":
            target = get_object_or_404(Testimonial, pk=request.POST.get("id"))
            target.is_published = not target.is_published
            target.save(update_fields=["is_published"])
            return redirect("console:testimonials")

        form = TestimonialForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            saved = form.save(commit=False)
            if item is None and not saved.sort_order:
                saved.sort_order = (Testimonial.objects.aggregate(top=Max("sort_order"))["top"] or 0) + 1
            saved.save()
            messages.success(request, "Quote updated." if item else "Quote added.")
            return redirect("console:testimonials")
        messages.error(request, "Please fix the highlighted fields.")

    return render(
        request,
        "console/testimonials.html",
        {
            "nav": "testimonials",
            "items": Testimonial.objects.all(),
            "item": item,
            "form": form,
            "published_count": Testimonial.objects.filter(is_published=True).count(),
        },
    )


# ── Client sew-outs ──────────────────────────────────────
@staff_required
@require_http_methods(["GET", "POST"])
def sewouts(request, pk=None):
    """Add, edit, hide or delete the client sew-out photos on the testimonials page."""
    item = get_object_or_404(SewOut, pk=pk) if pk else None
    form = SewOutForm(instance=item)

    if request.method == "POST":
        action = request.POST.get("action")

        if action in ("delete", "toggle_published"):
            target = get_object_or_404(SewOut, pk=request.POST.get("id"))
            if action == "delete":
                target.delete()
                messages.success(request, "Sew-out deleted.")
            else:
                target.is_published = not target.is_published
                target.save(update_fields=["is_published"])
            return redirect("console:sewouts")

        form = SewOutForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            saved = form.save(commit=False)
            if item is None and not saved.sort_order:
                saved.sort_order = (SewOut.objects.aggregate(top=Max("sort_order"))["top"] or 0) + 1
            saved.save()
            messages.success(request, "Sew-out updated." if item else "Sew-out added.")
            return redirect("console:sewouts")
        messages.error(request, "Please fix the highlighted fields.")

    return render(
        request,
        "console/sewouts.html",
        {
            "nav": "sewouts",
            "items": SewOut.objects.all(),
            "item": item,
            "form": form,
            "published_count": SewOut.objects.filter(is_published=True).count(),
        },
    )


# ── Media (service pictures, before/after, site photos) ──
@staff_required
@require_http_methods(["GET", "POST"])
def media(request):
    ba_form = BeforeAfterForm()
    upload_form = ServiceImageUploadForm()
    site_form = SiteImageForm()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "before_after":
            ba_form = BeforeAfterForm(request.POST, request.FILES)
            if ba_form.is_valid():
                pair = ba_form.save()
                messages.success(request, f"Before/after for {pair.get_service_display().lower()} saved.")
                return redirect("console:media")
            messages.error(request, "Please check the before/after form.")

        elif action == "before_after_delete":
            pair = get_object_or_404(BeforeAfter, pk=request.POST.get("id"))
            pair.before_image.delete(save=False)
            pair.after_image.delete(save=False)
            pair.delete()
            messages.success(request, "Before/after removed — the demo artwork is shown again.")
            return redirect("console:media")

        elif action == "service_images":
            upload_form = ServiceImageUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                data = upload_form.cleaned_data
                start = (ServiceImage.objects.aggregate(top=Max("sort_order"))["top"] or 0) + 1
                for offset, image in enumerate(data["images"]):
                    ServiceImage.objects.create(
                        service=data["service"],
                        image=image,
                        caption=data["caption"],
                        sort_order=start + offset,
                    )
                count = len(data["images"])
                messages.success(request, f"Added {count} picture{'s' if count != 1 else ''}.")
                return redirect("console:media")
            messages.error(request, "Please check the upload.")

        elif action == "service_image_delete":
            img = get_object_or_404(ServiceImage, pk=request.POST.get("id"))
            img.image.delete(save=False)
            img.delete()
            messages.success(request, "Picture deleted.")
            return redirect("console:media")

        elif action == "service_image_toggle":
            img = get_object_or_404(ServiceImage, pk=request.POST.get("id"))
            img.is_published = not img.is_published
            img.save(update_fields=["is_published"])
            return redirect("console:media")

        elif action == "site_image":
            site_form = SiteImageForm(request.POST, request.FILES)
            if site_form.is_valid():
                obj = site_form.save()
                messages.success(request, f"“{obj.get_slot_display()}” updated.")
                return redirect("console:media")
            messages.error(request, "Please check the photo.")

        elif action == "site_image_delete":
            obj = get_object_or_404(SiteImage, pk=request.POST.get("id"))
            obj.image.delete(save=False)
            obj.delete()
            messages.success(request, "Photo removed — the built-in artwork is shown again.")
            return redirect("console:media")

    existing = {obj.slot: obj for obj in SiteImage.objects.all()}
    return render(
        request,
        "console/media.html",
        {
            "nav": "media",
            "ba_form": ba_form,
            "upload_form": upload_form,
            "site_form": site_form,
            "pairs": BeforeAfter.objects.all(),
            "service_images": ServiceImage.objects.all(),
            "slots": [
                {"slot": v, "label": label, "size": SiteImage.SIZES.get(v, ""), "obj": existing.get(v)}
                for v, label in SiteImage.Slot.choices
            ],
            "max_image_bytes": django_settings.PORTFOLIO_IMAGE_MAX_BYTES,
        },
    )


# ── Settings ─────────────────────────────────────────────
SETTINGS_TABS = [
    ("pricing", "Pricing", "Flat price per design type"),
    ("turnaround", "Turnaround", "Delivery speeds and surcharges"),
    ("patches", "Patches", "Categories and price per piece"),
    ("notifications", "Notifications", "Where order alerts are sent"),
    ("site", "Site details", "Phone, email and public copy"),
    ("social", "Social links", "Icons shown in the site footer"),
    ("team", "Team", "Admins who can sign in here"),
    ("security", "Security", "Blocked chat visitors"),
    ("account", "My account", "Change your password"),
]
# Which tab to reopen after a form in that tab is submitted.
SECTION_TAB = {
    "tiers": "pricing",
    "turnarounds": "turnaround",
    "patches": "patches",
    "notifications": "notifications",
    "test_email": "notifications",
    "site": "site",
    "social": "social",
    "password": "account",
    "invite": "team",
    "toggle_admin": "team",
    "unblock_ip": "security",
}


def _email_status():
    """A human-readable summary of the outgoing mail configuration (never the password)."""
    backend = django_settings.EMAIL_BACKEND
    if "smtp" in backend:
        host = django_settings.EMAIL_HOST
        user = django_settings.EMAIL_HOST_USER
        return {
            "live": True,
            "label": f"{host}:{django_settings.EMAIL_PORT}",
            "account": user,
            "secure": "TLS"
            if django_settings.EMAIL_USE_TLS
            else ("SSL" if django_settings.EMAIL_USE_SSL else "none"),
            "password_set": bool(django_settings.EMAIL_HOST_PASSWORD),
            "from_email": django_settings.DEFAULT_FROM_EMAIL,
        }
    return {
        "live": False,
        "label": "Development inbox (Mailpit)" if "smtp" not in backend else backend,
        "account": "",
        "secure": "none",
        "password_set": False,
        "from_email": django_settings.DEFAULT_FROM_EMAIL,
    }


@staff_required
@require_http_methods(["GET", "POST"])
def settings_view(request):
    site = SiteSettings.load()
    section = request.POST.get("section") if request.method == "POST" else None
    tab = SECTION_TAB.get(section, "pricing")
    settings_url = reverse("console:settings")

    site_form = SiteSettingsForm(request.POST if section == "site" else None, instance=site)
    notify_form = NotificationSettingsForm(
        request.POST if section == "notifications" else None, instance=site
    )
    tiers = PricingTierFormSet(request.POST if section == "tiers" else None, prefix="tiers")
    turnarounds = TurnaroundFormSet(request.POST if section == "turnarounds" else None, prefix="ta")
    patches = PatchCategoryFormSet(request.POST if section == "patches" else None, prefix="pc")
    invite_form = InviteAdminForm(request.POST if section == "invite" else None)
    social_form = SocialLinksForm(request.POST if section == "social" else None, instance=site)
    password_form = AdminPasswordChangeForm(request.user, request.POST if section == "password" else None)

    if section == "password":
        if password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, password_form.user)  # stay signed in
            messages.success(request, "Password changed.")
            return redirect(f"{settings_url}?tab=account")
        messages.error(request, "Your password was not changed — see the notes below.")

    targets = {
        "site": site_form,
        "social": social_form,
        "notifications": notify_form,
        "tiers": tiers,
        "turnarounds": turnarounds,
        "patches": patches,
        "invite": invite_form,
    }
    if section in targets:
        target = targets[section]
        if target.is_valid():
            try:
                target.save()
            except Exception as exc:  # noqa: BLE001 - e.g. deleting a tier still referenced by orders
                messages.error(request, f"Could not save: {exc}")
                return redirect(f"{settings_url}?tab={tab}")
            messages.success(request, "Admin account created." if section == "invite" else "Settings saved.")
            return redirect(f"{settings_url}?tab={tab}")
        messages.error(request, "Please check the highlighted fields.")

    elif section == "test_email":
        recipients = site.notification_recipients
        sent = send_templated_email(
            "Test alert from your Scarlett Embroidery site",
            "test_alert",
            {
                "user": request.user,
                "recipients": recipients,
                "console_url": django_settings.SITE_URL + settings_url,
            },
            recipients,
            background=False,  # report the real result back to the admin
        )
        if sent:
            messages.success(
                request, f"Test email sent to {', '.join(recipients)}. Check the inbox (and spam)."
            )
        else:
            messages.error(
                request,
                "Could not send the test email. Check the mail settings in the server's .env file "
                "and look at the container logs for the exact error.",
            )
        return redirect(f"{settings_url}?tab=notifications")

    elif section == "toggle_admin":
        admin = get_object_or_404(User.objects.staff(), pk=request.POST.get("user_id"))
        if admin == request.user:
            messages.error(request, "You can't disable your own account.")
        else:
            admin.is_active = not admin.is_active
            admin.save(update_fields=["is_active"])
            messages.success(request, f"{admin.email} {'enabled' if admin.is_active else 'disabled'}.")
        return redirect(f"{settings_url}?tab=team")

    elif section == "unblock_ip":
        BlockedIP.objects.filter(pk=request.POST.get("block_id")).delete()
        messages.success(request, "IP unblocked.")
        return redirect(f"{settings_url}?tab=security")

    if request.method == "GET":
        requested = request.GET.get("tab")
        tab = requested if requested in dict((t[0], t) for t in SETTINGS_TABS) else "pricing"

    return render(
        request,
        "console/settings.html",
        {
            "nav": "settings",
            "tabs": SETTINGS_TABS,
            "active_tab": tab,
            "site_form": site_form,
            "notify_form": notify_form,
            "tiers": tiers,
            "turnarounds": turnarounds,
            "patches": patches,
            "invite_form": invite_form,
            "social_form": social_form,
            "password_form": password_form,
            "email_status": _email_status(),
            "recipients": site.notification_recipients,
            "admins": User.objects.staff().order_by("full_name"),
            "blocked": BlockedIP.objects.select_related("created_by").order_by("-created_at"),
        },
    )
