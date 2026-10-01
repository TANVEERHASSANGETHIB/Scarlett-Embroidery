from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import SiteSettings
from apps.core.utils import send_templated_email

from .models import Order, OrderEvent, OrderFile
from .pricing import compute_estimate


def attach_files(order, files, kind, user):
    created = []
    for f in files:
        created.append(
            OrderFile.objects.create(
                order=order,
                kind=kind,
                file=f,
                original_name=f.name[:255],
                size=f.size,
                uploaded_by=user,
            )
        )
    return created


@transaction.atomic
def create_order(user, order_form, patch_form=None, draft=None, is_quote=False):
    order = order_form.save(commit=False)
    order.customer = user
    order.is_quote = is_quote
    patch_data = patch_form.cleaned_data if patch_form is not None else {}
    # A quote request never carries an estimate: the customer is told the price by us.
    order.estimate = (
        None
        if is_quote
        else compute_estimate(
            order.service,
            tier=order.tier,
            turnaround=order.turnaround,
            patch_category=patch_data.get("category"),
            quantity=patch_data.get("quantity"),
        )
    )
    order.save()

    if order.is_patch and patch_form is not None:
        patch = patch_form.save(commit=False)
        patch.order = order
        patch.save()

    attach_files(order, order_form.cleaned_data.get("artwork") or [], OrderFile.Kind.ARTWORK, user)
    if draft is not None:
        from .drafts import attach_draft_files  # local import keeps the modules independent

        attach_draft_files(order, draft, user)
    OrderEvent.objects.create(
        order=order,
        actor=user,
        kind=OrderEvent.Kind.CREATED,
        message=f"{order.get_service_display()} {'quote requested' if order.is_quote else 'order placed'}.",
    )

    transaction.on_commit(lambda: notify_order_created(order.pk))
    return order


def staff_recipients():
    """Who gets order alerts — configured in the admin console (Settings -> Notifications)."""
    return SiteSettings.load().notification_recipients


def order_url(order, staff=False):
    name = "console:order_detail" if staff else "orders:detail"
    return settings.SITE_URL + reverse(name, args=[order.number])


def notify_order_created(order_id):
    order = Order.objects.select_related("customer", "tier", "turnaround", "patch__category").get(pk=order_id)
    send_templated_email(
        f"Quote request {order.number} received" if order.is_quote else f"Order {order.number} received",
        "order_received",
        {"order": order, "url": order_url(order)},
        order.contact_email,
    )
    site = SiteSettings.load()
    if site.notify_on_new_order:
        send_templated_email(
            f"New {'quote request' if order.is_quote else 'order'} {order.number} · "
            f"{order.get_service_display()} · {order.design_name}",
            "order_staff",
            {"order": order, "url": order_url(order, staff=True)},
            site.notification_recipients,
            reply_to=order.contact_email,
        )


CUSTOMER_STATUS_EMAILS = {
    Order.Status.AWAITING_APPROVAL: ("Your proof for {number} is ready", "order_proof_ready"),
    Order.Status.DELIVERED: ("Order {number} delivered", "order_delivered"),
    Order.Status.CANCELLED: ("Order {number} cancelled", "order_status"),
    Order.Status.IN_PROGRESS: ("Order {number} is in production", "order_status"),
}


@transaction.atomic
def change_status(order, new_status, actor, message=""):
    if order.status == new_status:
        return False
    old_label = order.get_status_display()
    order.status = new_status
    fields = ["status", "updated_at"]
    if new_status == Order.Status.DELIVERED:
        order.delivered_at = timezone.now()
        fields.append("delivered_at")
    order.save(update_fields=fields)
    OrderEvent.objects.create(
        order=order,
        actor=actor,
        kind=OrderEvent.Kind.STATUS,
        message=f"{old_label} → {order.get_status_display()}" + (f"\n{message}" if message else ""),
    )
    if new_status in CUSTOMER_STATUS_EMAILS:
        subject, template = CUSTOMER_STATUS_EMAILS[new_status]
        transaction.on_commit(
            lambda: send_templated_email(
                subject.format(number=order.number),
                template,
                {"order": order, "message": message, "url": order_url(order)},
                order.contact_email,
            )
        )
    return True


@transaction.atomic
def customer_approve(order, user):
    order.status = Order.Status.APPROVED
    order.save(update_fields=["status", "updated_at"])
    OrderEvent.objects.create(
        order=order, actor=user, kind=OrderEvent.Kind.APPROVED, message="Customer approved the proof."
    )
    transaction.on_commit(
        lambda: send_templated_email(
            f"{order.number} approved by customer",
            "order_staff_update",
            {
                "order": order,
                "headline": "The customer approved the proof. Upload the final files and deliver.",
                "url": order_url(order, staff=True),
            },
            staff_recipients(),
        )
    )


@transaction.atomic
def customer_request_revision(order, user, message):
    order.status = Order.Status.REVISION
    order.save(update_fields=["status", "updated_at"])
    OrderEvent.objects.create(order=order, actor=user, kind=OrderEvent.Kind.REVISION, message=message)
    transaction.on_commit(
        lambda: send_templated_email(
            f"Revision requested on {order.number}",
            "order_staff_update",
            {
                "order": order,
                "headline": "The customer requested a revision:",
                "message": message,
                "url": order_url(order, staff=True),
            },
            staff_recipients(),
        )
    )
