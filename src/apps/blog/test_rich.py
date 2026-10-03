import io

import pytest
from django.urls import reverse
from PIL import Image

from apps.accounts.models import User
from apps.blog.models import Post


@pytest.mark.django_db
def test_html_body_is_kept_but_sanitised():
    post = Post(
        title="t",
        body='<h2 style="color:red;position:fixed">Hi</h2><p><strong>b</strong><script>x()</script></p>'
        '<img src="/media/a.jpg" alt="a"><iframe src="https://evil.example/x"></iframe>'
        '<iframe src="https://www.youtube.com/embed/abc"></iframe>',
    )
    html = post.body_html
    assert "<h2" in html and "color:red" in html and "position" not in html
    assert "<script" not in html and "evil.example" not in html
    assert "youtube.com/embed/abc" in html and "<img" in html


@pytest.mark.django_db
def test_markdown_posts_still_render():
    assert "<h2>Hello</h2>" in Post(title="m", body="## Hello").body_html


@pytest.mark.django_db
def test_blog_image_upload_needs_staff_and_returns_url(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(buf, "PNG")
    buf.seek(0)
    buf.name = "pic.png"
    url = reverse("console:blog_image")
    assert client.post(url, {"image": buf}).status_code in (302, 403)
    staff = User.objects.create_user(email="s@x.com", password="pw-12345-Zz", is_staff=True)
    client.force_login(staff)
    buf.seek(0)
    res = client.post(url, {"image": buf})
    assert res.status_code == 200 and "blog/inline/" in res.json()["url"]
    assert client.post(url, {}).status_code == 400


@pytest.mark.django_db
def test_editor_shows_markdown_post_as_html(client):
    staff = User.objects.create_user(email="s@x.com", password="pw-12345-Zz", is_staff=True)
    client.force_login(staff)
    post = Post.objects.create(title="Old", body="## Heading\n\n**bold**")
    res = client.get(reverse("console:blog_edit", args=[post.pk]))
    assert b"&lt;h2&gt;Heading&lt;/h2&gt;" in res.content
    assert b"rich-editor.js" in res.content
