from typing import Any, Dict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Participant, Team, Tournament


class TeamRegistrationService:
    """
    Service class responsible for registering teams for tournaments.

    This class encapsulates the application-level logic for team registration,
    keeping the ORM models focused on data structure only.
    """

    @staticmethod
    @transaction.atomic
    def register_team(tournament_id: int, team_data: Dict[str, Any]) -> Team:
        """
        Register a new team in the specified tournament.

        The method performs the following validations:
        - Tournament must be in the "registration" status.
        - Current time must be within the registration window.
        - Captain email must be unique within the tournament.
        - Team cannot register twice (same captain_email in the same tournament).
        - Participant emails must be unique within the team.
        - Minimum of 2 participants is required.

        Args:
            tournament_id: ID of the tournament.
            team_data: Dictionary with team and participants data. Expected keys:
                - name (str)
                - captain_name (str)
                - captain_email (str)
                - school (str, optional)
                - telegram (str, optional)
                - participants (list of dicts with "full_name" and "email")

        Returns:
            The created `Team` instance.

        Raises:
            Tournament.DoesNotExist: If the tournament does not exist.
            ValidationError: If any validation rule is violated.
        """
        tournament = (
            Tournament.objects.select_for_update()
            .only(
                "id",
                "status",
                "registration_start",
                "registration_end",
            )
            .get(id=tournament_id)
        )

        now = timezone.now()

        if tournament.status != Tournament.Status.REGISTRATION:
            raise ValidationError("Tournament is not open for registration.")

        if not (tournament.registration_start <= now <= tournament.registration_end):
            raise ValidationError("Registration window is closed.")

        name = (team_data.get("name") or "").strip()
        captain_name = (team_data.get("captain_name") or "").strip()
        captain_email_raw = (team_data.get("captain_email") or "").strip()
        school = (team_data.get("school") or None) or None
        telegram = (team_data.get("telegram") or None) or None
        participants_data = team_data.get("participants") or []

        if not name:
            raise ValidationError("Team name is required.")

        if not captain_name:
            raise ValidationError("Captain name is required.")

        if not captain_email_raw:
            raise ValidationError("Captain email is required.")

        if len(participants_data) < 2:
            raise ValidationError("At least two participants are required.")

        captain_email_normalized = captain_email_raw.lower()

        captain_exists = Team.objects.filter(
            tournament_id=tournament.id,
            captain_email__iexact=captain_email_normalized,
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
            raise ValidationError(
                "Participant emails must be unique within the team."
            )

        team = Team.objects.create(
            tournament=tournament,
            name=name,
            captain_name=captain_name,
            captain_email=captain_email_raw,
            school=school,
            telegram=telegram,
        )

        participants = [
            Participant(
                team=team,
                full_name=(participant["full_name"] or "").strip(),
                email=(participant["email"] or "").strip(),
            )
            for participant in participants_data
        ]

        Participant.objects.bulk_create(participants)

        return team