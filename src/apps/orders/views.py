import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.models import SiteSettings
from apps.core.utils import get_client_ip, rate_limited

from . import drafts
from .forms import AdditionalArtworkForm, OrderForm, PatchDetailForm, RevisionRequestForm
from .models import (
    Order,
    OrderEvent,
    OrderFile,
    PatchCategory,
    PatchDetail,
    PricingTier,
    Service,
    TurnaroundOption,
)
from .pricing import pricing_payload
from .services import attach_files, create_order, customer_approve, customer_request_revision
from .validators import validate_upload

ORDER_META = [("Quote", "Under 30 min"), ("Pay", "After approval"), ("Revisions", "Free in scope")]


@require_http_methods(["GET", "POST"])
def place_order(request):
    """The order form. Guests may fill it in; we save their work and ask them to sign in."""
    user = request.user
    draft = drafts.get_draft(request)
    saved_files = drafts.valid_saved_files(draft)
    show_login_gate = False
    restored = False

    if user.is_authenticated:
        initial = {"contact_name": user.full_name, "contact_email": user.email}
        patch_initial = {"shipping_name": user.full_name, "shipping_phone": user.phone}
    else:
        initial, patch_initial = {}, {}

    requested_service = request.GET.get("service")
    if requested_service in Service.values:
        initial["service"] = requested_service
    requested_tier = request.GET.get("tier")
    if requested_tier and requested_tier.isdigit():
        tier = PricingTier.objects.filter(pk=requested_tier, is_active=True).first()
        if tier:  # e.g. arriving from a pricing card on the home page
            initial["tier"] = tier.pk
            initial["service"] = tier.service

    if request.method == "POST":
        is_patch = request.POST.get("service") == Service.PATCHES

        if not user.is_authenticated:
            # Park everything — answers and artwork — then ask them to sign in.
            form = OrderForm(request.POST, request.FILES, initial=initial)
            patch_form = (
                PatchDetailForm(request.POST, prefix="patch") if is_patch else PatchDetailForm(prefix="patch")
            )
            form.is_valid()  # surfaces any obvious mistakes while they are still here
            if is_patch:
                patch_form.is_valid()
            if rate_limited(f"draft:{get_client_ip(request.META)}", limit=20, window_seconds=3600):
                messages.error(request, "Too many attempts from your connection. Please try again later.")
            else:
                uploads = [f for f in request.FILES.getlist("artwork") if f]
                accepted = []
                for uploaded in uploads:
                    try:
                        validate_upload(uploaded, settings.ARTWORK_EXTENSIONS)
                    except ValidationError as exc:
                        messages.error(request, exc.messages[0])
                        continue
                    accepted.append(uploaded)
                draft = drafts.save_draft(request, accepted)
                drafts.purge_expired()
                saved_files = drafts.valid_saved_files(draft)
                show_login_gate = True
        else:
            form = OrderForm(request.POST, request.FILES, initial=initial, saved_file_count=len(saved_files))
            patch_form = (
                PatchDetailForm(request.POST, prefix="patch") if is_patch else PatchDetailForm(prefix="patch")
            )
            order_ok = form.is_valid()
            patch_ok = patch_form.is_valid() if is_patch else True
            if order_ok and patch_ok:
                order = create_order(user, form, patch_form if is_patch else None, draft=draft)
                drafts.discard(request, draft)
                messages.success(
                    request, f"Order {order.number} placed — we're on it. Your quote lands in your inbox."
                )
                return redirect("accounts:dashboard")
            messages.error(request, "Please fix the highlighted fields below.")
    else:
        draft_initial, draft_patch_initial = drafts.initial_from_draft(draft)
        if draft_initial or draft_patch_initial or saved_files:
            restored = True
            # The visitor's own answers win; their account details fill the gaps.
            initial = {**initial, **{k: v for k, v in draft_initial.items() if v not in ("", None)}}
            patch_initial = {
                **patch_initial,
                **{k: v for k, v in draft_patch_initial.items() if v not in ("", None)},
            }
        form = OrderForm(initial=initial, saved_file_count=len(saved_files))
        patch_form = PatchDetailForm(prefix="patch", initial=patch_initial)

    tiers = list(PricingTier.objects.filter(is_active=True))
    patch_categories = list(PatchCategory.objects.filter(is_active=True))

    def from_price(service):
        prices = [t.price for t in tiers if t.service == service]
        return min(prices) if prices else None

    digit_from, vector_from = from_price(Service.DIGITIZING), from_price(Service.VECTOR)
    patch_from = min((c.unit_price for c in patch_categories), default=None)
    service_cards = [
        (Service.DIGITIZING, "Digitizing", f"from ${digit_from:.0f} flat" if digit_from is not None else ""),
        (Service.VECTOR, "Vector Art", f"from ${vector_from:.0f} / logo" if vector_from is not None else ""),
        (Service.PATCHES, "Patches", f"from ${patch_from} ea" if patch_from is not None else ""),
    ]

    return render(
        request,
        "orders/place_order.html",
        {
            "form": form,
            "patch_form": patch_form,
            "order_meta": ORDER_META,
            "pricing": pricing_payload(),
            "service_cards": service_cards,
            "tiers": tiers,
            "turnarounds": TurnaroundOption.objects.filter(is_active=True),
            "patch_categories": patch_categories,
            "backings": PatchDetail.Backing.choices,
            "site_settings": SiteSettings.load(),
            "max_upload_bytes": settings.ORDER_UPLOAD_MAX_BYTES,
            "saved_files": saved_files,
            "show_login_gate": show_login_gate,
            "restored": restored,
            "login_next": reverse("orders:place"),
        },
    )


