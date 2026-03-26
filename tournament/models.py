from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Tournament(models.Model):
    name = models.CharField(max_length=255, verbose_name="РќР°Р·РІР°")
    description = models.TextField(verbose_name="РћРїРёСЃ")
    registration_form_description = models.TextField(
        blank=True,
        default="",
        verbose_name="РћРїРёСЃ С„РѕСЂРјРё СЂРµС”СЃС‚СЂР°С†С–С— РєРѕРјР°РЅРґРё",
    )
    registration_fields_config = models.JSONField(
        blank=True,
        default=list,
        verbose_name="РџРѕР»СЏ С„РѕСЂРјРё СЂРµС”СЃС‚СЂР°С†С–С—",
    )
    start_date = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Р”Р°С‚Р° РїРѕС‡Р°С‚РєСѓ")
    end_date = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Р”Р°С‚Р° Р·Р°РІРµСЂС€РµРЅРЅСЏ")
    registration_start = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="РџРѕС‡Р°С‚РѕРє СЂРµС”СЃС‚СЂР°С†С–С—")
    registration_end = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Р—Р°РІРµСЂС€РµРЅРЅСЏ СЂРµС”СЃС‚СЂР°С†С–С—")
    max_teams = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="РњР°РєСЃРёРјР°Р»СЊРЅР° РєС–Р»СЊРєС–СЃС‚СЊ РєРѕРјР°РЅРґ",
    )
    min_team_members = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="РњС–РЅС–РјР°Р»СЊРЅР° РєС–Р»СЊРєС–СЃС‚СЊ Р»СЋРґРµР№ Сѓ РєРѕРјР°РЅРґС–",
    )
    max_team_members = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="РњР°РєСЃРёРјР°Р»СЊРЅР° РєС–Р»СЊРєС–СЃС‚СЊ Р»СЋРґРµР№ Сѓ РєРѕРјР°РЅРґС–",
    )
    is_draft = models.BooleanField(default=True, db_index=True, verbose_name="Р§РµСЂРЅРµС‚РєР°")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tournaments_created",
        verbose_name="РЎС‚РІРѕСЂРµРЅРѕ РєРѕСЂРёСЃС‚СѓРІР°С‡РµРј",
    )
    jury_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="jury_tournaments",
        verbose_name="РџСЂРёР·РЅР°С‡РµРЅРµ Р¶СѓСЂС–",
    )


    class Meta:
        ordering = ["-start_date", "name"]
        verbose_name = "РўСѓСЂРЅС–СЂ"
        verbose_name_plural = "РўСѓСЂРЅС–СЂРё"

    def __str__(self):
        return self.name

    @property
    def lifecycle_status(self):
        now = timezone.now()
        if self.is_draft:
            return "draft"
        if not self.start_date or not self.end_date:
            return "scheduled"
        if now > self.end_date:
            return "finished"
        if (
            self.registration_start
            and self.registration_end
            and self.registration_start <= now <= self.registration_end
        ):
            return "registration"
        if self.start_date <= now <= self.end_date:
            return "running"
        return "scheduled"

    @property
    def lifecycle_status_label(self):
        labels = {
            "draft": "Р§РµСЂРЅРµС‚РєР°",
            "registration": "Р РµС”СЃС‚СЂР°С†С–СЏ",
            "running": "Р™РґРµ",
            "finished": "Р—Р°РІРµСЂС€РµРЅРѕ",
            "scheduled": "РћС‡С–РєСѓС” СЃС‚Р°СЂС‚Сѓ",
        }
        return labels[self.lifecycle_status]

    @property
    def is_registration_open(self):
        now = timezone.now()
        return (
            not self.is_draft
            and self.registration_start is not None
            and self.registration_end is not None
            and self.registration_start <= now <= self.registration_end
        )

    @property
    def is_running(self):
        now = timezone.now()
        return (
            not self.is_draft
            and self.start_date is not None
            and self.end_date is not None
            and self.start_date <= now <= self.end_date
        )

    @property
    def is_finished(self):
        return self.end_date is not None and timezone.now() > self.end_date


