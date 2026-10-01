import re

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_dbg(client, staff):
    client.force_login(staff)
    resp = client.post(
        reverse("console:settings"),
        {
            "section": "site",
            "phone": "+1 (512) 555-0148",
            "email": "hello@sedigitizer.com",
            "orders_email": "orders@sedigitizer.com",
            "hours": "Live chat 24/7",
            "business_name": "Scarlett Embroidery",
            "address": "9 Bobbin Road, Austin, TX 78702",
            "map_embed_url": "",
            "show_map": "on",
            "announcement": "4-hour standard turnaround",
            "patch_production_note": "8-12 day production",
            "patch_min_quantity": "50",
        },
    )
    print("status:", resp.status_code)
    if resp.status_code == 200:
        body = resp.content.decode()
        for m in re.findall(r'class="errorlist">.*?</ul>', body, re.S)[:5]:
            print("ERR:", re.sub(r"<[^>]+>", " ", m).strip()[:160])
        for m in re.findall(r'class="form-errors"[^>]*>(.*?)</div>', body, re.S)[:3]:
            print("FORMERR:", re.sub(r"<[^>]+>", " ", m).strip()[:200])
        for m in re.findall(r'class="flash flash-\w+"[^>]*>(.*?)</div>', body, re.S)[:3]:
            print("FLASH:", re.sub(r"<[^>]+>", " ", m).strip()[:160])
