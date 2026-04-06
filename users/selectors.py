from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from tournament.models import (
    Announcement,
    Certificate,
    Submission,
    Task,
    Team,
    Tournament,
    TournamentRegistration,
)

from .models import CustomUser
from .policies import is_participant_user


def get_primary_team_with_quick_overview(user):
    if not getattr(user, "is_authenticated", False):
        return None, None

    teams = (
        Team.objects.filter(Q(captain_user=user) | Q(participants__email=user.email))
        .select_related("captain_user")
        .prefetch_related("participants", "registrations__tournament")
        .distinct()
        .order_by("name")
    )

    fallback_team = None
    fallback_overview = None
    for team in teams:
        overview = build_team_quick_overview(team)
        if fallback_team is None:
            fallback_team = team
            fallback_overview = overview
        if overview is not None:
            return team, overview

    return fallback_team, fallback_overview


def build_public_announcements():
    return Announcement.objects.select_related("created_by", "tournament").order_by("-created_at")[:5]


def build_user_announcements_queryset():
    return Announcement.objects.select_related("created_by", "tournament").order_by("-created_at")


def build_user_certificates_queryset(user):
    return (
        Certificate.objects.filter(Q(recipient_user=user) | Q(recipient_email__iexact=user.email))
        .select_related("tournament", "team", "issued_by", "recipient_user")
        .distinct()
        .order_by("-issued_at")
    )


def build_user_message_items(user):
    items = []
    seen_keys = set()
    now = timezone.now()
    kind_labels = {
        "announcement": "Оголошення",
        "status": "Статус",
        "event": "Подія",
        "deadline": "Дедлайн",
        "finished": "Завершено",
        "system": "Система",
    }

    def add_item(*, key, title, body, created_at, kind="system", tournament=None):
        if created_at is None or created_at > now or key in seen_keys:
            return
        seen_keys.add(key)
        items.append(
            {
                "key": key,
                "title": title,
                "body": body,
                "created_at": created_at,
                "kind": kind,
                "kind_label": kind_labels.get(kind, "Система"),
                "tournament": tournament,
            }
        )

    for announcement in build_user_announcements_queryset():
        add_item(
            key=f"announcement:{announcement.id}",
            title=announcement.title,
            body=announcement.message,
            created_at=announcement.created_at,
            kind="announcement",
            tournament=announcement.tournament,
        )

    if getattr(user, "is_authenticated", False):
        public_tournaments = Tournament.objects.filter(is_draft=False).order_by("-registration_start", "-start_date")
        for tournament in public_tournaments:
            if tournament.registration_start is not None:
                add_item(
                    key=f"registration-open:{tournament.id}",
                    title=f"Старт реєстрації: {tournament.name}",
                    body="Реєстрацію на турнір відкрито. Можна подавати заявки команди.",
                    created_at=tournament.registration_start,
                    kind="event",
                    tournament=tournament,
                )

    if getattr(user, "is_authenticated", False) and is_participant_user(user):
        registrations = (
            TournamentRegistration.objects.select_related("tournament", "team")
            .prefetch_related("members")
            .filter(Q(team__captain_user=user) | Q(members__user=user))
            .distinct()
        )
        for registration in registrations:
            tournament = registration.tournament
            add_item(
                key=f"registration:{registration.id}:{registration.status}",
                title=f"Статус заявки: {tournament.name}",
                body=f"Заявка команди {registration.team.name} має статус «{registration.get_status_display()}».",
                created_at=registration.created_at,
                kind="status",
                tournament=tournament,
            )
            if registration.status == TournamentRegistration.Status.APPROVED:
                if tournament.start_date is not None:
                    add_item(
                        key=f"start:{tournament.id}",
                        title=f"Старт завдань: {tournament.name}",
                        body="Завдання турніру вже доступні. Перевірте умови, дедлайни та подайте сабміти вчасно.",
                        created_at=tournament.start_date,
                        kind="event",
                        tournament=tournament,
                    )
                if tournament.end_date is not None:
                    deadline_24h = tournament.end_date - timedelta(hours=24)
                    if deadline_24h <= now:
                        add_item(
                            key=f"deadline:{tournament.id}",
                            title=f"24 години до дедлайну: {tournament.name}",
                            body="До завершення турніру залишилася доба. Перевірте, чи всі сабміти подані.",
                            created_at=deadline_24h,
                            kind="deadline",
                            tournament=tournament,
                        )
                if tournament.is_finished:
                    add_item(
                        key=f"finished:{tournament.id}",
                        title=f"Сабміти закрито: {tournament.name}",
                        body="Турнір завершено. Прийом робіт закрито, офіційні відповіді вже доступні, а підсумковий рейтинг відкриється після завершення оцінювання.",
                        created_at=tournament.end_date,
                        kind="finished",
                        tournament=tournament,
                    )
                    if tournament.evaluation_results_ready:
                        add_item(
                            key=f"evaluation-finished:{tournament.id}",
                            title=f"Оцінювання завершено: {tournament.name}",
                            body="Підсумковий лідерборд і результати команд уже доступні.",
                            created_at=tournament.evaluation_finished_at or tournament.end_date,
                            kind="system",
                            tournament=tournament,
                        )

    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items


