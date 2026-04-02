from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Tournament(models.Model):
    DEFAULT_CONTACT_METHODS = ["telegram", "discord", "viber"]

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
    allowed_contact_methods = models.JSONField(
        blank=True,
        default=list,
        verbose_name="Доступні способи зв'язку для команди",
    )
    start_date = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Дата початку")
    end_date = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Дата завершення")
    registration_start = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Початок реєстрації")
    registration_end = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Завершення реєстрації")
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
    is_draft = models.BooleanField(default=True, db_index=True, verbose_name="Чернетка")
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
    evaluation_finished_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Оцінювання завершено",
    )
    evaluation_finished_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tournaments_evaluation_finished",
        verbose_name="Оцінювання завершив",
    )


    class Meta:
        ordering = ["-start_date", "name"]
        verbose_name = "Турнір"
        verbose_name_plural = "Турніри"

    def __str__(self):
        return self.name

    @property
    def effective_allowed_contact_methods(self):
        methods = self.allowed_contact_methods or self.DEFAULT_CONTACT_METHODS
        valid_values = {choice[0] for choice in Team.ContactMethod.choices}
        filtered_methods = [method for method in methods if method in valid_values]
        return filtered_methods or self.DEFAULT_CONTACT_METHODS

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

    @property
    def all_submissions_evaluated(self):
        submission_ids = list(
            Submission.objects.filter(
                task__tournament=self,
            ).values_list('id', flat=True).distinct()
        )
        if not submission_ids:
            return False

        evaluated_submission_ids = set(
            Evaluation.objects.filter(
                assignment__submission_id__in=submission_ids,
            ).values_list('assignment__submission_id', flat=True).distinct()
        )
        return len(evaluated_submission_ids) == len(set(submission_ids))

    @property
    def evaluation_results_ready(self):
        return (
            self.is_finished
            and (
                self.evaluation_finished_at is not None
                or self.all_submissions_evaluated
            )
        )

    @property
    def evaluation_status_label(self):
        if self.evaluation_results_ready:
            return "Оцінювання завершено"
        if self.is_finished:
            return "Оцінювання триває"
        return "Оцінювання ще не завершено"


class TournamentScheduleItem(models.Model):
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="schedule_items",
        verbose_name="Турнір",
    )
    title = models.CharField(max_length=255, verbose_name="Назва події")
    starts_at = models.DateTimeField(db_index=True, verbose_name="Дата та час")
    description = models.TextField(blank=True, default="", verbose_name="Опис події")
    position = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ["starts_at", "position", "id"]
        verbose_name = "Подія розкладу турніру"
        verbose_name_plural = "Події розкладу турніру"

    def __str__(self):
        return f"{self.title} ({self.tournament.name})"


