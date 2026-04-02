from typing import Any, Dict, Iterable

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models, transaction

from users.models import CustomUser

from .models import RegistrationMember, Team, Tournament, TournamentRegistration
from .validators import validate_school_name


class RegistrationService:
    @staticmethod
    def _normalize_roster(roster: Iterable[Dict[str, Any]] | None) -> list[dict[str, str]]:
        normalized = []
        seen_emails = set()

        for item in roster or []:
            full_name = (item.get("full_name") or "").strip()
            email = (item.get("email") or "").strip().lower()

            if not full_name:
                raise ValidationError("Вкажіть ім'я учасника.")
            if not email:
                raise ValidationError("Вкажіть email учасника.")
            try:
                validate_email(email)
            except ValidationError as exc:
                raise ValidationError("Некоректний формат email учасника.") from exc
            if email in seen_emails:
                raise ValidationError("Email не повинен повторюватися в межах однієї команди.")

            seen_emails.add(email)
            normalized.append({
                "full_name": full_name,
                "email": email,
            })

        return normalized

    @staticmethod
    def _ensure_unique_tournament_emails(
        *,
        tournament: Tournament,
        team: Team,
        captain_email: str,
        roster: list[dict[str, str]],
    ) -> None:
        active_statuses = [
            TournamentRegistration.Status.PENDING,
            TournamentRegistration.Status.APPROVED,
        ]
        emails_to_check = {captain_email}
        emails_to_check.update(item["email"] for item in roster)

        conflicting_registrations = TournamentRegistration.objects.filter(
            tournament=tournament,
            status__in=active_statuses,
        ).exclude(team=team).filter(
            models.Q(team__captain_email__in=emails_to_check)
            | models.Q(members__email__in=emails_to_check)
        ).distinct()

        if conflicting_registrations.exists():
            raise ValidationError("Один email не може бути у двох командах цього турніру.")

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
            raise ValidationError("Реєстрація на турнір зараз закрита.")

        active_statuses = [
            TournamentRegistration.Status.PENDING,
            TournamentRegistration.Status.APPROVED,
        ]

        team_name = (team_data.get("name") or "").strip()
        captain_name = (team_data.get("captain_name") or "").strip()
        captain_email = (team_data.get("captain_email") or "").strip().lower()
        school = (team_data.get("school") or "").strip()
        preferred_contact_method = (team_data.get("preferred_contact_method") or "").strip()
        preferred_contact_value = (team_data.get("preferred_contact_value") or "").strip()
        telegram = preferred_contact_value if preferred_contact_method == Team.ContactMethod.TELEGRAM else ""
        discord = preferred_contact_value if preferred_contact_method == Team.ContactMethod.DISCORD else ""
        viber = preferred_contact_value if preferred_contact_method == Team.ContactMethod.VIBER else ""

        if not team_name:
            raise ValidationError("Вкажіть назву команди.")
        if not captain_name:
            raise ValidationError("Вкажіть ім'я контактної особи.")
        if not captain_email:
            raise ValidationError("Вкажіть email контактної особи.")
        if not preferred_contact_method:
            raise ValidationError("Вкажіть зручний спосіб зв'язку.")
        if not preferred_contact_value:
            raise ValidationError("Вкажіть контакт для зв'язку.")
        school = validate_school_name(school)
        try:
            validate_email(captain_email)
        except ValidationError as exc:
            raise ValidationError("Некоректний формат email контактної особи.") from exc

        normalized_roster = RegistrationService._normalize_roster(roster)
        if captain_email in {item["email"] for item in normalized_roster}:
            raise ValidationError("Email контактної особи не може дублюватися серед учасників.")

        if team is None:
            team = Team.objects.create(
                captain_user=captain_user,
                name=team_name,
                captain_name=captain_name,
                captain_email=captain_email,
                school=school or None,
                preferred_contact_method=preferred_contact_method or None,
                preferred_contact_value=preferred_contact_value or None,
                telegram=telegram or None,
                discord=discord or None,
                viber=viber or None,
            )
        else:
            team.name = team_name
            team.captain_name = captain_name
            team.captain_email = captain_email
            team.school = school or None
            team.preferred_contact_method = preferred_contact_method or None
            team.preferred_contact_value = preferred_contact_value or None
            team.telegram = telegram or None
            team.discord = discord or None
            team.viber = viber or None
            team.save(update_fields=[
                "name",
                "captain_name",
                "captain_email",
                "school",
                "preferred_contact_method",
                "preferred_contact_value",
                "telegram",
                "discord",
                "viber",
            ])

        if TournamentRegistration.objects.filter(
            tournament=tournament,
            team=team,
            status__in=active_statuses,
        ).exists():
            raise ValidationError("Команда вже має активну заявку на цей турнір.")

        if (
            tournament.max_teams
            and TournamentRegistration.objects.filter(
                tournament=tournament,
                status__in=active_statuses,
            ).count()
            >= tournament.max_teams
        ):
            raise ValidationError("Ліміт команд для цього турніру вже вичерпано.")

        members_count = 1 + len(normalized_roster)
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

        RegistrationService._ensure_unique_tournament_emails(
            tournament=tournament,
            team=team,
            captain_email=captain_email,
            roster=normalized_roster,
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
