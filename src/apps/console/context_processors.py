from apps.chat.models import ChatSession
from apps.core.models import ContactMessage
from apps.orders.models import Order


def console(request):
    if not request.path.startswith("/console/"):
        return {}
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_staff:
        return {}
    return {
        "console_badges": {
            "chat": ChatSession.objects.filter(status=ChatSession.Status.WAITING).count(),
            "orders": Order.objects.filter(
                status__in=[Order.Status.PENDING, Order.Status.REVISION, Order.Status.APPROVED]
            ).count(),
            "inbox": ContactMessage.objects.filter(is_read=False).count(),
        }
    }