def build_notification_nav_context(user):
    if not getattr(user, "is_authenticated", False):
        return {
            "has_unread_announcements": False,
            "has_unread_certificates": False,
            "unread_announcements_count": 0,
            "unread_certificates_count": 0,
        }

    messages_seen_at = user.announcements_seen_at
    certificates_seen_at = user.certificates_seen_at

    message_items = build_user_message_items(user)
    certificates_qs = build_user_certificates_queryset(user)

    unread_messages_count = sum(
        1 for item in message_items if messages_seen_at is None or item["created_at"] > messages_seen_at
    )

    unread_certificates_qs = certificates_qs
    if certificates_seen_at is not None:
        unread_certificates_qs = unread_certificates_qs.filter(issued_at__gt=certificates_seen_at)

    return {
        "has_unread_announcements": unread_messages_count > 0,
        "has_unread_certificates": unread_certificates_qs.exists(),
        "unread_announcements_count": unread_messages_count,
        "unread_certificates_count": unread_certificates_qs.count(),
    }


def build_team_quick_overview(team):
    active_registration = (
        team.registrations.select_related("tournament")
        .filter(status=TournamentRegistration.Status.APPROVED)
        .order_by("tournament__start_date")
        .first()
    )
    if active_registration is None:
        return None

    tournament = active_registration.tournament
    tasks = list(Task.objects.filter(tournament=tournament, is_draft=False).order_by("title"))
    submissions = list(
        Submission.objects.filter(team=team, task__tournament=tournament)
        .select_related("task")
        .order_by("-submitted_at")
    )
    submission_by_task_id = {submission.task_id: submission for submission in submissions}
    next_task = next((task for task in tasks if task.id not in submission_by_task_id), tasks[0] if tasks else None)
    latest_submission = submissions[0] if submissions else None

    return {
        "tournament": tournament,
        "registration": active_registration,
        "next_task": next_task,
        "latest_submission": latest_submission,
        "tasks_total": len(tasks),
        "submitted_total": len(submissions),
    }


def collect_registration_recipients(registration):
    recipients = []
    seen_emails = set()

    def add_recipient(*, user=None, name="", email=""):
        normalized_email = (email or "").strip().lower()
        if not normalized_email or normalized_email in seen_emails:
            return
        seen_emails.add(normalized_email)
        recipients.append(
            {
                "user": user,
                "name": (name or normalized_email).strip(),
                "email": normalized_email,
            }
        )

    add_recipient(
        user=registration.team.captain_user,
        name=registration.team.captain_name,
        email=registration.team.captain_email,
    )

    for member in registration.members.all():
        add_recipient(user=member.user, name=member.full_name, email=member.email)

    for participant in registration.team.participants.all():
        linked_user = CustomUser.objects.filter(email__iexact=participant.email).first()
        add_recipient(user=linked_user, name=participant.full_name, email=participant.email)

    return recipients
