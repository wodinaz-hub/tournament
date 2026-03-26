# Налаштування реальної відправки email

Платформа вміє надсилати реальні листи, якщо задані SMTP-змінні середовища.

## Локально

1. Скопіюйте `.env.example` у `.env`.
2. Заповніть:
   - `EMAIL_HOST`
   - `EMAIL_PORT`
   - `EMAIL_HOST_USER`
   - `EMAIL_HOST_PASSWORD`
   - `DEFAULT_FROM_EMAIL`
3. Для Gmail використовуйте пароль застосунку.

## Сервер / Render

Додайте в environment variables:

- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `EMAIL_USE_SSL`
- `EMAIL_TIMEOUT`
- `DEFAULT_FROM_EMAIL`

## Перевірка

```bash
python manage.py send_test_email you@example.com
```

Якщо лист приходить, значить SMTP-конфігурація працює.
