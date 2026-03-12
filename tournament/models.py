from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Tournament(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Чернетка")
        REGISTRATION = "registration", _("Реєстрація")
        RUNNING = "running", _("Проводиться")
        FINISHED = "finished", _("Завершено")

    name = models.CharField(
        max_length=255,
        verbose_name="Назва",
    )
    description = models.TextField(
        verbose_name="Опис",
    )
    start_date = models.DateTimeField(
        verbose_name="Дата початку",
    )
    registration_start = models.DateTimeField(
        verbose_name="Початок реєстрації",
    )
    registration_end = models.DateTimeField(
        verbose_name="Завершення реєстрації",
    )
    max_teams = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Максимальна кількість команд",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Статус",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tournaments_created",
        verbose_name="Створено користувачем",
    )

    class Meta:
        ordering = ["-start_date", "name"]
        verbose_name = "Турнір"
        verbose_name_plural = "Турніри"

    def __str__(self) -> str:
        return self.name


class Team(models.Model):
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="teams",
        verbose_name="Турнір",
    )
    name = models.CharField(
        max_length=255,
        verbose_name="Назва команди",
    )
    captain_name = models.CharField(
        max_length=255,
        verbose_name="Ім'я капітана",
    )
    captain_email = models.EmailField(
        verbose_name="Email капітана",
    )
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
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата створення",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Команда"
        verbose_name_plural = "Команди"
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "name"],
                name="unique_team_name_per_tournament",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.tournament.name})"


class Participant(models.Model):
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Команда",
    )
    full_name = models.CharField(
        max_length=255,
        verbose_name="ПІБ",
    )
    email = models.EmailField(
        verbose_name="Email",
    )

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Учасник"
        verbose_name_plural = "Учасники"

    def __str__(self) -> str:
        return self.full_name


class Task(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Чернетка")
        ACTIVE = "active", _("Активне")
        SUBMISSION_CLOSED = "submission_closed", _("Прийом рішень завершено")
        EVALUATED = "evaluated", _("Оцінено")

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="Турнір",
    )
    title = models.CharField(
        max_length=255,
        verbose_name="Назва завдання",
    )
    description = models.TextField(
        verbose_name="Опис",
    )
    requirements = models.TextField(
        verbose_name="Вимоги",
    )
    must_have = models.TextField(
        verbose_name="Обов'язково має бути",
    )
    start_time = models.DateTimeField(
        verbose_name="Час початку",
    )
    deadline = models.DateTimeField(
        verbose_name="Дедлайн",
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Статус",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tasks_created",
        verbose_name="Створено користувачем",
    )

    class Meta:
        ordering = ["start_time", "title"]
        verbose_name = "Завдання"
        verbose_name_plural = "Завдання"

    def __str__(self) -> str:
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
    github_link = models.URLField(
        verbose_name="GitHub посилання",
    )
    video_link = models.URLField(
        verbose_name="Відео посилання",
    )
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
    submitted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Час подання",
    )
    is_final = models.BooleanField(
        default=False,
        verbose_name="Фінальна версія",
    )

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

    def __str__(self) -> str:
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

    def __str__(self) -> str:
        return f"{self.jury_user} → {self.submission}"


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
    evaluated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Час оцінювання",
    )

    class Meta:
        ordering = ["-evaluated_at"]
        verbose_name = "Оцінювання"
        verbose_name_plural = "Оцінювання"

    def __str__(self) -> str:
        return f"Оцінка {self.assignment}"

    @property
    def total_score(self) -> float:
        return (
            self.score_backend
            + self.score_frontend
            + self.score_functionality
            + self.score_ux
        ) / 4.0