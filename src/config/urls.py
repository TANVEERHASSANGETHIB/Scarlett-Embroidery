from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from django.views.static import serve

from apps.core.sitemaps import BlogSitemap, StaticSitemap

admin.site.site_header = "Scarlett Embroidery — data admin"

urlpatterns = [
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("sitemap.xml", sitemap, {"sitemaps": {"pages": StaticSitemap, "blog": BlogSitemap}}, name="sitemap"),
    path("django-admin/", admin.site.urls),
    path("console/", include("apps.console.urls")),
    path("account/", include("apps.accounts.urls")),
    path("order/", include("apps.orders.urls")),
    path("blog/", include("apps.blog.urls")),
    path("chat/", include("apps.chat.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif getattr(settings, "SERVE_MEDIA", False):  # no Caddy in front (e.g. Render)
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]

handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
