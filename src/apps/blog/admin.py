from django.contrib import admin

from .models import Category, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "status", "is_featured", "published_at"]
    list_filter = ["status", "category", "is_featured"]
    search_fields = ["title", "body"]
    prepopulated_fields = {"slug": ["title"]}
