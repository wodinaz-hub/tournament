import json
from datetime import timedelta
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import LoginThrottle


LOGIN_THROTTLE_IDENTIFIER_SESSION_KEY = "login_throttle_identifier"
LOGIN_THROTTLE_IP_SESSION_KEY = "login_throttle_ip"


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def normalize_login_identifier(value):
    return (value or "").strip().lower()


def get_login_throttle(identifier, ip_address):
    if not identifier:
        return None
    return LoginThrottle.objects.filter(
        identifier=identifier,
        ip_address=ip_address,
    ).first()


def clear_login_throttle(request, identifier, ip_address):
    if identifier:
        LoginThrottle.objects.filter(
            identifier=identifier,
            ip_address=ip_address,
        ).delete()
    request.session.pop(LOGIN_THROTTLE_IDENTIFIER_SESSION_KEY, None)
    request.session.pop(LOGIN_THROTTLE_IP_SESSION_KEY, None)


def register_failed_login(identifier, ip_address):
    if not identifier:
        return None, None

    now = timezone.now()
    throttle, _created = LoginThrottle.objects.get_or_create(
        identifier=identifier,
        ip_address=ip_address,
    )

    if throttle.blocked_until and throttle.blocked_until > now:
        return throttle, 0

    max_attempts = getattr(settings, "LOGIN_MAX_ATTEMPTS", 5)
    block_minutes = getattr(settings, "LOGIN_BLOCK_MINUTES", 15)
    next_attempts = throttle.failed_attempts + 1

    throttle.failed_attempts = next_attempts
    throttle.last_failed_at = now

    if next_attempts >= max_attempts:
        throttle.blocked_until = now + timedelta(minutes=block_minutes)
        throttle.failed_attempts = 0
        throttle.save(update_fields=["failed_attempts", "blocked_until", "last_failed_at"])
        return throttle, 0

    throttle.blocked_until = None
    throttle.save(update_fields=["failed_attempts", "blocked_until", "last_failed_at"])
    return throttle, max_attempts - next_attempts


def send_platform_email(to_email, subject, message):
    provider = getattr(settings, "EMAIL_DELIVERY_PROVIDER", "")

    if provider == "brevo":
        payload = json.dumps(
            {
                "sender": {
                    "email": settings.DEFAULT_FROM_EMAIL,
                    "name": getattr(settings, "EMAIL_SENDER_NAME", "Tournament Platform"),
                },
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": message,
            }
        ).encode("utf-8")
        request = Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={
                "accept": "application/json",
                "api-key": settings.BREVO_API_KEY,
                "content-type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=settings.EMAIL_TIMEOUT):
            pass
        return

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        fail_silently=False,
    )


def send_verification_email(request, user):
    verification_link = request.build_absolute_uri(
        reverse(
            "verify_email",
            args=[
                urlsafe_base64_encode(force_bytes(user.pk)),
                default_token_generator.make_token(user),
            ],
        )
    )
    subject = "Підтвердження електронної пошти"
    message = render_to_string(
        "emails/verify_email.txt",
        {
            "user": user,
            "verification_link": verification_link,
        },
    )
    send_platform_email(user.email, subject, message)


def send_team_invitation_email(request, *, team, recipient_name, recipient_email):
    registration_link = request.build_absolute_uri(reverse("register"))
    greeting_name = recipient_name or recipient_email
    subject = f'Запрошення до команди "{team.name}"'
    message = (
        f"Вітаємо, {greeting_name}!\n\n"
        f'Вас намагаються додати до команди "{team.name}" на турнірній платформі.\n'
        "Щоб приєднатися до команди та отримати доступ до турнірів, спочатку зареєструйтеся на сайті.\n\n"
        f"Посилання для реєстрації: {registration_link}\n\n"
        "Після реєстрації організатор або контактна особа команди зможе додати вас повторно."
    )
    send_platform_email(recipient_email, subject, message)


def email_delivery_ready():
    if settings.EMAIL_BACKEND == "django.core.mail.backends.locmem.EmailBackend":
        return True
    non_delivery_backends = {
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
    }
    provider = getattr(settings, "EMAIL_DELIVERY_PROVIDER", "")
    if provider == "brevo":
        return bool(getattr(settings, "BREVO_API_KEY", "") and settings.DEFAULT_FROM_EMAIL)
    return settings.DEBUG or settings.EMAIL_BACKEND not in non_delivery_backends
