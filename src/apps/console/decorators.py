from functools import wraps
from urllib.parse import quote

from django.shortcuts import redirect
from django.urls import reverse


def staff_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not user.is_staff or not user.is_active:
            return redirect(f"{reverse('console:login')}?next={quote(request.get_full_path())}")
        return view(request, *args, **kwargs)

    return wrapper
