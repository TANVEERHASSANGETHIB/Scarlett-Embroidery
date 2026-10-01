from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Category, Post


def post_list(request):
    posts = Post.published.select_related("category", "author")
    active = request.GET.get("category", "")
    if active:
        posts = posts.filter(category__slug=active)

    featured = None
    page_number = request.GET.get("page")
    if not active and not page_number:
        featured = posts.filter(is_featured=True).first() or posts.first()
        if featured:
            posts = posts.exclude(pk=featured.pk)

    page = Paginator(posts, 8).get_page(page_number)
    return render(
        request,
        "blog/list.html",
        {
            "featured": featured,
            "page": page,
            "categories": Category.objects.filter(posts__status="published").distinct(),
            "active": active,
        },
    )


def post_detail(request, slug):
    queryset = Post.objects if request.user.is_staff else Post.published
    post = get_object_or_404(queryset.select_related("category", "author"), slug=slug)
    related = Post.published.exclude(pk=post.pk)
    if post.category_id:
        related = related.filter(category_id=post.category_id)
    return render(request, "blog/detail.html", {"post": post, "related": related[:3]})
