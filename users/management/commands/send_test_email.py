from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Надсилає тестовий лист для перевірки email-конфігурації."

    def add_arguments(self, parser):
        parser.add_argument("recipient", help="Email-адреса отримувача")

    def handle(self, *args, **options):
        recipient = options["recipient"]

        if not settings.DEFAULT_FROM_EMAIL:
            raise CommandError("DEFAULT_FROM_EMAIL не налаштований.")

        send_mail(
            subject="Тестовий лист із платформи турнірів",
            message="Якщо ви отримали цей лист, email-конфігурація працює.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        self.stdout.write(self.style.SUCCESS(f"Лист успішно відправлено на {recipient}"))
