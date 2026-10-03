import math
import re

import markdown
import nh3
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import TimeStampedModel

ALLOWED_TAGS = {
    "p", "br", "strong", "em", "b", "i", "u", "s", "del", "mark", "sub", "sup", "small",
    "a", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "code", "pre",
    "hr", "img", "figure", "figcaption", "div", "span", "table", "thead", "tbody", "tfoot",
    "tr", "th", "td", "iframe", "video", "source",
}  # fmt: skip
ALLOWED_ATTRS = {
    "*": {"class", "id", "style", "title"},
    "a": {"href", "target", "name"},
    "img": {"src", "alt", "width", "height", "loading"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
    "iframe": {"src", "width", "height", "allowfullscreen", "frameborder", "allow"},
    "video": {"src", "controls", "poster", "width", "height"},
    "source": {"src", "type"},
}
ALLOWED_STYLES = {
    "color", "background-color", "text-align", "font-weight", "font-style", "text-decoration",
    "font-size", "width", "max-width", "height", "margin", "padding", "float", "border-radius",
    "line-height",
}  # fmt: skip
EMBED_HOSTS = {"www.youtube.com", "www.youtube-nocookie.com", "player.vimeo.com"}
HTML_HINT = re.compile(r"</?(p|h[1-6]|div|ul|ol|li|img|figure|blockquote|table|br|span|strong|em|a)\b", re.I)


def looks_like_html(text):
    return bool(HTML_HINT.search(text or ""))


def _safe_embed(tag, attr, value):
    """nh3 attribute filter: iframes may only point at YouTube/Vimeo."""
    if tag == "iframe" and attr == "src":
        from urllib.parse import urlparse

        parsed = urlparse(value)
        return value if parsed.scheme == "https" and parsed.netloc in EMBED_HOSTS else None
    return value


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=Post.Status.PUBLISHED, published_at__lte=timezone.now())


class Post(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts"
    )
    author_title = models.CharField(max_length=80, blank=True, default="Head Digitizer")
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField(
        help_text="Write visually, or switch to HTML to paste your own markup. Markdown from older posts still works."
    )
    cover = models.ImageField(upload_to="blog/", blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    published = PublishedManager()

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "post"
            slug, n = base, 2
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:detail", args=[self.slug])

    @property
    def body_html(self):
        raw = self.body or ""
        html = raw if looks_like_html(raw) else markdown.markdown(raw, extensions=["extra", "sane_lists"])
        return nh3.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRS,
            filter_style_properties=ALLOWED_STYLES,
            attribute_filter=_safe_embed,
            link_rel="noopener noreferrer",
            url_schemes={"http", "https", "mailto", "tel"},
        )

    @property
    def reading_minutes(self):
        words = len(nh3.clean(self.body or "", tags=set()).split())
        return max(1, math.ceil(words / 220))

    @property
    def summary(self):
        if self.excerpt:
            return self.excerpt
        text = nh3.clean(self.body_html, tags=set())
        return (text[:220] + "…") if len(text) > 220 else text
