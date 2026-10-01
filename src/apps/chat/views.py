import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.core.utils import get_client_ip

from .consumers import VISITOR_COOKIE
from .models import ChatSession
from .services import is_blocked

COOKIE_MAX_AGE = 60 * 60 * 24 * 90


@require_GET
def visitor_session(request):
    """Issue the visitor chat cookie and return any existing conversation history."""
    if is_blocked(get_client_ip(request.META)):
        return JsonResponse({"blocked": True, "messages": []}, status=403)

    raw = request.COOKIES.get(VISITOR_COOKIE)
    try:
        token = uuid.UUID(raw) if raw else None
    except ValueError:
        token = None

    messages = []
    status = None
    if token:
        session = ChatSession.objects.filter(token=token).first()
        if session:
            status = session.status
            messages = [
                m.as_dict()
                for m in session.messages.select_related("staff_user").order_by("-created_at")[:50]
            ]
            messages.reverse()
    else:
        token = uuid.uuid4()

    user = request.user
    response = JsonResponse(
        {
            "blocked": False,
            "status": status,
            "messages": messages,
            "knownVisitor": bool(user.is_authenticated) or bool(messages),
        }
    )
    response.set_cookie(
        VISITOR_COOKIE,
        str(token),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure(),
    )
    return response