class Team(models.Model):
    captain_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="captain_teams",
        verbose_name="РљРѕСЂРёСЃС‚СѓРІР°С‡-РєР°РїС–С‚Р°РЅ",
    )
    name = models.CharField(max_length=255, verbose_name="РќР°Р·РІР° РєРѕРјР°РЅРґРё")
    captain_name = models.CharField(max_length=255, verbose_name="Р†Рј'СЏ РєР°РїС–С‚Р°РЅР°")
    captain_email = models.EmailField(verbose_name="Email РєР°РїС–С‚Р°РЅР°")
    school = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="РЁРєРѕР»Р°",
    )
    telegram = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Телеграм",
    )
    discord = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Діскорд",
    )
    viber = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Вайбер",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Р”Р°С‚Р° СЃС‚РІРѕСЂРµРЅРЅСЏ")

    class Meta:
        ordering = ["name"]
        verbose_name = "РљРѕРјР°РЅРґР°"
        verbose_name_plural = "РљРѕРјР°РЅРґРё"

    def __str__(self):
        return self.name

    @property
    def members_count(self):
        return 1 + self.participants.count()


class TournamentRegistration(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "РћС‡С–РєСѓС”"
        APPROVED = "approved", "РЎС…РІР°Р»РµРЅРѕ"
        REJECTED = "rejected", "Р’С–РґС…РёР»РµРЅРѕ"

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="registrations",
        verbose_name="РўСѓСЂРЅС–СЂ",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="registrations",
        verbose_name="РљРѕРјР°РЅРґР°",
    )
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tournament_registrations",
        verbose_name="Р—Р°СЂРµС”СЃС‚СЂРѕРІР°РЅРѕ РєРѕСЂРёСЃС‚СѓРІР°С‡РµРј",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="РЎС‚Р°С‚СѓСЃ Р·Р°СЏРІРєРё",
    )
    form_answers = models.JSONField(
        blank=True,
        default=dict,
        verbose_name="Р’С–РґРїРѕРІС–РґС– РЅР° РїРѕР»СЏ С„РѕСЂРјРё",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Р”Р°С‚Р° СЂРµС”СЃС‚СЂР°С†С–С—")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Р РµС”СЃС‚СЂР°С†С–СЏ РєРѕРјР°РЅРґРё РЅР° С‚СѓСЂРЅС–СЂ"
        verbose_name_plural = "Р РµС”СЃС‚СЂР°С†С–С— РєРѕРјР°РЅРґ РЅР° С‚СѓСЂРЅС–СЂРё"
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "team"],
                name="unique_team_per_tournament",
            )
        ]

    def __str__(self):
        return f"{self.team.name} -> {self.tournament.name}"


class Participant(models.Model):
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="РљРѕРјР°РЅРґР°",
    )
    full_name = models.CharField(max_length=255, verbose_name="РџР†Р‘")
    email = models.EmailField(verbose_name="Email")

    class Meta:
        ordering = ["full_name"]
        verbose_name = "РЈС‡Р°СЃРЅРёРє"
        verbose_name_plural = "РЈС‡Р°СЃРЅРёРєРё"
        constraints = [
            models.UniqueConstraint(
                fields=["team", "email"],
                name="unique_participant_email_per_team",
            )
        ]

    def __str__(self):
        return self.full_name


class Task(models.Model):
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="РўСѓСЂРЅС–СЂ",
    )
    title = models.CharField(max_length=255, verbose_name="РќР°Р·РІР° Р·Р°РІРґР°РЅРЅСЏ")
    description = models.TextField(verbose_name="РћРїРёСЃ")
    requirements = models.TextField(verbose_name="Р’РёРјРѕРіРё")
    must_have = models.TextField(verbose_name="РћР±РѕРІ'СЏР·РєРѕРІРѕ РјР°С” Р±СѓС‚Рё")
    official_solution = models.TextField(
        null=True,
        blank=True,
        verbose_name="РћС„С–С†С–Р№РЅР° РІС–РґРїРѕРІС–РґСЊ / СЂРѕР·Р±С–СЂ",
    )
    is_draft = models.BooleanField(default=True, verbose_name="Р§РµСЂРЅРµС‚РєР°")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tasks_created",
        verbose_name="РЎС‚РІРѕСЂРµРЅРѕ РєРѕСЂРёСЃС‚СѓРІР°С‡РµРј",
    )

    class Meta:
        ordering = ["title"]
        verbose_name = "Р—Р°РІРґР°РЅРЅСЏ"
        verbose_name_plural = "Р—Р°РІРґР°РЅРЅСЏ"

    def __str__(self):
        return f"{self.title} ({self.tournament.name})"


