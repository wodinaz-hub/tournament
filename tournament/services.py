from typing import Any, Dict, Iterable

from django.core.exceptions import ValidationError
from django.db import transaction

from users.models import CustomUser

from .models import RegistrationMember, Team, Tournament, TournamentRegistration


class RegistrationService:
    @staticmethod
    def _normalize_roster(roster: Iterable[Dict[str, Any]] | None) -> list[dict[str, str]]:
        normalized = []
        seen_emails = set()

        for item in roster or []:
            full_name = (item.get("full_name") or "").strip()
            email = (item.get("email") or "").strip().lower()

            if not full_name:
                raise ValidationError("Participant full name is required.")
            if not email:
                raise ValidationError("Participant email is required.")
            if email in seen_emails:
                raise ValidationError("Participant emails must be unique within the registration.")

            seen_emails.add(email)
            normalized.append({
                "full_name": full_name,
                "email": email,
            })

        return normalized

    @staticmethod
    @transaction.atomic
    def submit_registration(
        *,
        tournament: Tournament,
        registered_by: CustomUser,
        captain_user: CustomUser,
        team_data: Dict[str, Any],
        form_answers: Dict[str, Any],
        roster: Iterable[Dict[str, Any]] | None = None,
    ) -> TournamentRegistration:
        tournament = Tournament.objects.select_for_update().get(pk=tournament.pk)
        team = Team.objects.select_for_update().filter(captain_user=captain_user).first()

        if tournament.is_draft or not tournament.is_registration_open:
            raise ValidationError("Tournament is not open for registration.")

        active_statuses = [
            TournamentRegistration.Status.PENDING,
            TournamentRegistration.Status.APPROVED,
        ]

        team_name = (team_data.get("name") or "").strip()
        captain_name = (team_data.get("captain_name") or "").strip()
        captain_email = (team_data.get("captain_email") or "").strip().lower()
        school = (team_data.get("school") or "").strip()
        telegram = (team_data.get("telegram") or "").strip()

        if not team_name:
            raise ValidationError("Вкажіть назву команди.")
        if not captain_name:
            raise ValidationError("Вкажіть імʼя капітана.")
        if not captain_email:
            raise ValidationError("Вкажіть email капітана.")

        if team is None:
            team = Team.objects.create(
                captain_user=captain_user,
                name=team_name,
                captain_name=captain_name,
                captain_email=captain_email,
                school=school or None,
                telegram=telegram or None,
            )
        else:
            team.name = team_name
            team.captain_name = captain_name
            team.captain_email = captain_email
            team.school = school or None
            team.telegram = telegram or None
            team.save(update_fields=[
                "name",
                "captain_name",
                "captain_email",
                "school",
                "telegram",
            ])

        if TournamentRegistration.objects.filter(
            tournament=tournament,
            team=team,
            status__in=active_statuses,
        ).exists():
            raise ValidationError("Team already has an active registration for this tournament.")

        if (
            tournament.max_teams
            and TournamentRegistration.objects.filter(
                tournament=tournament,
                status__in=active_statuses,
            ).count()
            >= tournament.max_teams
        ):
            raise ValidationError("Tournament team limit has been reached.")

        normalized_roster = RegistrationService._normalize_roster(roster)

        members_count = 1 + len(normalized_roster) if normalized_roster else team.members_count
        if (
            tournament.min_team_members is not None
            and members_count < tournament.min_team_members
        ):
            raise ValidationError(
                f"У команді замало людей. Потрібно щонайменше: {tournament.min_team_members}."
            )
        if (
            tournament.max_team_members is not None
            and members_count > tournament.max_team_members
        ):
            raise ValidationError(
                f"У команді забагато людей. Максимум дозволено: {tournament.max_team_members}."
            )

        TournamentRegistration.objects.filter(
            tournament=tournament,
            team=team,
            status=TournamentRegistration.Status.REJECTED,
        ).delete()

        registration = TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=registered_by,
            status=TournamentRegistration.Status.PENDING,
            form_answers=form_answers,
        )

        if normalized_roster:
            RegistrationMember.objects.bulk_create([
                RegistrationMember(
                    registration=registration,
                    user=CustomUser.objects.filter(email__iexact=item["email"]).first(),
                    full_name=item["full_name"],
                    email=item["email"],
                )
                for item in normalized_roster
            ])

        return registration
