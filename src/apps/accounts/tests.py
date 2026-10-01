import re
from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import EmailVerification, User
from apps.accounts.services import issue_verification_code, verify_code

pytestmark = pytest.mark.django_db


def _code_from_outbox():
    body = mail.outbox[-1].body
    return re.search(r"\b(\d{6})\b", body).group(1)


def test_signup_sends_six_digit_code_and_requires_verification(client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(
            reverse("accounts:signup"),
            {
                "full_name": "Jane Whitfield",
                "company": "Whitfield",
                "email": "Jane@Shop.com",
                "password": "Str0ng-pass!",
            },
        )
    assert resp.status_code == 302
    assert resp.url == reverse("accounts:verify")

    user = User.objects.get(email="jane@shop.com")
    assert not user.email_verified
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["jane@shop.com"]
    code = _code_from_outbox()

    # Not logged in yet: dashboard redirects to login
    assert client.get(reverse("accounts:dashboard")).status_code == 302

    resp = client.post(reverse("accounts:verify"), {"code": code})
    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.email_verified
    assert client.get(reverse("accounts:dashboard")).status_code == 200


def test_unverified_login_redirects_to_verify(client, django_capture_on_commit_callbacks):
    User.objects.create_user(email="new@shop.com", password="Str0ng-pass!", full_name="New")
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(reverse("accounts:login"), {"email": "new@shop.com", "password": "Str0ng-pass!"})
    assert resp.status_code == 302
    assert resp.url.startswith(reverse("accounts:verify"))
    assert len(mail.outbox) == 1
    assert "_auth_user_id" not in client.session


def test_wrong_code_counts_attempts_and_locks(customer, settings):
    customer.email_verified = False
    customer.save()
    code = issue_verification_code(customer)
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(settings.VERIFICATION_CODE_MAX_ATTEMPTS):
        assert not verify_code(customer, wrong).ok
    assert EmailVerification.objects.get(user=customer).attempts == settings.VERIFICATION_CODE_MAX_ATTEMPTS
    # Locked: even the correct code is now refused
    assert not verify_code(customer, code).ok
    customer.refresh_from_db()
    assert not customer.email_verified


def test_expired_code_is_rejected(customer, django_capture_on_commit_callbacks):
    customer.email_verified = False
    customer.save()
    with django_capture_on_commit_callbacks(execute=True):
        code = issue_verification_code(customer)
    EmailVerification.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    assert not verify_code(customer, code).ok
    customer.refresh_from_db()
    assert not customer.email_verified


def test_new_code_invalidates_previous(customer):
    customer.email_verified = False
    customer.save()
    first = issue_verification_code(customer)
    second = issue_verification_code(customer)
    if first != second:
        assert not verify_code(customer, first).ok
    assert verify_code(customer, second).ok


def test_login_with_valid_credentials(client, customer):
    resp = client.post(reverse("accounts:login"), {"email": "JANE@shop.com", "password": "Str0ng-pass!"})
    assert resp.status_code == 302
    assert resp.url == reverse("accounts:dashboard")


def test_login_invalid_password(client, customer):
    resp = client.post(reverse("accounts:login"), {"email": "jane@shop.com", "password": "nope"})
    assert resp.status_code == 200
    assert b"Email or password is incorrect" in resp.content


def test_duplicate_signup_rejected(client, customer):
    resp = client.post(
        reverse("accounts:signup"),
        {
            "full_name": "Jane",
            "email": "jane@shop.com",
            "password": "Str0ng-pass!",
        },
    )
    assert resp.status_code == 200
    assert b"already exists" in resp.content
