from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('participant', 'Participant'),
        ('captain', 'Captain'),
        ('jury', 'Jury'),
        ('admin', 'Admin'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='participant')
    is_approved = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.role == 'participant':
            self.is_approved = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.role})"