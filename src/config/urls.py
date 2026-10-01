from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Scarlett Embroidery — data admin"

urlpatterns = [
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

handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
