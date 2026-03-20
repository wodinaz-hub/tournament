from typing import Any, Dict

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Participant, Team, Tournament, TournamentRegistration


class TeamRegistrationService:
    @staticmethod
    @transaction.atomic
    def register_team(tournament_id: int, team_data: Dict[str, Any]) -> Team:
        tournament = (
            Tournament.objects.select_for_update()
            .only(
                "id",
                "is_draft",
                "registration_start",
                "registration_end",
            )
            .get(id=tournament_id)
        )

        if tournament.is_draft or not tournament.is_registration_open:
            raise ValidationError("Tournament is not open for registration.")

        name = (team_data.get("name") or "").strip()
        captain_name = (team_data.get("captain_name") or "").strip()
        captain_email_raw = (team_data.get("captain_email") or "").strip()
        school = (team_data.get("school") or None) or None
        telegram = (team_data.get("telegram") or None) or None
        participants_data = team_data.get("participants") or []
        registered_by = team_data.get("registered_by")
        captain_user = team_data.get("captain_user") or registered_by

        if not name:
            raise ValidationError("Team name is required.")
        if not captain_name:
            raise ValidationError("Captain name is required.")
        if not captain_email_raw:
            raise ValidationError("Captain email is required.")
        if registered_by is None:
            raise ValidationError("registered_by is required.")
        if captain_user is None:
            raise ValidationError("captain_user is required.")
        if len(participants_data) < 2:
            raise ValidationError("At least two participants are required.")
        if (
            tournament.max_teams
            and TournamentRegistration.objects.filter(
                tournament_id=tournament.id,
                status__in=[
                    TournamentRegistration.Status.PENDING,
                    TournamentRegistration.Status.APPROVED,
                ],
            ).count()
            >= tournament.max_teams
        ):
            raise ValidationError("Tournament team limit has been reached.")

        captain_exists = TournamentRegistration.objects.filter(
            tournament_id=tournament.id,
            team__captain_email__iexact=captain_email_raw.lower(),
            status__in=[
                TournamentRegistration.Status.PENDING,
                TournamentRegistration.Status.APPROVED,
            ],
        ).exists()
        if captain_exists:
            raise ValidationError(
                "A team with this captain email is already registered in this tournament."
            )

        participant_emails = []
        for participant in participants_data:
            email = (participant.get("email") or "").strip()
            full_name = (participant.get("full_name") or "").strip()
            if not full_name:
                raise ValidationError("Participant full name is required.")
            if not email:
                raise ValidationError("Participant email is required.")
            participant_emails.append(email.lower())

        if len(participant_emails) != len(set(participant_emails)):
            raise ValidationError("Participant emails must be unique within the team.")

        team = Team.objects.create(
            captain_user=captain_user,
            name=name,
            captain_name=captain_name,
            captain_email=captain_email_raw,
            school=school,
            telegram=telegram,
        )

        TournamentRegistration.objects.create(
            tournament=tournament,
            team=team,
            registered_by=registered_by,
        )

        Participant.objects.bulk_create(
            [
                Participant(
                    team=team,
                    full_name=(participant["full_name"] or "").strip(),
                    email=(participant["email"] or "").strip(),
                )
                for participant in participants_data
            ]
        )

        return team