class Team(models.Model):
    class ContactMethod(models.TextChoices):
        TELEGRAM = "telegram", "Телеграм"
        DISCORD = "discord", "Діскорд"
        VIBER = "viber", "Вайбер"

    captain_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="captain_teams",
        verbose_name="Прив'язаний користувач",
    )
    name = models.CharField(max_length=255, verbose_name="Назва команди")
    captain_name = models.CharField(max_length=255, verbose_name="Ім'я контактної особи")
    captain_email = models.EmailField(verbose_name="Email контактної особи")
    school = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Школа",
    )
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=ContactMethod.choices,
        null=True,
        blank=True,
        verbose_name="Спосіб зв'язку",
    )
    preferred_contact_value = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Контакт для зв'язку",
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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")

    class Meta:
        ordering = ["name"]
        verbose_name = "Команда"
        verbose_name_plural = "Команди"

    def __str__(self):
        return self.name

    @property
    def effective_allowed_contact_methods(self):
        methods = self.allowed_contact_methods or self.DEFAULT_CONTACT_METHODS
        valid_values = {choice[0] for choice in Team.ContactMethod.choices}
        filtered_methods = [method for method in methods if method in valid_values]
        return filtered_methods or self.DEFAULT_CONTACT_METHODS

    @property
    def members_count(self):
        return 1 + self.participants.count()

    @property
    def effective_contact_method(self):
        if self.preferred_contact_method and self.preferred_contact_value:
            return self.preferred_contact_method
        for method_name in (
            self.ContactMethod.TELEGRAM,
            self.ContactMethod.DISCORD,
            self.ContactMethod.VIBER,
        ):
            if getattr(self, method_name, None):
                return method_name
        return ""

    @property
    def effective_contact_value(self):
        if self.preferred_contact_method and self.preferred_contact_value:
            return self.preferred_contact_value
        method_name = self.effective_contact_method
        return getattr(self, method_name, "") if method_name else ""

    @property
    def effective_contact_label(self):
        method_name = self.effective_contact_method
        if not method_name:
            return ""
        return self.ContactMethod(method_name).label


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
        db_index=True,
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
        verbose_name="Турнір",
    )
    title = models.CharField(max_length=255, verbose_name="Назва завдання")
    description = models.TextField(verbose_name="Опис")
    requirements = models.TextField(verbose_name="Вимоги")
    must_have = models.TextField(verbose_name="Обов'язково має бути")
    start_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Початок завдання",
    )
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Дедлайн здачі",
    )
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

    @property
    def effective_start(self):
        return self.start_at or self.tournament.start_date

    @property
    def effective_deadline(self):
        return self.deadline or self.tournament.end_date

    @property
    def lifecycle_status(self):
        now = timezone.now()
        if self.is_draft:
            return "draft"
        if self.effective_start and now < self.effective_start:
            return "scheduled"
        if self.effective_deadline and now > self.effective_deadline:
            return "submission_closed"
        return "active"

    @property
    def lifecycle_status_label(self):
        labels = {
            "draft": "Чернетка",
            "scheduled": "Очікує старту",
            "active": "Активне",
            "submission_closed": "Прийом рішень закрито",
        }
        return labels[self.lifecycle_status]

    @property
    def is_submission_open(self):
        return self.lifecycle_status == "active"


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
        verbose_name="Демо РїРѕСЃРёР»Р°РЅРЅСЏ",
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


class RegistrationMember(models.Model):
    registration = models.ForeignKey(
        TournamentRegistration,
        on_delete=models.CASCADE,
        related_name="members",
        verbose_name="Заявка",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registration_memberships",
        verbose_name="Пов'язаний користувач",
    )
    full_name = models.CharField(max_length=255, verbose_name="ПІБ")
    email = models.EmailField(verbose_name="Email")

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Учасник заявки"
        verbose_name_plural = "Учасники заявок"
        constraints = [
            models.UniqueConstraint(
                fields=["registration", "email"],
                name="unique_registration_member_email",
            )
        ]

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class Announcement(models.Model):
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    message = models.TextField(verbose_name="Текст оголошення")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="announcements_created",
        verbose_name="Створено користувачем",
    )
    tournament = models.ForeignKey(
        Tournament,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="announcements",
        verbose_name="Турнір",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Дата створення")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Оголошення"
        verbose_name_plural = "Оголошення"

    def __str__(self):
        return self.title


class Certificate(models.Model):
    class CertificateType(models.TextChoices):
        PARTICIPANT = "participant", "Учасник"
        WINNER = "winner", "Переможець"

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="certificates",
        verbose_name="Турнір",
    )
    team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="certificates",
        verbose_name="Команда",
    )
    certificate_type = models.CharField(
        max_length=20,
        choices=CertificateType.choices,
        db_index=True,
        verbose_name="Тип сертифіката",
    )
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="certificates_received",
        verbose_name="Користувач-отримувач",
    )
    recipient_name = models.CharField(max_length=255, verbose_name="Ім'я отримувача")
    recipient_email = models.EmailField(verbose_name="Email отримувача")
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="certificates_issued",
        verbose_name="Видав користувач",
    )
    issued_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Дата видачі")

    class Meta:
        ordering = ["-issued_at"]
        verbose_name = "Сертифікат"
        verbose_name_plural = "Сертифікати"
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
        verbose_name="Турнір",
    )
    certificate_type = models.CharField(
        max_length=20,
        choices=Certificate.CertificateType.choices,
        db_index=True,
        verbose_name="Тип сертифіката",
    )
    background_image = models.ImageField(
        upload_to="certificate_templates/",
        verbose_name="Шаблон сертифіката",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_certificate_templates",
        verbose_name="Завантажив користувач",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Дата завантаження")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Шаблон сертифіката"
        verbose_name_plural = "Шаблони сертифікатів"

    def __str__(self):
        scope = self.tournament.name if self.tournament_id else "Глобальний"
        return f"{scope}: {self.get_certificate_type_display()}"



