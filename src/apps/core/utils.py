import logging
import threading
import time

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def get_client_ip(meta):
    """Best-effort client IP from a request.META dict or an ASGI header dict."""
    if settings.TRUST_PROXY_HEADERS:
        forwarded = meta.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real = meta.get("HTTP_X_REAL_IP", "")
        if real:
            return real.strip()
    return meta.get("REMOTE_ADDR") or None


def describe_device(user_agent):
    ua = (user_agent or "").lower()
    if "iphone" in ua:
        os_name = "iPhone"
    elif "ipad" in ua:
        os_name = "iPad"
    elif "android" in ua:
        os_name = "Android"
    elif "windows" in ua:
        os_name = "Windows"
    elif "mac os" in ua or "macintosh" in ua:
        os_name = "Mac"
    elif "linux" in ua:
        os_name = "Linux"
    else:
        os_name = "Unknown OS"

    if "edg/" in ua:
        browser = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "chrome" in ua or "crios" in ua:
        browser = "Chrome"
    elif "safari" in ua:
        browser = "Safari"
    else:
        browser = "Browser"
    return f"{os_name} · {browser}"


def _deliver(message, template, recipients):
    """Send with retries. SMTP hiccups (slow TLS handshakes) are common, so don't give up first try."""
    attempts = settings.EMAIL_MAX_ATTEMPTS
    for attempt in range(1, attempts + 1):
        try:
            message.send(fail_silently=False)
            if attempt > 1:
                logger.info("Sent '%s' email to %s on attempt %s", template, recipients, attempt)
            return True
        except Exception as exc:
            if attempt == attempts:
                logger.exception(
                    "Failed to send '%s' email to %s after %s attempts", template, recipients, attempts
                )
                return False
            logger.warning(
                "Retrying '%s' email to %s (attempt %s failed: %s)",
                template,
                recipients,
                attempt,
                exc,
            )
            time.sleep(settings.EMAIL_RETRY_DELAY_SECONDS * attempt)
    return False


def send_templated_email(subject, template, context, to, reply_to=None, background=None):
    """Render emails/<template>.txt (+ optional .html) and send.

    Delivery runs in a background thread by default so a slow mail server never
    delays the customer's page. Returns True when the message was handed off
    (or delivered, when sending synchronously).
    """
    recipients = [to] if isinstance(to, str) else list(to)
    recipients = [r for r in recipients if r]
    if not recipients:
        return False
    ctx = {"site_url": settings.SITE_URL, **context}
    text_body = render_to_string(f"emails/{template}.txt", ctx)
    message = EmailMultiAlternatives(
        subject=f"{subject}",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        reply_to=[reply_to] if reply_to else None,
    )
    try:
        html_body = render_to_string(f"emails/{template}.html", ctx)
        message.attach_alternative(html_body, "text/html")
    except TemplateDoesNotExist:
        pass  # plain-text only email

    if background is None:
        background = settings.EMAIL_SEND_IN_BACKGROUND
    if not background:
        return _deliver(message, template, recipients)

    thread = threading.Thread(
        target=_deliver, args=(message, template, recipients), name=f"email-{template}", daemon=True
    )
    thread.start()
    return True


def rate_limited(key, limit, window_seconds):
    """Increment a counter and report whether it exceeded `limit` inside the window."""
    cache_key = f"ratelimit:{key}"
    added = cache.add(cache_key, 1, window_seconds)
    if added:
        return False
    try:
        count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, window_seconds)
        return False
    return count > limit


def reset_rate_limit(key):
    cache.delete(f"ratelimit:{key}")
