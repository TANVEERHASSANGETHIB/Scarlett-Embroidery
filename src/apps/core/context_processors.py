from django.utils.functional import SimpleLazyObject

from .models import SiteImage, SiteSettings


def site(request):
    return {"site": SiteSettings.load(), "site_photos": SimpleLazyObject(SiteImage.urls)}