class Submission(models.Model):
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="РљРѕРјР°РЅРґР°",
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Р—Р°РІРґР°РЅРЅСЏ",
    )
    github_link = models.URLField(verbose_name="GitHub РїРѕСЃРёР»Р°РЅРЅСЏ")
    video_link = models.URLField(verbose_name="Р’С–РґРµРѕ РїРѕСЃРёР»Р°РЅРЅСЏ")
    live_demo = models.URLField(
        null=True,
        blank=True,
        verbose_name="Демо РїРѕСЃРёР»Р°РЅРЅСЏ",
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="РћРїРёСЃ СЂС–С€РµРЅРЅСЏ",
    )
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="Р§Р°СЃ РїРѕРґР°РЅРЅСЏ")
    is_final = models.BooleanField(default=False, verbose_name="Р¤С–РЅР°Р»СЊРЅР° РІРµСЂСЃС–СЏ")

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "РќР°РґС–СЃР»Р°РЅР° СЂРѕР±РѕС‚Р°"
        verbose_name_plural = "РќР°РґС–СЃР»Р°РЅС– СЂРѕР±РѕС‚Рё"
        constraints = [
            models.UniqueConstraint(
                fields=["team", "task"],
                name="unique_submission_per_team_task",
            )
        ]

    def __str__(self):
        return f"{self.team.name} - {self.task.title}"


class JuryAssignment(models.Model):
    jury_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="jury_assignments",
        verbose_name="Р§Р»РµРЅ Р¶СѓСЂС–",
    )
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="jury_assignments",
        verbose_name="Р РѕР±РѕС‚Р°",
    )

    class Meta:
        ordering = ["jury_user", "submission"]
        verbose_name = "РџСЂРёР·РЅР°С‡РµРЅРЅСЏ Р¶СѓСЂС–"
        verbose_name_plural = "РџСЂРёР·РЅР°С‡РµРЅРЅСЏ Р¶СѓСЂС–"
        constraints = [
            models.UniqueConstraint(
                fields=["jury_user", "submission"],
                name="unique_jury_per_submission",
            )
        ]

    def __str__(self):
        return f"{self.jury_user} -> {self.submission}"


class Evaluation(models.Model):
    assignment = models.OneToOneField(
        JuryAssignment,
        on_delete=models.CASCADE,
        related_name="evaluation",
        verbose_name="РџСЂРёР·РЅР°С‡РµРЅРЅСЏ Р¶СѓСЂС–",
    )
    score_backend = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="РћС†С–РЅРєР° backend",
    )
    score_frontend = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="РћС†С–РЅРєР° frontend",
    )
    score_functionality = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="РћС†С–РЅРєР° С„СѓРЅРєС†С–РѕРЅР°Р»СЊРЅРѕСЃС‚С–",
    )
    score_ux = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="РћС†С–РЅРєР° UX",
    )
    comment = models.TextField(
        null=True,
        blank=True,
        verbose_name="РљРѕРјРµРЅС‚Р°СЂ",
    )
    evaluated_at = models.DateTimeField(auto_now_add=True, verbose_name="Р§Р°СЃ РѕС†С–РЅСЋРІР°РЅРЅСЏ")

    class Meta:
        ordering = ["-evaluated_at"]
        verbose_name = "РћС†С–РЅСЋРІР°РЅРЅСЏ"
        verbose_name_plural = "РћС†С–РЅСЋРІР°РЅРЅСЏ"

    def __str__(self):
        return f"РћС†С–РЅРєР° {self.assignment}"

    @property
    def total_score(self):
        return (
            self.score_backend
            + self.score_frontend
            + self.score_functionality
            + self.score_ux
        ) / 4.0


