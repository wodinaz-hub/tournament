from django.core.management.base import BaseCommand, CommandError

from users.views import send_platform_email


class Command(BaseCommand):
    help = "Надсилає тестовий лист для перевірки email-конфігурації."

    def add_arguments(self, parser):
        parser.add_argument("recipient", help="Email-адреса отримувача")

    def handle(self, *args, **options):
        recipient = options["recipient"]

        try:
            send_platform_email(
                recipient,
                "Тестовий лист із платформи турнірів",
                "Якщо ви отримали цей лист, email-конфігурація працює.",
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Лист успішно відправлено на {recipient}"))