@require_POST
def remove_saved_file(request, pk):
    """Drop one file a visitor attached before signing in (their session only)."""
    draft = drafts.get_draft(request)
    if draft is None:
        raise Http404
    saved = draft.files.filter(pk=pk).first()
    if saved is None:
        raise Http404
    saved.file.delete(save=False)
    saved.delete()
    messages.success(request, "File removed.")
    return redirect("orders:place")


def _customer_order(request, number):
    return get_object_or_404(
        Order.objects.select_related("tier", "turnaround", "patch__category"),
        number=number,
        customer=request.user,
    )


@login_required
def order_detail(request, number):
    order = _customer_order(request, number)
    files = list(order.files.all())
    context = {
        "order": order,
        "artwork": [f for f in files if f.kind == OrderFile.Kind.ARTWORK],
        "proofs": [f for f in files if f.kind == OrderFile.Kind.PROOF],
        "deliverables": [f for f in files if f.kind == OrderFile.Kind.DELIVERABLE],
        "events": order.events.filter(is_internal=False).select_related("actor"),
        "revision_form": RevisionRequestForm(),
        "artwork_form": AdditionalArtworkForm(),
        "nav": "orders",
    }
    return render(request, "orders/order_detail.html", context)


@login_required
@require_POST
def order_action(request, number):
    order = _customer_order(request, number)
    action = request.POST.get("action")

    if action == "approve":
        if order.status != Order.Status.AWAITING_APPROVAL:
            messages.error(request, "This order has no proof waiting for approval.")
        else:
            customer_approve(order, request.user)
            messages.success(request, "Proof approved. Final files will be delivered shortly.")

    elif action == "revision":
        form = RevisionRequestForm(request.POST)
        if order.status not in (Order.Status.AWAITING_APPROVAL, Order.Status.DELIVERED):
            messages.error(request, "Revisions can be requested once a proof or delivery is ready.")
        elif form.is_valid():
            customer_request_revision(order, request.user, form.cleaned_data["message"])
            messages.success(request, "Revision requested. Your digitizer has been notified.")
        else:
            messages.error(request, "Describe what should change.")

    elif action == "artwork":
        form = AdditionalArtworkForm(request.POST, request.FILES)
        if not order.is_open:
            messages.error(request, "This order is closed. Place a new order for new artwork.")
        elif form.is_valid():
            files = attach_files(order, form.cleaned_data["files"], OrderFile.Kind.ARTWORK, request.user)
            note = form.cleaned_data.get("note", "")
            OrderEvent.objects.create(
                order=order,
                actor=request.user,
                kind=OrderEvent.Kind.FILE,
                message=f"Added {len(files)} artwork file(s)." + (f"\n{note}" if note else ""),
            )
            messages.success(request, "Files uploaded.")
        else:
            for errs in form.errors.values():
                for e in errs:
                    messages.error(request, e)
    else:
        raise Http404
    return redirect("orders:detail", number=order.number)


@login_required
def download_file(request, pk):
    order_file = get_object_or_404(OrderFile.objects.select_related("order"), pk=pk)
    if not (request.user.is_staff or order_file.order.customer_id == request.user.pk):
        raise Http404
    try:
        handle = order_file.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("File missing") from exc
    inline = request.GET.get("inline") == "1" and order_file.is_image
    response = FileResponse(
        handle, as_attachment=not inline, filename=os.path.basename(order_file.original_name)
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response
