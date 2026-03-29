# Налаштування реальної відправки email

На безкоштовному Render SMTP-порти `25`, `465`, `587` заблоковані.
Тому для Free-плану рекомендовано використовувати email API, наприклад Brevo.

## Варіант 1. SMTP

Підходить для локальної розробки та платних інстансів Render.

Заповніть:

- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `EMAIL_USE_SSL`
- `EMAIL_TIMEOUT`
- `DEFAULT_FROM_EMAIL`
- `EMAIL_SENDER_NAME`

Для Gmail використовуйте пароль застосунку.

## Варіант 2. Brevo API

Рекомендований для безкоштовного Render.

1. Створіть акаунт у Brevo.
2. Підтвердьте email-відправника або домен.
3. Створіть API key.
4. Додайте змінні:

- `EMAIL_DELIVERY_PROVIDER=brevo`
- `BREVO_API_KEY=...`
- `DEFAULT_FROM_EMAIL=verified-sender@example.com`
- `EMAIL_SENDER_NAME=Tournament Platform`
- `EMAIL_TIMEOUT=20`

## Перевірка

```bash
python manage.py send_test_email you@example.com
```

Якщо лист приходить, конфігурація працює.
