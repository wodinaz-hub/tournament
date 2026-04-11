import shutil
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from PIL import Image

from tournament.models import (
    Announcement,
    Certificate,
    CertificateTemplate,
    Evaluation,
    Participant,
    RegistrationMember,
    Submission,
    Task,
    Team,
    Tournament,
    TournamentScheduleItem,
    TournamentRegistration,
)
from users.models import LoginThrottle


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@example.com",
)
class TournamentPlatformViewTests(TestCase):
    def setUp(self):
        media_base_dir = Path(__file__).resolve().parents[1] / "test_media_root"
        media_base_dir.mkdir(exist_ok=True)
        self.temp_media_dir = media_base_dir / f"tournament-media-{uuid4().hex}"
        self.temp_media_dir.mkdir(parents=True, exist_ok=True)
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media_dir)
        self.media_override.enable()
        self.captain = User.objects.create_user(
            username="captain",
            password="secret123",
            role="participant",
            is_approved=True,
            email="captain@example.com",
        )
        self.jury_user = User.objects.create_user(
            username="jury1",
            password="secret123",
            role="jury",
            is_approved=True,
            email="jury@example.com",
        )
        self.participant_user = User.objects.create_user(
            username="member1",
            password="secret123",
            role="participant",
            is_approved=True,
            email="member@example.com",
        )
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="secret123",
            email="admin@example.com",
        )
        self.organizer_user = User.objects.create_user(
            username="organizer",
            password="secret123",
            role="organizer",
            is_approved=True,
            email="organizer@example.com",
        )
        self.curator_user = User.objects.create_user(
            username="organizer2",
            password="secret123",
            role="organizer",
            is_approved=True,
            email="organizer2@example.com",
        )
        self.client.force_login(self.captain)

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.temp_media_dir, ignore_errors=True)
        super().tearDown()

    def make_test_image_upload(self, name="template.png"):
        buffer = BytesIO()
        Image.new("RGB", (1400, 1000), "white").save(buffer, format="PNG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

    def create_tournament(self, **overrides):
        now = timezone.now()
        defaults = {
            "name": "Spring Cup",
            "description": "Test tournament",
            "start_date": now + timedelta(days=1),
            "end_date": now + timedelta(days=2),
            "registration_start": now - timedelta(days=1),
            "registration_end": now + timedelta(hours=12),
            "is_draft": False,
            "created_by": self.admin_user,
        }
        defaults.update(overrides)
        return Tournament.objects.create(**defaults)

    def test_register_form_creates_participant_and_sends_verification_email(self):
        self.client.logout()

        response = self.client.post(
            reverse("register"),
            {
                "username": "newparticipant",
                "email": "newparticipant@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("register_success"))
        created_user = User.objects.get(username="newparticipant")
        self.assertEqual(created_user.role, "participant")
        self.assertTrue(created_user.is_approved)
        self.assertFalse(created_user.email_verified)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Підтвердження електронної пошти", mail.outbox[0].subject)
        self.assertIn("newparticipant@example.com", mail.outbox[0].to)
        self.assertIn(
            reverse(
                "verify_email",
                args=[
                    urlsafe_base64_encode(force_bytes(created_user.pk)),
                    default_token_generator.make_token(created_user),
                ],
            ),
            mail.outbox[0].body,
        )

    def test_login_is_blocked_until_email_is_verified(self):
        user = User.objects.create_user(
            username="pendingmail",
            password="StrongPass123!",
            role="participant",
            is_approved=True,
            email="pendingmail@example.com",
            email_verified=False,
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "StrongPass123!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Спочатку підтвердіть електронну пошту")
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_BLOCK_MINUTES=15)
    def test_login_is_temporarily_blocked_after_too_many_failed_attempts(self):
        self.client.logout()

        for _attempt in range(2):
            response = self.client.post(
                reverse("login"),
                {"username": self.captain.username, "password": "wrong-password"},
            )

        self.assertContains(response, "Залишилося спроб: 1")

        blocked_response = self.client.post(
            reverse("login"),
            {"username": self.captain.username, "password": "wrong-password"},
        )

        self.assertEqual(blocked_response.status_code, 200)
        self.assertContains(blocked_response, "Забагато невдалих спроб входу")
        self.assertContains(blocked_response, "Розблокування через:")
        throttle = LoginThrottle.objects.get(
            identifier=self.captain.username.lower(),
            ip_address="127.0.0.1",
        )
        self.assertIsNotNone(throttle.blocked_until)

        login_response = self.client.post(
            reverse("login"),
            {"username": self.captain.username, "password": "secret123"},
        )

        self.assertContains(login_response, "Забагато невдалих спроб входу")
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_BLOCK_MINUTES=15)
    def test_login_block_expires_and_allows_successful_sign_in(self):
        self.client.logout()
        throttle = LoginThrottle.objects.create(
            identifier=self.captain.username.lower(),
            ip_address="127.0.0.1",
            failed_attempts=0,
            blocked_until=timezone.now() - timedelta(minutes=1),
        )

        response = self.client.post(
            reverse("login"),
            {"username": self.captain.username, "password": "secret123"},
        )

        self.assertRedirects(response, reverse("redirect_by_role"), fetch_redirect_response=False)
        self.assertFalse(
            LoginThrottle.objects.filter(
                identifier=self.captain.username.lower(),
                ip_address="127.0.0.1",
            ).exists()
        )

    @override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_BLOCK_MINUTES=15)
    def test_successful_login_clears_previous_failed_attempts(self):
        self.client.logout()
        LoginThrottle.objects.create(
            identifier=self.captain.username.lower(),
            ip_address="127.0.0.1",
            failed_attempts=2,
            blocked_until=None,
        )

        response = self.client.post(
            reverse("login"),
            {"username": self.captain.username, "password": "secret123"},
        )

        self.assertRedirects(response, reverse("redirect_by_role"), fetch_redirect_response=False)
        self.assertFalse(
            LoginThrottle.objects.filter(
                identifier=self.captain.username.lower(),
                ip_address="127.0.0.1",
            ).exists()
        )

    def test_email_verification_marks_user_as_verified(self):
        user = User.objects.create_user(
            username="verifyme",
            password="StrongPass123!",
            role="participant",
            is_approved=True,
            email="verifyme@example.com",
            email_verified=False,
        )

        response = self.client.get(
            reverse(
                "verify_email",
                args=[
                    urlsafe_base64_encode(force_bytes(user.pk)),
                    default_token_generator.make_token(user),
                ],
            )
        )

        self.assertRedirects(response, reverse("login") + "?verified=1", fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertIsNotNone(user.email_verified_at)

    @override_settings(
        DEBUG=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    @patch("users.views.send_verification_email", side_effect=RuntimeError("smtp failed"))
    def test_register_does_not_create_user_if_email_sending_failed(self, _mock_send):
        self.client.logout()

        response = self.client.post(
            reverse("register"),
            {
                "username": "brokenmail",
                "email": "brokenmail@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Не вдалося надіслати лист підтвердження")
        self.assertFalse(User.objects.filter(username="brokenmail").exists())

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    )
    def test_register_requires_real_email_delivery_in_production(self):
        self.client.logout()

        response = self.client.post(
            reverse("register"),
            {
                "username": "prodmail",
                "email": "prodmail@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "На сервері не налаштовано реальну відправку email")
        self.assertFalse(User.objects.filter(username="prodmail").exists())

    @override_settings(
        DEBUG=False,
        EMAIL_DELIVERY_PROVIDER="brevo",
        BREVO_API_KEY="test-key",
        DEFAULT_FROM_EMAIL="verified@example.com",
        EMAIL_SENDER_NAME="Tournament Platform",
    )
    @patch("users.platform_services.urlopen")
    def test_register_uses_brevo_api_when_configured(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = None
        self.client.logout()

        response = self.client.post(
            reverse("register"),
            {
                "username": "brevouser",
                "email": "brevouser@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("register_success")))
        self.assertTrue(User.objects.filter(username="brevouser").exists())
        mock_urlopen.assert_called_once()

    def test_register_form_rejects_duplicate_email(self):
        self.client.logout()

        response = self.client.post(
            reverse("register"),
            {
                "username": "anotheruser",
                "email": self.participant_user.email,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Користувач з таким email уже існує.")

    @patch("users.views.send_verification_email")
    def test_register_does_not_send_email_for_duplicate_username(self, mock_send):
        self.client.logout()

        response = self.client.post(
            reverse("register"),
            {
                "username": self.participant_user.username,
                "email": "newaddress@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Користувач з таким логіном уже існує.")
        mock_send.assert_not_called()

    @patch("users.views.send_verification_email")
    def test_register_does_not_send_email_for_duplicate_email(self, mock_send):
        self.client.logout()

        response = self.client.post(
            reverse("register"),
            {
                "username": "totallynewuser",
                "email": self.participant_user.email,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Користувач з таким email уже існує.")
        mock_send.assert_not_called()

    def test_home_page_is_public_and_shows_tournaments(self):
        self.client.logout()
        tournament = self.create_tournament(name="Public Cup")

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public Cup")
        self.assertContains(response, reverse("public_tournament_detail", args=[tournament.id]))

    def test_home_page_filters_tournaments_by_status(self):
        now = timezone.now()
        registration_tournament = self.create_tournament(
            name="Registration Cup",
            registration_start=now - timedelta(days=1),
            registration_end=now + timedelta(days=1),
            start_date=now + timedelta(days=2),
            end_date=now + timedelta(days=3),
        )
        self.create_tournament(
            name="Finished Cup",
            registration_start=now - timedelta(days=4),
            registration_end=now - timedelta(days=3),
            start_date=now - timedelta(days=2),
            end_date=now - timedelta(hours=2),
        )

        response = self.client.get(reverse("home"), {"status": "registration"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, registration_tournament.name)
        filtered_names = [row["tournament"].name for row in response.context["filtered_tournament_rows"]]
        self.assertEqual(filtered_names, ["Registration Cup"])

    def test_home_page_renders_client_side_filter_attributes(self):
        self.create_tournament(name="Filter Cup")

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-home-filter="all"', html=False)
        self.assertContains(response, 'data-home-filter="registration"', html=False)
        self.assertContains(response, 'data-filter-bucket="', html=False)
        self.assertContains(response, "tournament-filter-empty", html=False)

    def test_home_page_shows_quick_team_block_for_team_member(self):
        now = timezone.now()
        tournament = self.create_tournament(
            name="Home Quick Cup",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=10),
            registration_end=now - timedelta(hours=2),
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Home quick task",
            description="desc",
            requirements="req",
            must_have="must",
            start_at=now - timedelta(minutes=30),
            deadline=now + timedelta(hours=2),
            is_draft=False,
            created_by=self.admin_user,
        )
        team = Team.objects.create(
            name="Home Quick Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        Participant.objects.create(
            team=team,
            full_name="Member One",
            email=self.participant_user.email,
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        self.client.force_login(self.participant_user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Швидкий блок команди")
        self.assertContains(response, "Home Quick Team")
        self.assertContains(response, tournament.name)
        self.assertContains(response, task.title)
        self.assertContains(response, reverse("team_detail", args=[team.id]))
        self.assertContains(response, reverse("public_tournament_detail", args=[tournament.id]))

    def test_admin_login_redirects_to_home_with_admin_actions(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("redirect_by_role"))

        self.assertRedirects(response, reverse("home"))
        home_response = self.client.get(reverse("home"))
        self.assertContains(home_response, reverse("admin_users"))
        self.assertContains(home_response, reverse("admin_active_tournaments"))
        self.assertContains(home_response, reverse("admin_registrations"))
        self.assertContains(home_response, reverse("admin_active_tournaments") + "?action=create-tournament")
        self.assertContains(home_response, reverse("admin_users") + "?action=create-user")

    def test_regular_admin_can_create_another_admin(self):
        admin_role_user = User.objects.create_user(
            username="roleadmin",
            password="secret123",
            role="admin",
            is_approved=True,
            email="roleadmin@example.com",
        )
        self.client.force_login(admin_role_user)

        response = self.client.post(
            reverse("create_user_by_admin"),
            {
                "username": "newadmin",
                "email": "newadmin@example.com",
                "role": "admin",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("admin_users"))
        created_user = User.objects.get(username="newadmin")
        self.assertEqual(created_user.role, "admin")

    def test_admin_actions_return_to_requested_dashboard_section(self):
        self.client.force_login(self.admin_user)
        target_user = User.objects.create_user(
            username="pending_mod",
            password="secret123",
            role="jury",
            is_approved=False,
            email="pending_mod@example.com",
        )

        response = self.client.post(
            reverse("approve_user", args=[target_user.id]),
            {"next": reverse("admin_dashboard") + "#users"},
        )

        self.assertRedirects(
            response,
            reverse("admin_dashboard") + "#users",
            fetch_redirect_response=False,
        )

    def test_public_tournament_detail_prompts_guest_to_register(self):
        self.client.logout()
        tournament = self.create_tournament(
            name="Guest Cup",
            registration_fields_config=[
                {"key": "school", "label": "Школа", "type": "text", "required": True},
            ],
        )

        response = self.client.get(reverse("public_tournament_detail", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Зареєструватися")
        self.assertContains(response, "Школа")

    def test_participant_can_create_team(self):
        self.client.force_login(self.participant_user)

        response = self.client.post(
            reverse("create_team"),
            {
                "name": "Participant Team",
                "captain_name": "Member Captain",
                "captain_email": "member@example.com",
                "school": "School 1",
                "preferred_contact_method": "telegram",
                "preferred_contact_value": "@team",
            },
        )

        self.assertRedirects(response, reverse("participant_dashboard"))
        self.assertTrue(Team.objects.filter(name="Participant Team", captain_user=self.participant_user).exists())

    def test_participant_cannot_create_team_without_contact_method(self):
        self.client.force_login(self.participant_user)

        response = self.client.post(
            reverse("create_team"),
            {
                "name": "Participant Team",
                "captain_name": "Member Captain",
                "captain_email": "member@example.com",
                "school": "School 1",
                "preferred_contact_method": "",
                "preferred_contact_value": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Оберіть зручний спосіб")
        self.assertContains(response, "Вкажіть контакт для зв")
        self.assertFalse(Team.objects.filter(name="Participant Team", captain_user=self.participant_user).exists())

    def test_participant_cannot_create_team_without_school(self):
        self.client.force_login(self.participant_user)

        response = self.client.post(
            reverse("create_team"),
            {
                "name": "Participant Team",
                "captain_name": "Member Captain",
                "captain_email": "member@example.com",
                "school": "",
                "preferred_contact_method": "telegram",
                "preferred_contact_value": "@team",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Вкажіть, будь ласка, свій навчальний заклад.")
        self.assertFalse(Team.objects.filter(name="Participant Team", captain_user=self.participant_user).exists())

    def test_participant_cannot_create_team_with_invalid_school(self):
        self.client.force_login(self.participant_user)

        response = self.client.post(
            reverse("create_team"),
            {
                "name": "Participant Team",
                "captain_name": "Member Captain",
                "captain_email": "member@example.com",
                "school": "test",
                "preferred_contact_method": "telegram",
                "preferred_contact_value": "@team",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Такого навчального закладу не знайдено, будь ласка, напишіть правильно.")
        self.assertFalse(Team.objects.filter(name="Participant Team", captain_user=self.participant_user).exists())

    def test_participant_can_submit_registration_from_public_tournament_page(self):
        tournament = self.create_tournament()
        self.client.force_login(self.participant_user)

        response = self.client.post(
            reverse("public_tournament_detail", args=[tournament.id]),
            {
                "team_name": "Open Team",
                "captain_name": "Member Captain",
                "captain_email": self.participant_user.email,
                "school": "Ліцей №1",
                "preferred_contact_method": "discord",
                "preferred_contact_value": "open-team-discord",
            },
        )

        self.assertRedirects(response, reverse("participant_dashboard"))
        team = Team.objects.get(captain_user=self.participant_user, name="Open Team")
        registration = TournamentRegistration.objects.get(tournament=tournament, team=team)
        self.assertEqual(registration.status, TournamentRegistration.Status.PENDING)
        self.assertEqual(team.school, "Ліцей №1")
        self.assertEqual(team.preferred_contact_method, "discord")
        self.assertEqual(team.preferred_contact_value, "open-team-discord")
        self.assertEqual(team.discord, "open-team-discord")
        self.assertFalse(team.telegram)
        self.assertFalse(team.viber)
        self.participant_user.refresh_from_db()
        self.assertEqual(self.participant_user.role, "participant")

    def test_public_tournament_registration_requires_contact_method(self):
        tournament = self.create_tournament()
        self.client.force_login(self.participant_user)

        response = self.client.post(
            reverse("public_tournament_detail", args=[tournament.id]),
            {
                "team_name": "Open Team",
                "captain_name": "Member Captain",
                "captain_email": self.participant_user.email,
                "school": "Ліцей №1",
                "preferred_contact_method": "",
                "preferred_contact_value": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Оберіть зручний спосіб")
        self.assertContains(response, "Вкажіть контакт для зв")
        self.assertFalse(Team.objects.filter(captain_user=self.participant_user, name="Open Team").exists())

    def test_public_tournament_registration_requires_valid_school(self):
        tournament = self.create_tournament()
        self.client.force_login(self.participant_user)

        response = self.client.post(
            reverse("public_tournament_detail", args=[tournament.id]),
            {
                "team_name": "Open Team",
                "captain_name": "Member Captain",
                "captain_email": self.participant_user.email,
                "school": "test",
                "preferred_contact_method": "discord",
                "preferred_contact_value": "open-team-discord",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Такого навчального закладу не знайдено, будь ласка, напишіть правильно.")
        self.assertFalse(Team.objects.filter(captain_user=self.participant_user, name="Open Team").exists())

    def test_create_tournament_requires_at_least_one_allowed_contact_method(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_tournament"),
            {
                "name": "No Contacts Cup",
                "description": "Tournament without contacts",
                "registration_form_description": "",
                "allowed_contact_methods": [],
                "start_date": (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
                "end_date": (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
                "registration_start": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "registration_end": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
                "min_team_members": 2,
                "max_team_members": 4,
                "max_teams": 20,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Залиште принаймні один спосіб зв")
        self.assertFalse(Tournament.objects.filter(name="No Contacts Cup").exists())

    def test_public_tournament_registration_shows_only_allowed_contact_methods(self):
        tournament = self.create_tournament(allowed_contact_methods=["discord"])
        self.client.force_login(self.participant_user)

        response = self.client.get(reverse("public_tournament_detail", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Діскорд")
        self.assertNotContains(response, "Телеграм")
        self.assertNotContains(response, "Вайбер")

    def test_create_tournament_requires_schedule_for_published_tournament(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_tournament"),
            {
                "name": "No Schedule Cup",
                "description": "Tournament without schedule",
                "registration_form_description": "",
                "registration_fields_definition": "",
                "schedule_definition": "",
                "allowed_contact_methods": ["telegram"],
                "start_date": (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
                "end_date": (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
                "registration_start": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "registration_end": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
                "min_team_members": 2,
                "max_team_members": 4,
                "max_teams": 20,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "хоча б одну подію розкладу")
        self.assertFalse(Tournament.objects.filter(name="No Schedule Cup").exists())

    def test_create_tournament_saves_schedule_items(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_tournament"),
            {
                "name": "Schedule Cup",
                "description": "Tournament with schedule",
                "registration_form_description": "",
                "registration_fields_definition": "",
                "schedule_definition": "2030-05-01T10:00|Старт реєстрації|Початок прийому заявок\n2030-05-03T18:00|Онлайн-консультація|Питання та відповіді",
                "allowed_contact_methods": ["telegram"],
                "start_date": (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
                "end_date": (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
                "registration_start": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "registration_end": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
                "min_team_members": 2,
                "max_team_members": 4,
                "max_teams": 20,
            },
        )

        self.assertRedirects(response, reverse("admin_active_tournaments"))
        tournament = Tournament.objects.get(name="Schedule Cup")
        self.assertEqual(tournament.schedule_items.count(), 2)
        self.assertTrue(TournamentScheduleItem.objects.filter(tournament=tournament, title="Старт реєстрації").exists())

    def test_public_and_jury_pages_show_tournament_schedule(self):
        tournament = self.create_tournament()
        TournamentScheduleItem.objects.create(
            tournament=tournament,
            title="Перша консультація",
            starts_at=timezone.now() + timedelta(hours=2),
            description="Розбір вимог і дедлайнів",
            position=0,
        )
        tournament.jury_users.add(self.jury_user)

        public_response = self.client.get(reverse("public_tournament_detail", args=[tournament.id]))
        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, "Розклад турніру")
        self.assertContains(public_response, "Перша консультація")

        self.client.force_login(self.jury_user)
        jury_response = self.client.get(reverse("jury_tournament_detail", args=[tournament.id]))
        self.assertEqual(jury_response.status_code, 200)
        self.assertContains(jury_response, "Розклад турніру")
        self.assertContains(jury_response, "Перша консультація")


    def test_admin_can_create_user_from_users_tab(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_user_by_admin"),
            {
                "username": "manual_jury",
                "email": "manual_jury@example.com",
                "role": "jury",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("admin_users"))
        created_user = User.objects.get(username="manual_jury")
        self.assertEqual(created_user.role, "jury")
        self.assertFalse(created_user.is_approved)

    def test_admin_cannot_create_admin_user(self):
        admin_user = User.objects.create_user(
            username="plainadmin",
            password="secret123",
            role="admin",
            is_approved=True,
            email="plainadmin@example.com",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("create_user_by_admin"),
            {
                "username": "blocked_admin",
                "email": "blocked_admin@example.com",
                "role": "admin",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="blocked_admin").exists())

    def test_organizer_can_open_own_dashboard(self):
        self.client.force_login(self.organizer_user)

        response = self.client.get(reverse("organizer_dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_admin_can_assign_organizer_role(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("update_user_role", args=[self.participant_user.id]),
            {
                "role": "organizer",
            },
        )

        self.assertRedirects(response, reverse("admin_users"))
        self.participant_user.refresh_from_db()
        self.assertEqual(self.participant_user.role, "organizer")

    def test_organizer_can_open_tournament_detail_for_owned_tournament(self):
        tournament = self.create_tournament()
        tournament.created_by = self.curator_user
        tournament.save(update_fields=["created_by"])
        self.client.force_login(self.curator_user)

        response = self.client.get(reverse("edit_tournament", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 200)

    def test_organizer_can_approve_registration_for_owned_tournament(self):
        tournament = self.create_tournament()
        tournament.created_by = self.curator_user
        tournament.save(update_fields=["created_by"])
        team = Team.objects.create(
            name="Pending Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        registration = TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.PENDING,
        )
        self.client.force_login(self.curator_user)

        response = self.client.post(reverse("approve_registration", args=[registration.id]))

        self.assertRedirects(response, reverse("organizer_dashboard"))
        registration.refresh_from_db()
        self.assertEqual(registration.status, TournamentRegistration.Status.APPROVED)

    def test_admin_can_create_announcement(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("admin_announcements"),
            {
                "title": "System update",
                "message": "Platform maintenance tonight.",
                "tournament": "",
            },
        )

        self.assertRedirects(response, reverse("admin_announcements"))
        self.assertTrue(Announcement.objects.filter(title="System update").exists())

    def test_home_shows_unread_message_and_certificate_badges(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(days=2),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(days=3),
        )
        team = Team.objects.create(
            name="Badge Team",
            captain_user=self.participant_user,
            captain_name="Member Captain",
            captain_email=self.participant_user.email,
        )
        Announcement.objects.create(
            title="Unread announcement",
            message="New message",
            created_by=self.admin_user,
        )
        Certificate.objects.create(
            tournament=tournament,
            team=team,
            certificate_type=Certificate.CertificateType.PARTICIPANT,
            recipient_user=self.participant_user,
            recipient_name="Member Captain",
            recipient_email=self.participant_user.email,
            issued_by=self.admin_user,
        )
        self.client.force_login(self.participant_user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse("messages"))
        self.assertContains(response, reverse("certificates"))
        self.assertContains(response, "notify-dot")

    def test_opening_messages_and_certificates_marks_items_as_seen(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(days=2),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(days=3),
        )
        team = Team.objects.create(
            name="Seen Team",
            captain_user=self.participant_user,
            captain_name="Member Captain",
            captain_email=self.participant_user.email,
        )
        Announcement.objects.create(
            title="Seen announcement",
            message="Read me",
            created_by=self.admin_user,
        )
        Certificate.objects.create(
            tournament=tournament,
            team=team,
            certificate_type=Certificate.CertificateType.PARTICIPANT,
            recipient_user=self.participant_user,
            recipient_name="Member Captain",
            recipient_email=self.participant_user.email,
            issued_by=self.admin_user,
        )
        self.client.force_login(self.participant_user)

        self.client.get(reverse("messages"))
        self.client.get(reverse("certificates"))

        self.participant_user.refresh_from_db()
        self.assertIsNotNone(self.participant_user.announcements_seen_at)
        self.assertIsNotNone(self.participant_user.certificates_seen_at)

    def test_messages_page_includes_system_tournament_events(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=20),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        team = Team.objects.create(
            name="Messages Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        self.client.force_login(self.captain)

        response = self.client.get(reverse("messages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Старт турніру {tournament.name}")
        self.assertContains(response, "24 години до дедлайну")

    def test_public_tournament_detail_hides_leaderboard_until_finish(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=2),
            end_date=timezone.now() + timedelta(hours=5),
            registration_end=timezone.now() - timedelta(hours=3),
        )
        self.client.logout()

        response = self.client.get(reverse("public_tournament_detail", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Лідерборд з'явиться тільки після завершення турніру")
        self.assertNotContains(response, "Відкрити повний лідерборд")

    def test_messages_page_shows_registration_open_event(self):
        tournament = self.create_tournament(
            registration_start=timezone.now() - timedelta(hours=2),
            registration_end=timezone.now() + timedelta(days=1),
            start_date=timezone.now() + timedelta(days=2),
            end_date=timezone.now() + timedelta(days=3),
        )
        self.client.force_login(self.participant_user)

        response = self.client.get(reverse("messages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Старт реєстрації: {tournament.name}")

    def test_archive_page_shows_finished_tournament_and_my_results_link(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(days=2),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(days=3),
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Archive task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        team = Team.objects.create(
            name="Archive Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        submission = Submission.objects.create(
            team=team,
            task=task,
            github_link="https://github.com/example/archive",
            video_link="https://example.com/archive",
        )
        self.client.force_login(self.jury_user)
        self.client.post(
            reverse("submit_evaluation", args=[submission.id]),
            {
                f"eval-{submission.id}-score_backend": 80,
                f"eval-{submission.id}-score_frontend": 80,
                f"eval-{submission.id}-score_functionality": 80,
                f"eval-{submission.id}-score_ux": 80,
                f"eval-{submission.id}-comment": "Archive rating",
            },
        )
        self.client.force_login(self.captain)

        response = self.client.get(reverse("archive"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("team_results", args=[team.id]))

    def test_team_detail_shows_quick_team_block(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=10),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Quick task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        team = Team.objects.create(
            name="Quick Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        Submission.objects.create(
            team=team,
            task=task,
            github_link="https://github.com/example/quick",
            video_link="https://example.com/quick",
        )
        self.client.force_login(self.captain)

        response = self.client.get(reverse("team_detail", args=[team.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Швидкий блок команди")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, task.title)

    def test_admin_can_issue_participant_certificates(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(days=2),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(days=3),
        )
        team = Team.objects.create(
            name="Cert Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        registration = TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        RegistrationMember.objects.create(
            registration=registration,
            user=self.participant_user,
            full_name="Member",
            email=self.participant_user.email,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse("issue_participant_certificates", args=[tournament.id]))

        self.assertRedirects(response, reverse("admin_certificates"))
        self.assertTrue(
            Certificate.objects.filter(
                tournament=tournament,
                certificate_type=Certificate.CertificateType.PARTICIPANT,
                recipient_email="captain@example.com",
            ).exists()
        )
        self.assertTrue(
            Certificate.objects.filter(
                tournament=tournament,
                certificate_type=Certificate.CertificateType.PARTICIPANT,
                recipient_email=self.participant_user.email,
            ).exists()
        )

    def test_admin_can_upload_certificate_template_and_download_pdf(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(days=2),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(days=3),
        )
        team = Team.objects.create(
            name="Template Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        certificate = Certificate.objects.create(
            tournament=tournament,
            team=team,
            certificate_type=Certificate.CertificateType.PARTICIPANT,
            recipient_user=self.captain,
            recipient_name="Captain",
            recipient_email="captain@example.com",
            issued_by=self.admin_user,
        )
        self.client.force_login(self.admin_user)

        upload_response = self.client.post(
            reverse("admin_certificates"),
            {
                "tournament": tournament.id,
                "certificate_type": Certificate.CertificateType.PARTICIPANT,
                "background_image": self.make_test_image_upload(),
            },
        )

        self.assertRedirects(upload_response, reverse("admin_certificates"))
        self.assertTrue(
            CertificateTemplate.objects.filter(
                tournament=tournament,
                certificate_type=Certificate.CertificateType.PARTICIPANT,
            ).exists()
        )

        download_response = self.client.get(reverse("download_certificate_pdf", args=[certificate.id]))

        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", download_response["Content-Disposition"])

    def test_admin_can_export_results_csv(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=4),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        tournament.jury_users.add(self.jury_user)
        task = Task.objects.create(
            tournament=tournament,
            title="CSV task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        team = Team.objects.create(
            name="CSV Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        submission = Submission.objects.create(
            team=team,
            task=task,
            github_link="https://github.com/example/csv",
            video_link="https://example.com/csv",
        )
        self.client.force_login(self.jury_user)
        self.client.post(
            reverse("submit_evaluation", args=[submission.id]),
            {
                f"eval-{submission.id}-score_backend": 95,
                f"eval-{submission.id}-score_frontend": 90,
                f"eval-{submission.id}-score_functionality": 85,
                f"eval-{submission.id}-score_ux": 80,
                f"eval-{submission.id}-comment": "CSV export",
            },
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("export_tournament_results_csv", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("CSV Team", response.content.decode("utf-8-sig"))

    def test_leaderboard_json_endpoint_returns_rows_after_finish(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        tournament.jury_users.add(self.jury_user)
        task = Task.objects.create(
            tournament=tournament,
            title="Live task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        team = Team.objects.create(
            name="Live Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        submission = Submission.objects.create(
            team=team,
            task=task,
            github_link="https://github.com/example/live",
            video_link="https://example.com/live",
        )
        self.client.force_login(self.jury_user)
        self.client.post(
            reverse("submit_evaluation", args=[submission.id]),
            {
                f"eval-{submission.id}-score_backend": 88,
                f"eval-{submission.id}-score_frontend": 86,
                f"eval-{submission.id}-score_functionality": 92,
                f"eval-{submission.id}-score_ux": 90,
                f"eval-{submission.id}-comment": "Live rating",
            },
        )
        self.client.force_login(self.captain)

        response = self.client.get(reverse("tournament_leaderboard", args=[tournament.id]) + "?format=json")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rows"][0]["team_name"], "Live Team")
        self.assertEqual(payload["rows"][0]["place"], 1)

    def test_finished_tournament_hides_leaderboard_until_evaluation_finishes(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        tournament.jury_users.add(self.jury_user)
        task = Task.objects.create(
            tournament=tournament,
            title="Pending evaluation task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        team = Team.objects.create(
            name="Waiting Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        Submission.objects.create(
            team=team,
            task=task,
            github_link="https://github.com/example/waiting",
            video_link="https://example.com/video",
            is_final=True,
        )

        response = self.client.get(reverse("tournament_leaderboard", args=[tournament.id]))

        self.assertRedirects(response, reverse("tournament_tasks", args=[tournament.id]))

    def test_finished_tournament_publishes_results_after_first_evaluation(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        tournament.jury_users.add(self.jury_user)
        task = Task.objects.create(
            tournament=tournament,
            title="Evaluation task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        team = Team.objects.create(
            name="Evaluated Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        submission = Submission.objects.create(
            team=team,
            task=task,
            github_link="https://github.com/example/evaluated",
            video_link="https://example.com/video",
            is_final=True,
        )

        self.client.force_login(self.jury_user)
        response = self.client.post(
            reverse("submit_evaluation", args=[submission.id]),
            {
                f"eval-{submission.id}-score_backend": 88,
                f"eval-{submission.id}-score_frontend": 86,
                f"eval-{submission.id}-score_functionality": 92,
                f"eval-{submission.id}-score_ux": 90,
                f"eval-{submission.id}-comment": "Ready",
            },
        )

        self.assertRedirects(response, reverse("jury_tournament_detail", args=[tournament.id]))
        tournament.refresh_from_db()
        self.assertIsNotNone(tournament.evaluation_finished_at)

        self.client.force_login(self.captain)
        leaderboard_response = self.client.get(reverse("tournament_leaderboard", args=[tournament.id]))
        self.assertEqual(leaderboard_response.status_code, 200)
        self.assertContains(leaderboard_response, "Evaluated Team")

    def test_organizer_can_start_and_finish_tournament_now(self):
        tournament = self.create_tournament(
            created_by=self.organizer_user,
            start_date=timezone.now() + timedelta(days=5),
            end_date=timezone.now() + timedelta(days=6),
            registration_end=timezone.now() + timedelta(days=3),
        )
        self.client.force_login(self.organizer_user)

        start_response = self.client.post(reverse("start_tournament_now", args=[tournament.id]))
        finish_response = self.client.post(reverse("finish_tournament_now", args=[tournament.id]))

        self.assertRedirects(start_response, reverse("organizer_dashboard"))
        self.assertRedirects(finish_response, reverse("organizer_dashboard"))
        tournament.refresh_from_db()
        self.assertFalse(tournament.is_draft)
        self.assertLessEqual(tournament.registration_end, timezone.now())
        self.assertLessEqual(tournament.end_date, timezone.now())

    def test_organizer_can_finish_evaluation_manually(self):
        tournament = self.create_tournament(
            created_by=self.organizer_user,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        self.client.force_login(self.organizer_user)

        response = self.client.post(reverse("finish_evaluation_now", args=[tournament.id]))

        self.assertRedirects(response, reverse("organizer_dashboard"))
        tournament.refresh_from_db()
        self.assertIsNotNone(tournament.evaluation_finished_at)
        self.assertEqual(tournament.evaluation_finished_by, self.organizer_user)

    def test_admin_can_open_separate_create_user_page(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("create_user_by_admin"))

        self.assertRedirects(
            response,
            reverse("admin_users") + "?action=create-user",
            fetch_redirect_response=False,
        )
    def test_participant_dashboard_shows_running_tournaments(self):
        tournament = self.create_tournament(
            name="Running Cup",
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=3),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        Task.objects.create(
            tournament=tournament,
            title="Live task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        team = Team.objects.create(
            name="My Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )

        response = self.client.get(reverse("participant_dashboard"))

        tournaments = response.context["tournaments_with_state"]
        self.assertEqual(len(tournaments), 1)
        self.assertTrue(tournaments[0]["can_open_tasks"])

    def test_register_team_for_tournament_respects_max_teams(self):
        tournament = self.create_tournament(max_teams=1)
        existing_team = Team.objects.create(
            name="Busy Team",
            captain_user=self.admin_user,
            captain_name="Admin Captain",
            captain_email="admin-captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=existing_team,
            registered_by=self.admin_user,
            status=TournamentRegistration.Status.APPROVED,
        )

        my_team = Team.objects.create(
            name="My Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )

        response = self.client.post(
            reverse("register_team_for_tournament", args=[tournament.id]),
            {"team": my_team.id},
        )

        self.assertRedirects(response, reverse("participant_dashboard"))
        self.assertFalse(
            TournamentRegistration.objects.filter(
                tournament=tournament,
                team=my_team,
            ).exists()
        )

    def test_register_team_for_tournament_enforces_team_size_limits(self):
        tournament = self.create_tournament(
            min_team_members=3,
            max_team_members=4,
        )
        my_team = Team.objects.create(
            name="Small Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )

        response = self.client.post(
            reverse("register_team_for_tournament", args=[tournament.id]),
            {"team": my_team.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Потрібно щонайменше: 3")
        self.assertFalse(
            TournamentRegistration.objects.filter(
                tournament=tournament,
                team=my_team,
            ).exists()
        )

    def test_admin_can_define_registration_fields_for_tournament(self):
        tournament = self.create_tournament()
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("edit_tournament", args=[tournament.id]),
            {
                "name": tournament.name,
                "description": tournament.description,
                "registration_form_description": "Заповніть анкету команди",
                "registration_fields_definition": "school|Школа|text|required\ncoach_email|Email керівника|email|optional",
                "start_date": tournament.start_date.astimezone().strftime("%Y-%m-%dT%H:%M"),
                "end_date": tournament.end_date.astimezone().strftime("%Y-%m-%dT%H:%M"),
                "registration_start": tournament.registration_start.astimezone().strftime("%Y-%m-%dT%H:%M"),
                "registration_end": tournament.registration_end.astimezone().strftime("%Y-%m-%dT%H:%M"),
                "min_team_members": "",
                "max_team_members": "",
                "max_teams": "",
            },
        )

        self.assertRedirects(response, reverse("admin_active_tournaments"))
        tournament.refresh_from_db()
        self.assertEqual(
            tournament.registration_fields_config,
            [
                {"key": "school", "label": "Школа", "type": "text", "required": True},
                {"key": "coach_email", "label": "Email керівника", "type": "email", "required": False},
            ],
        )

    def test_registration_page_renders_dynamic_fields_and_saves_answers(self):
        tournament = self.create_tournament(
            registration_fields_config=[
                {"key": "school", "label": "Школа", "type": "text", "required": True},
                {"key": "coach_email", "label": "Email керівника", "type": "email", "required": False},
            ],
        )
        my_team = Team.objects.create(
            name="Dynamic Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )

        response = self.client.get(reverse("register_team_for_tournament", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Школа")
        self.assertContains(response, "Email керівника")

        response = self.client.post(
            reverse("register_team_for_tournament", args=[tournament.id]),
            {
                "team": my_team.id,
                "field_school": "Ліцей №1",
                "field_coach_email": "coach@example.com",
            },
        )

        self.assertRedirects(response, reverse("participant_dashboard"))
        registration = TournamentRegistration.objects.get(tournament=tournament, team=my_team)
        self.assertEqual(registration.status, TournamentRegistration.Status.PENDING)
        self.assertEqual(
            registration.form_answers,
            {"school": "Ліцей №1", "coach_email": "coach@example.com"},
        )

    def test_registration_participants_field_updates_team_members(self):
        tournament = self.create_tournament(
            min_team_members=3,
            max_team_members=4,
            registration_fields_config=[
                {"key": "participants", "label": "Учасники", "type": "participants", "required": True},
            ],
        )
        my_team = Team.objects.create(
            name="Roster Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )

        response = self.client.post(
            reverse("register_team_for_tournament", args=[tournament.id]),
            {
                "team": my_team.id,
                "field_participants": '[{"full_name":"Іван","email":"ivan@example.com"},{"full_name":"Марія","email":"maria@example.com"}]',
            },
        )

        self.assertRedirects(response, reverse("participant_dashboard"))
        registration = TournamentRegistration.objects.get(tournament=tournament, team=my_team)
        self.assertEqual(len(registration.form_answers["participants"]), 2)
        self.assertEqual(my_team.participants.count(), 2)
        self.assertTrue(my_team.participants.filter(full_name="Іван", email="ivan@example.com").exists())
        self.assertTrue(my_team.participants.filter(full_name="Марія", email="maria@example.com").exists())

    def test_registration_participants_field_does_not_delete_existing_team_members(self):
        tournament = self.create_tournament(
            min_team_members=2,
            max_team_members=4,
            registration_fields_config=[
                {"key": "participants", "label": "Учасники", "type": "participants", "required": True},
            ],
        )
        my_team = Team.objects.create(
            name="Stable Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        Participant.objects.create(
            team=my_team,
            full_name="Old Member",
            email="oldmember@example.com",
        )

        response = self.client.post(
            reverse("register_team_for_tournament", args=[tournament.id]),
            {
                "team": my_team.id,
                "field_participants": '[{"full_name":"New Member","email":"newmember@example.com"}]',
            },
        )

        self.assertRedirects(response, reverse("participant_dashboard"))
        self.assertTrue(my_team.participants.filter(email="oldmember@example.com").exists())
        self.assertTrue(my_team.participants.filter(email="newmember@example.com").exists())

    def test_registration_participants_field_respects_member_limits(self):
        tournament = self.create_tournament(
            min_team_members=3,
            max_team_members=3,
            registration_fields_config=[
                {"key": "participants", "label": "Учасники", "type": "participants", "required": True},
            ],
        )
        my_team = Team.objects.create(
            name="Strict Roster Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )

        response = self.client.post(
            reverse("register_team_for_tournament", args=[tournament.id]),
            {
                "team": my_team.id,
                "field_participants": '[{"full_name":"Іван","email":"ivan@example.com"}]',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Потрібно щонайменше: 3")
        self.assertFalse(TournamentRegistration.objects.filter(tournament=tournament, team=my_team).exists())

    def test_registration_rejects_email_that_is_already_in_another_team_of_same_tournament(self):
        tournament = self.create_tournament(
            min_team_members=2,
            max_team_members=3,
            registration_fields_config=[
                {"key": "participants", "label": "Учасники", "type": "participants", "required": True},
            ],
        )
        other_captain = User.objects.create_user(
            username="captain_other",
            password="secret123",
            role="participant",
            is_approved=True,
            email="captain_other@example.com",
        )
        other_team = Team.objects.create(
            name="Other Team",
            captain_user=other_captain,
            captain_name="Other Captain",
            captain_email="captain_other@example.com",
        )
        other_registration = TournamentRegistration.objects.create(
            tournament=tournament,
            team=other_team,
            registered_by=other_captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        RegistrationMember.objects.create(
            registration=other_registration,
            full_name="Shared Student",
            email="shared@example.com",
        )

        response = self.client.post(
            reverse("register_team_for_tournament", args=[tournament.id]),
            {
                "team_name": "My Team",
                "captain_name": "Captain",
                "captain_email": "captain@example.com",
                "field_participants": '[{"full_name":"Іван","email":"shared@example.com"}]',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Один email не може бути у двох командах цього турніру.")
        self.assertFalse(
            TournamentRegistration.objects.filter(
                tournament=tournament,
                team__captain_user=self.captain,
            ).exists()
        )

    def test_captain_cannot_edit_team_after_registration_end(self):
        tournament = self.create_tournament(registration_end=timezone.now() - timedelta(hours=2))
        team = Team.objects.create(
            name="Locked Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )

        response = self.client.post(
            reverse("edit_team", args=[team.id]),
            {
                "name": "Updated Team",
                "captain_name": "Captain",
                "captain_email": "captain@example.com",
                "school": "",
                "preferred_contact_method": "",
                "preferred_contact_value": "",
            },
        )

        self.assertRedirects(response, reverse("team_detail", args=[team.id]))
        team.refresh_from_db()
        self.assertEqual(team.name, "Locked Team")

    def test_captain_cannot_add_participant_after_registration_end(self):
        tournament = self.create_tournament(registration_end=timezone.now() - timedelta(hours=2))
        team = Team.objects.create(
            name="Locked Roster Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )

        response = self.client.post(
            reverse("add_participant", args=[team.id]),
            {
                "full_name": "Late Member",
                "email": "late@example.com",
            },
        )

        self.assertRedirects(response, reverse("team_detail", args=[team.id]))
        self.assertFalse(team.participants.filter(email="late@example.com").exists())

    def test_captain_cannot_add_duplicate_participant_to_team(self):
        team = Team.objects.create(
            name="Duplicate Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        Participant.objects.create(
            team=team,
            full_name="Existing Member",
            email="member@example.com",
        )

        response = self.client.post(
            reverse("add_participant", args=[team.id]),
            {
                "full_name": "Existing Member Again",
                "email": "member@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Цей учасник уже є в команді.")
        self.assertEqual(team.participants.filter(email="member@example.com").count(), 1)

    def test_captain_cannot_add_participant_from_another_team(self):
        team = Team.objects.create(
            name="Main Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        other_captain = User.objects.create_user(
            username="othercaptain",
            password="secret123",
            role="participant",
            is_approved=True,
            email="othercaptain@example.com",
        )
        other_team = Team.objects.create(
            name="Other Team",
            captain_user=other_captain,
            captain_name="Other Captain",
            captain_email="othercaptain@example.com",
        )
        Participant.objects.create(
            team=other_team,
            full_name="Existing Elsewhere",
            email="sharedmember@example.com",
        )

        response = self.client.post(
            reverse("add_participant", args=[team.id]),
            {
                "full_name": "Existing Elsewhere",
                "email": "sharedmember@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Цей учасник уже зареєстрований в іншій команді.")
        self.assertFalse(team.participants.filter(email="sharedmember@example.com").exists())
        self.assertEqual(other_team.participants.filter(email="sharedmember@example.com").count(), 1)

    @patch("users.team_services.email_delivery_ready", return_value=True)
    @patch("users.team_services.send_team_invitation_email")
    def test_captain_sees_message_and_invitation_is_sent_for_unregistered_participant(self, mock_send_invite, _mock_delivery_ready):
        team = Team.objects.create(
            name="Invite Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )

        response = self.client.post(
            reverse("add_participant", args=[team.id]),
            {
                "full_name": "New Person",
                "email": "newperson@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Такого учасника не зареєстровано на платформі. Ми надіслали йому лист із запрошенням зареєструватися.",
        )
        self.assertFalse(team.participants.filter(email="newperson@example.com").exists())
        mock_send_invite.assert_called_once()

    @override_settings(DEBUG=False, EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_captain_sees_message_when_unregistered_participant_email_invite_is_unavailable(self):
        team = Team.objects.create(
            name="Invite Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )

        response = self.client.post(
            reverse("add_participant", args=[team.id]),
            {
                "full_name": "New Person",
                "email": "newperson@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Такого учасника не зареєстровано на платформі. Запрошення не вдалося надіслати, бо email не налаштовано.",
        )
        self.assertFalse(team.participants.filter(email="newperson@example.com").exists())

    def test_team_detail_counts_captain_in_members_total(self):
        team = Team.objects.create(
            name="Count Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )

        response = self.client.get(reverse("team_detail", args=[team.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["participants_count"], 1)
        self.assertContains(response, '<div class="stat-value">1</div>', html=False)

    def test_team_detail_back_button_leads_to_home(self):
        team = Team.objects.create(
            name="Back Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )

        response = self.client.get(reverse("team_detail", args=[team.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("home")}"', html=False)

    def test_participant_cannot_leave_team_after_registration_end(self):
        self.client.force_login(self.participant_user)
        tournament = self.create_tournament(registration_end=timezone.now() - timedelta(hours=2))
        team = Team.objects.create(
            name="Closed Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        Participant.objects.create(
            team=team,
            full_name="Member",
            email=self.participant_user.email,
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )

        response = self.client.post(reverse("leave_team", args=[team.id]))

        self.assertRedirects(response, reverse("team_detail", args=[team.id]))
        self.assertTrue(team.participants.filter(email=self.participant_user.email).exists())

    def test_tasks_stay_locked_until_registration_is_approved(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(days=1),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        team = Team.objects.create(
            name="Pending Access Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.PENDING,
        )

        response = self.client.get(reverse("participant_dashboard"))

        self.assertContains(response, "Завдання відкриються після схвалення заявки")
        self.assertContains(response, "Очікує")

    def test_outsider_cannot_open_tournament_leaderboard(self):
        outsider = User.objects.create_user(
            username="outsider",
            password="secret123",
            role="participant",
            is_approved=True,
            email="outsider@example.com",
        )
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        self.client.force_login(outsider)

        response = self.client.get(reverse("tournament_leaderboard", args=[tournament.id]))

        self.assertRedirects(response, reverse("participant_dashboard"))

    def test_rejected_registration_does_not_block_retry(self):
        tournament = self.create_tournament()
        my_team = Team.objects.create(
            name="Retry Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=my_team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.REJECTED,
        )

        response = self.client.get(
            reverse("register_team_for_tournament", args=[tournament.id]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Retry Team")

    def test_rejected_registration_still_shows_retry_button_on_dashboard(self):
        tournament = self.create_tournament()
        my_team = Team.objects.create(
            name="Retry Dashboard Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=my_team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.REJECTED,
        )

        response = self.client.get(reverse("participant_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Подати знову")
        self.assertContains(response, reverse("register_team_for_tournament", args=[tournament.id]))

    def test_submit_solution_requires_approved_registration(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(days=1),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        team = Team.objects.create(
            name="Pending Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.PENDING,
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Build app",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )

        response = self.client.post(
            reverse("submit_solution", args=[task.id]),
            {
                "github_link": "https://github.com/example/repo",
                "video_link": "https://example.com/video",
            },
        )

        self.assertRedirects(response, reverse("participant_dashboard"))
        self.assertFalse(task.submissions.exists())

    def test_submit_solution_saves_all_fields(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(days=1),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        team = Team.objects.create(
            name="Approved Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Build app",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )

        response = self.client.post(
            reverse("submit_solution", args=[task.id]),
            {
                "github_link": "https://github.com/example/repo",
                "video_link": "https://example.com/video",
                "live_demo": "https://example.com/demo",
                "description": "My final solution",
                "is_final": "on",
            },
        )

        self.assertRedirects(response, reverse("team_detail", args=[team.id]))
        submission = Submission.objects.get(team=team, task=task)
        self.assertEqual(submission.live_demo, "https://example.com/demo")
        self.assertEqual(submission.description, "My final solution")
        self.assertTrue(submission.is_final)

    def test_submit_solution_saves_custom_answer_fields_from_task_format(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(days=1),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        team = Team.objects.create(
            name="Language Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Essay",
            description="desc",
            requirements="req",
            must_have="must",
            submission_fields_config=[
                {"key": "essay_text", "label": "Текст відповіді", "type": "textarea", "required": True, "builtin": False},
                {"key": "description", "label": "Коментар", "type": "textarea", "required": False, "builtin": True},
            ],
            is_draft=False,
            created_by=self.admin_user,
        )

        response = self.client.post(
            reverse("submit_solution", args=[task.id]),
            {
                "essay_text": "Моя розгорнута відповідь",
                "description": "Додатковий коментар",
            },
        )

        self.assertRedirects(response, reverse("team_detail", args=[team.id]))
        submission = Submission.objects.get(team=team, task=task)
        self.assertEqual(submission.form_answers["essay_text"], "Моя розгорнута відповідь")
        self.assertEqual(submission.description, "Додатковий коментар")

    def test_submit_solution_is_blocked_after_task_deadline(self):
        now = timezone.now()
        tournament = self.create_tournament(
            start_date=now - timedelta(hours=2),
            end_date=now + timedelta(days=1),
            registration_end=now - timedelta(hours=3),
        )
        team = Team.objects.create(
            name="Approved Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Closed task",
            description="desc",
            requirements="req",
            must_have="must",
            start_at=now - timedelta(hours=2),
            deadline=now - timedelta(minutes=1),
            is_draft=False,
            created_by=self.admin_user,
        )

        response = self.client.post(
            reverse("submit_solution", args=[task.id]),
            {
                "github_link": "https://github.com/example/repo",
                "video_link": "https://example.com/video",
            },
        )

        self.assertRedirects(response, reverse("tournament_tasks", args=[tournament.id]))
        self.assertFalse(Submission.objects.filter(task=task, team=team).exists())

    def test_superuser_can_open_team_detail(self):
        team = Team.objects.create(
            name="Team A",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("team_detail", args=[team.id]))

        self.assertEqual(response.status_code, 200)

    def test_superuser_sees_inline_participant_form_on_team_page(self):
        team = Team.objects.create(
            name="Team Inline",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("team_detail", args=[team.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("add_participant", args=[team.id]))

    def test_admin_can_create_user_from_dashboard(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_user_by_admin"),
            {
                "username": "manualjury",
                "email": "manualjury@example.com",
                "role": "jury",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("admin_users"))
        created_user = User.objects.get(username="manualjury")
        self.assertEqual(created_user.role, "jury")
        self.assertFalse(created_user.is_approved)

    def test_admin_can_open_contextual_create_task_page(self):
        tournament = self.create_tournament()
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("create_tournament_task", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 200)

    def test_edit_tournament_page_has_add_task_button(self):
        tournament = self.create_tournament()
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("edit_tournament", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("create_tournament_task", args=[tournament.id]))

    def test_edit_tournament_page_shows_existing_tasks(self):
        tournament = self.create_tournament()
        task = Task.objects.create(
            tournament=tournament,
            title="Shown task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("edit_tournament", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, task.title)
        self.assertContains(response, reverse("edit_task", args=[task.id]))

    def test_create_task_returns_to_edit_tournament(self):
        tournament = self.create_tournament()
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_tournament_task", args=[tournament.id]),
            {
                "tournament": tournament.id,
                "title": "Context task",
                "description": "desc",
                "requirements": "req",
                "must_have": "must",
                "start_at": timezone.localtime(tournament.start_date).strftime("%Y-%m-%dT%H:%M"),
                "deadline": timezone.localtime(tournament.end_date).strftime("%Y-%m-%dT%H:%M"),
                "official_solution": "solution",
            },
        )

        self.assertRedirects(response, reverse("edit_tournament", args=[tournament.id]))
        task = Task.objects.get(title="Context task")
        self.assertEqual(task.start_at.replace(second=0, microsecond=0), tournament.start_date.replace(second=0, microsecond=0))
        self.assertEqual(task.deadline.replace(second=0, microsecond=0), tournament.end_date.replace(second=0, microsecond=0))

    def test_create_task_rejects_empty_submission_format_definition(self):
        tournament = self.create_tournament()
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_tournament_task", args=[tournament.id]),
            {
                "tournament": tournament.id,
                "title": "Context task",
                "description": "desc",
                "requirements": "req",
                "must_have": "must",
                "submission_preset": "generic",
                "submission_fields_definition": "",
                "start_at": timezone.localtime(tournament.start_date).strftime("%Y-%m-%dT%H:%M"),
                "deadline": timezone.localtime(tournament.end_date).strftime("%Y-%m-%dT%H:%M"),
                "official_solution": "solution",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Потрібно додати хоча б одне поле формату відповіді.")

    def test_edit_task_page_back_link_points_to_edit_tournament(self):
        tournament = self.create_tournament()
        task = Task.objects.create(
            tournament=tournament,
            title="Back task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("edit_task", args=[task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("edit_tournament", args=[tournament.id]))

    def test_admin_can_create_draft_tournament_without_dates(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_tournament"),
            {
                "name": "",
                "description": "",
                "allowed_contact_methods": ["telegram"],
                "start_date": "",
                "end_date": "",
                "registration_start": "",
                "registration_end": "",
                "max_teams": "",
                "is_draft": "on",
            },
        )

        self.assertRedirects(response, reverse("admin_active_tournaments"))
        tournament = Tournament.objects.latest("id")
        self.assertTrue(tournament.is_draft)
        self.assertIsNone(tournament.start_date)
        self.assertIsNone(tournament.end_date)

    def test_admin_can_create_draft_tournament_with_registration_fields(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_tournament"),
            {
                "name": "",
                "description": "",
                "registration_form_description": "",
                "registration_fields_definition": "participants|Учасники|participants|required\nschool|Школа|text|optional",
                "allowed_contact_methods": ["telegram"],
                "start_date": "",
                "end_date": "",
                "registration_start": "",
                "registration_end": "",
                "min_team_members": "2",
                "max_team_members": "4",
                "max_teams": "",
                "is_draft": "on",
            },
        )

        self.assertRedirects(response, reverse("admin_active_tournaments"))
        tournament = Tournament.objects.latest("id")
        self.assertTrue(tournament.is_draft)
        self.assertEqual(
            tournament.registration_fields_config,
            [
                {"key": "participants", "label": "Учасники", "type": "participants", "required": True},
                {"key": "school", "label": "Школа", "type": "text", "required": False},
            ],
        )

    def test_admin_can_edit_draft_tournament_without_dates(self):
        tournament = Tournament.objects.create(
            name="Draft Tournament",
            description="",
            is_draft=True,
            created_by=self.admin_user,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("edit_tournament", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Draft Tournament")

    def test_admin_can_create_draft_task_without_required_fields(self):
        tournament = self.create_tournament()
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_tournament_task", args=[tournament.id]),
            {
                "tournament": tournament.id,
                "title": "",
                "description": "",
                "requirements": "",
                "must_have": "",
                "official_solution": "",
                "is_draft": "on",
            },
        )

        self.assertRedirects(response, reverse("edit_tournament", args=[tournament.id]))
        task = Task.objects.latest("id")
        self.assertTrue(task.is_draft)
        self.assertEqual(task.title, "")

    def test_admin_cannot_publish_task_without_task_dates(self):
        tournament = self.create_tournament()
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_tournament_task", args=[tournament.id]),
            {
                "tournament": tournament.id,
                "title": "Task without dates",
                "description": "desc",
                "requirements": "req",
                "must_have": "must",
                "official_solution": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Це поле є обов’язковим для опублікованого завдання.")
        self.assertFalse(Task.objects.filter(title="Task without dates").exists())

    def test_admin_can_approve_registration(self):
        tournament = self.create_tournament()
        team = Team.objects.create(
            name="Approval Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        registration = TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.PENDING,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse("approve_registration", args=[registration.id]))

        self.assertRedirects(response, reverse("admin_users"))
        registration.refresh_from_db()
        self.assertEqual(registration.status, TournamentRegistration.Status.APPROVED)

    def test_admin_approval_requires_post(self):
        pending_user = User.objects.create_user(
            username="pending_jury",
            password="secret123",
            role="jury",
            is_approved=False,
            email="pending-jury@example.com",
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("approve_user", args=[pending_user.id]))

        self.assertEqual(response.status_code, 405)

    def test_admin_registration_decision_requires_post(self):
        tournament = self.create_tournament()
        team = Team.objects.create(
            name="Pending Approval Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        registration = TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.PENDING,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("approve_registration", args=[registration.id]))

        self.assertEqual(response.status_code, 405)
        registration.refresh_from_db()
        self.assertEqual(registration.status, TournamentRegistration.Status.PENDING)

    def test_admin_can_change_user_role(self):
        jury_candidate = User.objects.create_user(
            username="student1",
            password="secret123",
            role="participant",
            is_approved=True,
            email="student1@example.com",
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("update_user_role", args=[jury_candidate.id]),
            {"role": "jury"},
        )

        self.assertRedirects(response, reverse("admin_dashboard"))
        jury_candidate.refresh_from_db()
        self.assertEqual(jury_candidate.role, "jury")

    def test_admin_can_delete_user(self):
        removable_user = User.objects.create_user(
            username="captain2",
            password="secret123",
            role="participant",
            is_approved=True,
            email="captain2@example.com",
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse("delete_user", args=[removable_user.id]))

        self.assertRedirects(response, reverse("admin_users"))
        self.assertFalse(User.objects.filter(id=removable_user.id).exists())

    def test_admin_can_delete_tournament(self):
        tournament = self.create_tournament()
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse("delete_tournament", args=[tournament.id]))

        self.assertRedirects(response, reverse("admin_dashboard"))
        self.assertFalse(Tournament.objects.filter(id=tournament.id).exists())

    def test_admin_can_delete_task(self):
        tournament = self.create_tournament()
        task = Task.objects.create(
            tournament=tournament,
            title="Delete me",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse("delete_task", args=[task.id]))

        self.assertRedirects(response, reverse("admin_dashboard"))
        self.assertFalse(Task.objects.filter(id=task.id).exists())

    def test_admin_cannot_edit_tournament_after_registration_ends(self):
        tournament = self.create_tournament(
            registration_end=timezone.now() - timedelta(hours=1),
            start_date=timezone.now() + timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=3),
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("edit_tournament", args=[tournament.id]))

        self.assertRedirects(response, reverse("admin_dashboard"))

    def test_edit_tournament_prefills_datetime_fields(self):
        tournament = self.create_tournament()
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("edit_tournament", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            tournament.start_date.astimezone().strftime("%Y-%m-%dT%H:%M"),
            html=False,
        )
        self.assertContains(
            response,
            tournament.end_date.astimezone().strftime("%Y-%m-%dT%H:%M"),
            html=False,
        )

    def test_captain_sees_published_tournament_before_registration_starts(self):
        tournament = self.create_tournament(
            registration_start=timezone.now() + timedelta(days=1),
            registration_end=timezone.now() + timedelta(days=2),
            start_date=timezone.now() + timedelta(days=3),
            end_date=timezone.now() + timedelta(days=4),
            is_draft=False,
        )

        response = self.client.get(reverse("participant_dashboard"))

        tournaments = response.context["tournaments_with_state"]
        self.assertEqual(len(tournaments), 1)
        self.assertEqual(tournaments[0]["tournament"].id, tournament.id)
        self.assertFalse(tournaments[0]["can_register"])

    def test_draft_tournament_is_hidden_from_participant_until_published(self):
        Tournament.objects.create(
            name="Hidden Draft",
            description="Draft",
            registration_start=timezone.now() - timedelta(days=1),
            registration_end=timezone.now() + timedelta(days=1),
            start_date=timezone.now() + timedelta(days=2),
            end_date=timezone.now() + timedelta(days=3),
            is_draft=True,
            created_by=self.admin_user,
        )

        response = self.client.get(reverse("participant_dashboard"))

        tournaments = response.context["tournaments_with_state"]
        self.assertEqual(len(tournaments), 0)

    def test_finished_tournament_stays_visible_for_approved_team(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(days=2),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(days=3),
        )
        team = Team.objects.create(
            name="Archive Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )

        response = self.client.get(reverse("participant_dashboard"))

        tournaments = response.context["tournaments_with_state"]
        self.assertEqual(len(tournaments), 1)
        self.assertTrue(tournaments[0]["can_open_tasks"])

    def test_official_solution_is_visible_only_after_tournament_finish(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=2),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Solution task",
            description="desc",
            requirements="req",
            must_have="must",
            official_solution="Official walkthrough",
            is_draft=False,
            created_by=self.admin_user,
        )
        team = Team.objects.create(
            name="Approved Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )

        response = self.client.get(reverse("tournament_tasks", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, task.official_solution)

        tournament.end_date = timezone.now() - timedelta(minutes=1)
        tournament.save(update_fields=["end_date"])

        response = self.client.get(reverse("tournament_tasks", args=[tournament.id]))

        self.assertContains(response, task.official_solution)
        self.assertNotContains(response, reverse("submit_solution", args=[task.id]))

    def test_admin_cannot_create_task_after_registration_ends(self):
        tournament = self.create_tournament(
            registration_end=timezone.now() - timedelta(hours=1),
            start_date=timezone.now() + timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=3),
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("create_tournament_task", args=[tournament.id]))

        self.assertRedirects(response, reverse("admin_dashboard"))

    def test_admin_cannot_edit_task_after_registration_ends(self):
        tournament = self.create_tournament(
            registration_end=timezone.now() - timedelta(hours=1),
            start_date=timezone.now() + timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=3),
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Locked task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("edit_task", args=[task.id]))

        self.assertRedirects(response, reverse("admin_dashboard"))

    def test_jury_dashboard_shows_tournaments_with_submissions(self):
        tournament = self.create_tournament()
        team = Team.objects.create(
            name="Jury Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Demo task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        Submission.objects.create(
            team=team,
            task=task,
            github_link="https://github.com/example/repo",
            video_link="https://example.com/video",
        )
        self.client.force_login(self.jury_user)

        response = self.client.get(reverse("jury_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 200)

    def test_jury_can_open_tournament_detail_with_team_submissions(self):
        tournament = self.create_tournament()
        tournament.jury_users.add(self.jury_user)
        team = Team.objects.create(
            name="Folder Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Folder task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        Submission.objects.create(
            team=team,
            task=task,
            github_link="https://github.com/example/repo",
            video_link="https://example.com/video",
            description="Submission for jury",
        )
        self.client.force_login(self.jury_user)

        response = self.client.get(reverse("jury_tournament_detail", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, team.name)
        self.assertContains(response, task.title)

    def test_jury_can_submit_evaluation(self):
        tournament = self.create_tournament()
        team = Team.objects.create(
            name="Scored Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Score task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        submission = Submission.objects.create(
            team=team,
            task=task,
            github_link="https://github.com/example/repo",
            video_link="https://example.com/video",
        )
        self.client.force_login(self.jury_user)

        response = self.client.post(
            reverse("submit_evaluation", args=[submission.id]),
            {
                f"eval-{submission.id}-score_backend": 80,
                f"eval-{submission.id}-score_frontend": 90,
                f"eval-{submission.id}-score_functionality": 85,
                f"eval-{submission.id}-score_ux": 95,
                f"eval-{submission.id}-comment": "Strong work",
            },
        )

        self.assertRedirects(response, reverse("jury_tournament_detail", args=[tournament.id]))
        evaluation = Evaluation.objects.get(assignment__submission=submission, assignment__jury_user=self.jury_user)
        self.assertEqual(evaluation.score_backend, 80)
        self.assertEqual(evaluation.comment, "Strong work")

    def test_captain_sees_jury_evaluation_in_team_results(self):
        tournament = self.create_tournament()
        team = Team.objects.create(
            name="Visible Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Results task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        submission = Submission.objects.create(
            team=team,
            task=task,
            github_link="https://github.com/example/repo",
            video_link="https://example.com/video",
        )
        self.client.force_login(self.jury_user)
        self.client.post(
            reverse("submit_evaluation", args=[submission.id]),
            {
                f"eval-{submission.id}-score_backend": 80,
                f"eval-{submission.id}-score_frontend": 90,
                f"eval-{submission.id}-score_functionality": 85,
                f"eval-{submission.id}-score_ux": 95,
                f"eval-{submission.id}-comment": "Visible comment",
            },
        )
        self.client.force_login(self.captain)

        response = self.client.get(reverse("team_results", args=[team.id]))

        self.assertContains(response, "Visible comment")
        self.assertContains(response, "87,5")

    def test_participant_sees_jury_evaluation_in_team_results(self):
        tournament = self.create_tournament()
        team = Team.objects.create(
            name="Member Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        Participant.objects.create(
            team=team,
            full_name="Member",
            email=self.participant_user.email,
        )
        task = Task.objects.create(
            tournament=tournament,
            title="Participant results task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        submission = Submission.objects.create(
            team=team,
            task=task,
            github_link="https://github.com/example/repo",
            video_link="https://example.com/video",
        )
        self.client.force_login(self.jury_user)
        self.client.post(
            reverse("submit_evaluation", args=[submission.id]),
            {
                f"eval-{submission.id}-score_backend": 70,
                f"eval-{submission.id}-score_frontend": 75,
                f"eval-{submission.id}-score_functionality": 80,
                f"eval-{submission.id}-score_ux": 85,
                f"eval-{submission.id}-comment": "Seen by participant",
            },
        )
        self.client.force_login(self.participant_user)

        response = self.client.get(reverse("team_results", args=[team.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seen by participant")

    def test_captain_can_delete_team(self):
        team = Team.objects.create(
            name="Delete Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        self.client.force_login(self.captain)

        response = self.client.post(reverse("delete_team", args=[team.id]))

        self.assertRedirects(response, reverse("participant_dashboard"))
        self.assertFalse(Team.objects.filter(id=team.id).exists())

    def test_superuser_delete_team_redirects_to_admin_teams(self):
        team = Team.objects.create(
            name="Admin Delete Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse("delete_team", args=[team.id]))

        self.assertRedirects(response, reverse("admin_teams"))
        self.assertFalse(Team.objects.filter(id=team.id).exists())

    def test_participant_can_leave_team(self):
        team = Team.objects.create(
            name="Leave Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        Participant.objects.create(
            team=team,
            full_name="Member",
            email=self.participant_user.email,
        )
        self.client.force_login(self.participant_user)

        response = self.client.post(reverse("leave_team", args=[team.id]))

        self.assertRedirects(response, reverse("participant_dashboard"))
        self.assertFalse(team.participants.filter(email=self.participant_user.email).exists())

    def test_participant_can_open_team_participants_page(self):
        team = Team.objects.create(
            name="Participants Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        Participant.objects.create(
            team=team,
            full_name="Member",
            email=self.participant_user.email,
        )
        self.client.force_login(self.participant_user)

        response = self.client.get(reverse("team_participants", args=[team.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Member")

    def test_tournament_leaderboard_orders_teams_by_average_score(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() - timedelta(hours=1),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        tournament.jury_users.add(self.jury_user)
        task = Task.objects.create(
            tournament=tournament,
            title="Leaderboard task",
            description="desc",
            requirements="req",
            must_have="must",
            is_draft=False,
            created_by=self.admin_user,
        )
        first_team = Team.objects.create(
            name="Alpha Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        second_captain = User.objects.create_user(
            username="captain_b",
            password="secret123",
            role="participant",
            is_approved=True,
            email="captainb@example.com",
        )
        second_team = Team.objects.create(
            name="Beta Team",
            captain_user=second_captain,
            captain_name="Captain B",
            captain_email="captainb@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=first_team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=second_team,
            registered_by=second_captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        first_submission = Submission.objects.create(
            team=first_team,
            task=task,
            github_link="https://github.com/example/a",
            video_link="https://example.com/a",
        )
        second_submission = Submission.objects.create(
            team=second_team,
            task=task,
            github_link="https://github.com/example/b",
            video_link="https://example.com/b",
        )
        self.client.force_login(self.jury_user)
        self.client.post(
            reverse("submit_evaluation", args=[first_submission.id]),
            {
                f"eval-{first_submission.id}-score_backend": 95,
                f"eval-{first_submission.id}-score_frontend": 90,
                f"eval-{first_submission.id}-score_functionality": 95,
                f"eval-{first_submission.id}-score_ux": 100,
                f"eval-{first_submission.id}-comment": "Alpha first",
            },
        )
        self.client.post(
            reverse("submit_evaluation", args=[second_submission.id]),
            {
                f"eval-{second_submission.id}-score_backend": 70,
                f"eval-{second_submission.id}-score_frontend": 75,
                f"eval-{second_submission.id}-score_functionality": 80,
                f"eval-{second_submission.id}-score_ux": 85,
                f"eval-{second_submission.id}-comment": "Beta second",
            },
        )
        self.client.force_login(self.captain)

        response = self.client.get(reverse("tournament_leaderboard", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        leaderboard = response.context["leaderboard"]
        self.assertEqual(leaderboard[0]["team"].name, "Alpha Team")
        self.assertEqual(leaderboard[0]["place"], 1)
        self.assertEqual(leaderboard[1]["team"].name, "Beta Team")

    def test_messages_page_includes_system_tournament_events(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=20),
            registration_end=timezone.now() - timedelta(hours=2),
        )
        team = Team.objects.create(
            name="Messages Team",
            captain_user=self.captain,
            captain_name="Captain",
            captain_email="captain@example.com",
        )
        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=self.captain,
            status=TournamentRegistration.Status.APPROVED,
        )
        self.client.force_login(self.captain)

        response = self.client.get(reverse("messages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Старт реєстрації: {tournament.name}")
        self.assertContains(response, f"Старт завдань: {tournament.name}")
        self.assertContains(response, "24 години до дедлайну")


