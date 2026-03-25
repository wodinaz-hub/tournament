import shutil
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
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
    TournamentRegistration,
)


User = get_user_model()


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
            role="captain",
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
            username="curator",
            password="secret123",
            role="curator",
            is_approved=True,
            email="curator@example.com",
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

    def test_register_form_creates_participant_and_logs_in(self):
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

        self.assertRedirects(response, reverse("home"))
        created_user = User.objects.get(username="newparticipant")
        self.assertEqual(created_user.role, "participant")
        self.assertTrue(created_user.is_approved)

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

    def test_home_page_is_public_and_shows_tournaments(self):
        self.client.logout()
        tournament = self.create_tournament(name="Public Cup")

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public Cup")
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
                "telegram": "@team",
            },
        )

        self.assertRedirects(response, reverse("participant_dashboard"))
        self.assertTrue(Team.objects.filter(name="Participant Team", captain_user=self.participant_user).exists())

    def test_participant_can_submit_registration_from_public_tournament_page(self):
        tournament = self.create_tournament(
            registration_fields_config=[
                {"key": "school", "label": "Школа", "type": "text", "required": True},
            ],
        )
        team = Team.objects.create(
            name="Open Team",
            captain_user=self.participant_user,
            captain_name="Member Captain",
            captain_email=self.participant_user.email,
        )
        self.client.force_login(self.participant_user)

        response = self.client.post(
            reverse("public_tournament_detail", args=[tournament.id]),
            {
                "team": team.id,
                "field_school": "Ліцей",
            },
        )

        self.assertRedirects(response, reverse("participant_dashboard"))
        registration = TournamentRegistration.objects.get(tournament=tournament, team=team)
        self.assertEqual(registration.status, TournamentRegistration.Status.PENDING)
        self.assertEqual(registration.form_answers["school"], "Ліцей")
        self.participant_user.refresh_from_db()
        self.assertEqual(self.participant_user.role, "captain")

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

    def test_admin_can_assign_curator_role(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("update_user_role", args=[self.participant_user.id]),
            {
                "role": "curator",
            },
        )

        self.assertRedirects(response, reverse("admin_users"))
        self.participant_user.refresh_from_db()
        self.assertEqual(self.participant_user.role, "curator")

    def test_curator_can_open_assigned_tournament(self):
        tournament = self.create_tournament()
        tournament.curator_users.add(self.curator_user)
        self.client.force_login(self.curator_user)

        response = self.client.get(reverse("curator_tournament_detail", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, tournament.name)

    def test_curator_can_approve_registration_for_assigned_tournament(self):
        tournament = self.create_tournament()
        tournament.curator_users.add(self.curator_user)
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

        self.assertRedirects(response, reverse("curator_dashboard"))
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
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=3),
            registration_end=timezone.now() - timedelta(hours=2),
        )
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

    def test_leaderboard_json_endpoint_returns_live_rows(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=3),
            registration_end=timezone.now() - timedelta(hours=2),
        )
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
            role="captain",
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
                "telegram": "",
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
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(days=1),
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
        self.assertContains(response, tournament.name)

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
                "official_solution": "solution",
            },
        )

        self.assertRedirects(response, reverse("edit_tournament", args=[tournament.id]))

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

        self.assertRedirects(response, reverse("admin_dashboard"))
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
            role="captain",
            is_approved=True,
            email="captain2@example.com",
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse("delete_user", args=[removable_user.id]))

        self.assertRedirects(response, reverse("admin_dashboard"))
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
        self.assertContains(response, tournament.name)

    def test_jury_can_open_tournament_detail_with_team_submissions(self):
        tournament = self.create_tournament()
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
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=3),
            registration_end=timezone.now() - timedelta(hours=2),
        )
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
            role="captain",
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
