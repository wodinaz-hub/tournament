from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0012_customuser_email_verified_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginThrottle",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("identifier", models.CharField(max_length=150, verbose_name="Логін")),
                ("ip_address", models.CharField(max_length=64, verbose_name="IP-адреса")),
                (
                    "failed_attempts",
                    models.PositiveIntegerField(default=0, verbose_name="Кількість невдалих спроб"),
                ),
                (
                    "blocked_until",
                    models.DateTimeField(blank=True, null=True, verbose_name="Заблоковано до"),
                ),
                (
                    "last_failed_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Остання невдала спроба"),
                ),
            ],
            options={
                "verbose_name": "Обмеження входу",
                "verbose_name_plural": "Обмеження входу",
            },
        ),
        migrations.AddConstraint(
            model_name="loginthrottle",
            constraint=models.UniqueConstraint(
                fields=("identifier", "ip_address"),
                name="unique_login_throttle_identifier_ip",
            ),
        ),
    ]
