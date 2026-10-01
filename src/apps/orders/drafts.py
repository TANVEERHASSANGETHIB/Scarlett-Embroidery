"""Saving and restoring a guest's half-finished order.

A visitor can fill in the whole order form before creating an account. When
they submit, the answers and their uploaded artwork are parked in an
`OrderDraft` tied to their session, and they are asked to sign in. Coming back
(after logging in or verifying a new account) puts everything back on screen.
"""

import os
from datetime import timedelta

from django.core.files.base import File
from django.db import transaction
from django.utils import timezone

from .models import OrderDraft, OrderDraftFile, OrderFile
from .validators import validate_upload

SESSION_KEY = "order_draft_id"
DRAFT_TTL_DAYS = 14
MAX_DRAFT_FILES = 10

# Posted keys that must never be stored.
SKIP_FIELDS = {"csrfmiddlewaretoken", "next"}


def _session_draft_id(request):
    return request.session.get(SESSION_KEY)


def get_draft(request):
    """The draft belonging to this visitor's session, if any."""
    draft_id = _session_draft_id(request)
    if not draft_id:
        return None
    draft = OrderDraft.objects.filter(pk=draft_id).prefetch_related("files").first()
    if draft is None:
        request.session.pop(SESSION_KEY, None)
    return draft


def purge_expired():
    """Drop drafts nobody came back for (and their files)."""
    cutoff = timezone.now() - timedelta(days=DRAFT_TTL_DAYS)
    for draft in OrderDraft.objects.filter(updated_at__lt=cutoff):
        draft.delete()


@transaction.atomic
def save_draft(request, files=None):
    """Store the posted answers plus any uploaded artwork against this session."""
    if not request.session.session_key:
        request.session.save()

    draft = get_draft(request)
    if draft is None:
        draft = OrderDraft(session_key=request.session.session_key)

    data = {}
    for key in request.POST:
        if key in SKIP_FIELDS:
            continue
        values = request.POST.getlist(key)
        data[key] = values if len(values) > 1 else values[0]

    draft.data = data
    draft.session_key = request.session.session_key
    if request.user.is_authenticated:
        draft.user = request.user
    draft.save()
    request.session[SESSION_KEY] = draft.pk

    for uploaded in files or []:
        if draft.files.count() >= MAX_DRAFT_FILES:
            break
        OrderDraftFile.objects.create(
            draft=draft, file=uploaded, original_name=uploaded.name[:255], size=uploaded.size
        )
    return draft


def valid_saved_files(draft):
    """Saved files that still pass the upload rules (settings may have changed)."""
    if draft is None:
        return []
    keep = []
    for saved in draft.files.all():
        try:
            validate_upload(saved.file, [os.path.splitext(saved.original_name)[1].lower().lstrip(".")])
        except Exception:  # noqa: BLE001 - a rejected leftover simply isn't offered back
            continue
        keep.append(saved)
    return keep


def initial_from_draft(draft):
    """Turn stored answers back into form initial data."""
    if draft is None:
        return {}, {}
    data = draft.data or {}
    order_initial = {k: v for k, v in data.items() if not k.startswith("patch-")}
    patch_initial = {k[len("patch-") :]: v for k, v in data.items() if k.startswith("patch-")}
    return order_initial, patch_initial


def attach_draft_files(order, draft, user):
    """Copy a draft's artwork onto the real order, then drop the draft."""
    if draft is None:
        return []
    created = []
    for saved in draft.files.all():
        order_file = OrderFile(
            order=order,
            kind=OrderFile.Kind.ARTWORK,
            original_name=saved.original_name,
            size=saved.size,
            uploaded_by=user,
        )
        with saved.file.open("rb") as handle:
            order_file.file.save(os.path.basename(saved.file.name), File(handle), save=False)
        order_file.save()
        created.append(order_file)
    return created


def discard(request, draft):
    """Forget a draft once its order exists (or the visitor asked to start over)."""
    if draft is not None:
        draft.delete()
    request.session.pop(SESSION_KEY, None)