class RegistrationMember(models.Model):
    registration = models.ForeignKey(
        TournamentRegistration,
        on_delete=models.CASCADE,
        related_name="members",
        verbose_name="Р—Р°СЏРІРєР°",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registration_memberships",
        verbose_name="РџРѕРІ'СЏР·Р°РЅРёР№ РєРѕСЂРёСЃС‚СѓРІР°С‡",
    )
    full_name = models.CharField(max_length=255, verbose_name="РџР†Р‘")
    email = models.EmailField(verbose_name="Email")

    class Meta:
        ordering = ["full_name"]
        verbose_name = "РЈС‡Р°СЃРЅРёРє Р·Р°СЏРІРєРё"
        verbose_name_plural = "РЈС‡Р°СЃРЅРёРєРё Р·Р°СЏРІРѕРє"
        constraints = [
            models.UniqueConstraint(
                fields=["registration", "email"],
                name="unique_registration_member_email",
            )
        ]

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class Announcement(models.Model):
    title = models.CharField(max_length=255, verbose_name="Р—Р°РіРѕР»РѕРІРѕРє")
    message = models.TextField(verbose_name="РўРµРєСЃС‚ РѕРіРѕР»РѕС€РµРЅРЅСЏ")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="announcements_created",
        verbose_name="РЎС‚РІРѕСЂРµРЅРѕ РєРѕСЂРёСЃС‚СѓРІР°С‡РµРј",
    )
    tournament = models.ForeignKey(
        Tournament,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="announcements",
        verbose_name="РўСѓСЂРЅС–СЂ",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Р”Р°С‚Р° СЃС‚РІРѕСЂРµРЅРЅСЏ")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "РћРіРѕР»РѕС€РµРЅРЅСЏ"
        verbose_name_plural = "РћРіРѕР»РѕС€РµРЅРЅСЏ"

    def __str__(self):
        return self.title


class Certificate(models.Model):
    class CertificateType(models.TextChoices):
        PARTICIPANT = "participant", "РЈС‡Р°СЃРЅРёРє"
        WINNER = "winner", "РџРµСЂРµРјРѕР¶РµС†СЊ"

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="certificates",
        verbose_name="РўСѓСЂРЅС–СЂ",
    )
    team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="certificates",
        verbose_name="РљРѕРјР°РЅРґР°",
    )
    certificate_type = models.CharField(
        max_length=20,
        choices=CertificateType.choices,
        db_index=True,
        verbose_name="РўРёРї СЃРµСЂС‚РёС„С–РєР°С‚Р°",
    )
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="certificates_received",
        verbose_name="РљРѕСЂРёСЃС‚СѓРІР°С‡-РѕС‚СЂРёРјСѓРІР°С‡",
    )
    recipient_name = models.CharField(max_length=255, verbose_name="Р†Рј'СЏ РѕС‚СЂРёРјСѓРІР°С‡Р°")
    recipient_email = models.EmailField(verbose_name="Email РѕС‚СЂРёРјСѓРІР°С‡Р°")
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="certificates_issued",
        verbose_name="Р’РёРґР°РІ РєРѕСЂРёСЃС‚СѓРІР°С‡",
    )
    issued_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Р”Р°С‚Р° РІРёРґР°С‡С–")

    class Meta:
        ordering = ["-issued_at"]
        verbose_name = "РЎРµСЂС‚РёС„С–РєР°С‚"
        verbose_name_plural = "РЎРµСЂС‚РёС„С–РєР°С‚Рё"
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "certificate_type", "recipient_email"],
                name="unique_certificate_per_tournament_type_email",
            )
        ]

    def __str__(self):
        return f"{self.get_certificate_type_display()}: {self.recipient_name}"


class CertificateTemplate(models.Model):
    tournament = models.ForeignKey(
        Tournament,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="certificate_templates",
        verbose_name="РўСѓСЂРЅС–СЂ",
    )
    certificate_type = models.CharField(
        max_length=20,
        choices=Certificate.CertificateType.choices,
        db_index=True,
        verbose_name="РўРёРї СЃРµСЂС‚РёС„С–РєР°С‚Р°",
    )
    background_image = models.ImageField(
        upload_to="certificate_templates/",
        verbose_name="РЁР°Р±Р»РѕРЅ СЃРµСЂС‚РёС„С–РєР°С‚Р°",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_certificate_templates",
        verbose_name="Р—Р°РІР°РЅС‚Р°Р¶РёРІ РєРѕСЂРёСЃС‚СѓРІР°С‡",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Р”Р°С‚Р° Р·Р°РІР°РЅС‚Р°Р¶РµРЅРЅСЏ")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "РЁР°Р±Р»РѕРЅ СЃРµСЂС‚РёС„С–РєР°С‚Р°"
        verbose_name_plural = "РЁР°Р±Р»РѕРЅРё СЃРµСЂС‚РёС„С–РєР°С‚С–РІ"

    def __str__(self):
        scope = self.tournament.name if self.tournament_id else "Р“Р»РѕР±Р°Р»СЊРЅРёР№"
        return f"{scope}: {self.get_certificate_type_display()}"



