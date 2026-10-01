import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat


def validate_upload(uploaded, allowed_extensions, max_bytes=None):
    ext = os.path.splitext(uploaded.name)[1].lower().lstrip(".")
    if ext not in allowed_extensions:
        raise ValidationError(
            f"“{uploaded.name}” is not an accepted file type. Allowed: {', '.join(sorted(allowed_extensions)).upper()}."
        )
    limit = settings.ORDER_UPLOAD_MAX_BYTES if max_bytes is None else max_bytes
    if uploaded.size > limit:
        raise ValidationError(
            f"“{uploaded.name}” is {filesizeformat(uploaded.size)}; "
            f"the limit is {filesizeformat(limit)} per file."
        )
    return uploaded
