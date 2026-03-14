from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Tournament


User = get_user_model()


class TournamentStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin",
            password="secret123",
            email="admin@example.com",
        )

    def test_registration_open_property(self):
        now = timezone.now()
        tournament = Tournament.objects.create(
            name="Open Cup",
            description="desc",
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=2),
            registration_start=now - timedelta(hours=1),
            registration_end=now + timedelta(hours=1),
            is_draft=False,
            created_by=self.user,
        )

        self.assertTrue(tournament.is_registration_open)

    def test_running_property(self):
        now = timezone.now()
        tournament = Tournament.objects.create(
            name="Running Cup",
            description="desc",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            registration_start=now - timedelta(days=2),
            registration_end=now - timedelta(days=1),
            is_draft=False,
            created_by=self.user,
        )

        self.assertTrue(tournament.is_running)
