from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('participant', 'Учасник'),
        ('jury', 'Журі'),
        ('organizer', 'Організатор'),
        ('admin', 'Адміністратор'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='participant')
    is_approved = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    announcements_seen_at = models.DateTimeField(null=True, blank=True)
    certificates_seen_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.role == 'participant':
            self.is_approved = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.role})"


class LoginThrottle(models.Model):
    identifier = models.CharField(max_length=150, verbose_name="Логін")
    ip_address = models.CharField(max_length=64, verbose_name="IP-адреса")
    failed_attempts = models.PositiveIntegerField(default=0, verbose_name="Кількість невдалих спроб")
    blocked_until = models.DateTimeField(null=True, blank=True, verbose_name="Заблоковано до")
    last_failed_at = models.DateTimeField(null=True, blank=True, verbose_name="Остання невдала спроба")

    class Meta:
        verbose_name = "Обмеження входу"
        verbose_name_plural = "Обмеження входу"
        constraints = [
            models.UniqueConstraint(
                fields=["identifier", "ip_address"],
                name="unique_login_throttle_identifier_ip",
            )
        ]

    def __str__(self):
        return f"{self.identifier} @ {self.ip_address}"

