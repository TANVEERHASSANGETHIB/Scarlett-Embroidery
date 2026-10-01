from django.core.management.base import BaseCommand

from apps.orders.drafts import DRAFT_TTL_DAYS, purge_expired
from apps.orders.models import OrderDraft


class Command(BaseCommand):
    help = f"Delete unfinished guest order drafts (and their files) older than {DRAFT_TTL_DAYS} days."

    def handle(self, *args, **options):
        before = OrderDraft.objects.count()
        purge_expired()
        removed = before - OrderDraft.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Removed {removed} expired draft(s); {before - removed} kept."))
