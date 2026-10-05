from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.blog.models import Post


class StaticSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8
    protocol = "https"

    def items(self):
        names = [
            ("core:home", {}),
            ("core:services", {}),
            ("core:service", {"slug": "embroidery"}),
            ("core:service", {"slug": "vector"}),
            ("core:service", {"slug": "patches"}),
            ("core:portfolio", {}),
            ("core:testimonials", {}),
            ("core:about", {}),
            ("core:contact", {}),
            ("blog:list", {}),
        ]
        return [reverse(n, kwargs=kw) for n, kw in names]

    def location(self, item):
        return item


class BlogSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = "https"

    def items(self):
        return Post.published.all()

    def lastmod(self, obj):
        return obj.updated_at
