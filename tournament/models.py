from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Tournament(models.Model):
    name = models.CharField(max_length=255, verbose_name="Назва")
    description = models.TextField(verbose_name="Опис")
    registration_form_description = models.TextField(
        blank=True,
        default="",
        verbose_name="Опис форми реєстрації команди",
    )
    registration_fields_config = models.JSONField(
        blank=True,
        default=list,
        verbose_name="Поля форми реєстрації",
    )
    start_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата початку")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата завершення")
    registration_start = models.DateTimeField(null=True, blank=True, verbose_name="Початок реєстрації")
    registration_end = models.DateTimeField(null=True, blank=True, verbose_name="Завершення реєстрації")
    max_teams = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Максимальна кількість команд",
    )
    min_team_members = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Мінімальна кількість людей у команді",
    )
    max_team_members = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Максимальна кількість людей у команді",
    )
    is_draft = models.BooleanField(default=True, verbose_name="Чернетка")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tournaments_created",
        verbose_name="Створено користувачем",
    )
    jury_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="jury_tournaments",
        verbose_name="Призначене журі",
    )

    class Meta:
        ordering = ["-start_date", "name"]
        verbose_name = "Турнір"
        verbose_name_plural = "Турніри"

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
            "draft": "Чернетка",
            "registration": "Реєстрація",
            "running": "Йде",
            "finished": "Завершено",
            "scheduled": "Очікує старту",
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
        verbose_name="Користувач-капітан",
    )
    name = models.CharField(max_length=255, verbose_name="Назва команди")
    captain_name = models.CharField(max_length=255, verbose_name="Ім'я капітана")
    captain_email = models.EmailField(verbose_name="Email капітана")
    school = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Школа",
    )
    telegram = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Telegram",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")

    class Meta:
        ordering = ["name"]
        verbose_name = "Команда"
        verbose_name_plural = "Команди"

    def __str__(self):
        return self.name

    @property
    def members_count(self):
        return 1 + self.participants.count()


class TournamentRegistration(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Очікує"
        APPROVED = "approved", "Схвалено"
        REJECTED = "rejected", "Відхилено"

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="registrations",
        verbose_name="Турнір",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="registrations",
        verbose_name="Команда",
    )
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tournament_registrations",
        verbose_name="Зареєстровано користувачем",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Статус заявки",
    )
    form_answers = models.JSONField(
        blank=True,
        default=dict,
        verbose_name="Відповіді на поля форми",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата реєстрації")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Реєстрація команди на турнір"
        verbose_name_plural = "Реєстрації команд на турніри"
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
        verbose_name="Команда",
    )
    full_name = models.CharField(max_length=255, verbose_name="ПІБ")
    email = models.EmailField(verbose_name="Email")

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Учасник"
        verbose_name_plural = "Учасники"

    def __str__(self):
        return self.full_name


class Task(models.Model):
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="Турнір",
    )
    title = models.CharField(max_length=255, verbose_name="Назва завдання")
    description = models.TextField(verbose_name="Опис")
    requirements = models.TextField(verbose_name="Вимоги")
    must_have = models.TextField(verbose_name="Обов'язково має бути")
    official_solution = models.TextField(
        null=True,
        blank=True,
        verbose_name="Офіційна відповідь / розбір",
    )
    is_draft = models.BooleanField(default=True, verbose_name="Чернетка")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tasks_created",
        verbose_name="Створено користувачем",
    )

    class Meta:
        ordering = ["title"]
        verbose_name = "Завдання"
        verbose_name_plural = "Завдання"

    def __str__(self):
        return f"{self.title} ({self.tournament.name})"


class Submission(models.Model):
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Команда",
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Завдання",
    )
    github_link = models.URLField(verbose_name="GitHub посилання")
    video_link = models.URLField(verbose_name="Відео посилання")
    live_demo = models.URLField(
        null=True,
        blank=True,
        verbose_name="Live demo посилання",
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="Опис рішення",
    )
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="Час подання")
    is_final = models.BooleanField(default=False, verbose_name="Фінальна версія")

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Надіслана робота"
        verbose_name_plural = "Надіслані роботи"
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
        verbose_name="Член журі",
    )
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="jury_assignments",
        verbose_name="Робота",
    )

    class Meta:
        ordering = ["jury_user", "submission"]
        verbose_name = "Призначення журі"
        verbose_name_plural = "Призначення журі"
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
        verbose_name="Призначення журі",
    )
    score_backend = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Оцінка backend",
    )
    score_frontend = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Оцінка frontend",
    )
    score_functionality = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Оцінка функціональності",
    )
    score_ux = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Оцінка UX",
    )
    comment = models.TextField(
        null=True,
        blank=True,
        verbose_name="Коментар",
    )
    evaluated_at = models.DateTimeField(auto_now_add=True, verbose_name="Час оцінювання")

    class Meta:
        ordering = ["-evaluated_at"]
        verbose_name = "Оцінювання"
        verbose_name_plural = "Оцінювання"

    def __str__(self):
        return f"Оцінка {self.assignment}"

    @property
    def total_score(self):
        return (
            self.score_backend
            + self.score_frontend
            + self.score_functionality
            + self.score_ux
        ) / 4.0
