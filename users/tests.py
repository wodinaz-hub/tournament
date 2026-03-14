from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tournament.models import Submission, Task, Team, Tournament, TournamentRegistration


User = get_user_model()


class TournamentPlatformViewTests(TestCase):
    def setUp(self):
        self.captain = User.objects.create_user(
            username="captain",
            password="secret123",
            role="captain",
            is_approved=True,
            email="captain@example.com",
        )
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="secret123",
            email="admin@example.com",
        )
        self.client.force_login(self.captain)

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

    def test_admin_can_open_contextual_create_task_page(self):
        tournament = self.create_tournament()
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("create_tournament_task", args=[tournament.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, tournament.name)

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

        response = self.client.get(reverse("approve_registration", args=[registration.id]))

        self.assertRedirects(response, reverse("admin_dashboard"))
        registration.refresh_from_db()
        self.assertEqual(registration.status, TournamentRegistration.Status.APPROVED)

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

    def test_admin_cannot_edit_started_tournament(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=3),
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("edit_tournament", args=[tournament.id]))

        self.assertRedirects(response, reverse("admin_dashboard"))

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

    def test_admin_cannot_create_task_for_started_tournament(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=3),
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("create_tournament_task", args=[tournament.id]))

        self.assertRedirects(response, reverse("admin_dashboard"))

    def test_admin_cannot_edit_task_after_tournament_start(self):
        tournament = self.create_tournament(
            start_date=timezone.now() - timedelta(hours=1),
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
