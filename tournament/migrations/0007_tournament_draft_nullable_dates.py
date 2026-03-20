from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tournament", "0006_task_official_solution"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tournament",
            name="start_date",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Дата початку"),
        ),
        migrations.AlterField(
            model_name="tournament",
            name="end_date",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Дата завершення"),
        ),
        migrations.AlterField(
            model_name="tournament",
            name="registration_start",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Початок реєстрації"),
        ),
        migrations.AlterField(
            model_name="tournament",
            name="registration_end",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Завершення реєстрації"),
        ),
    ]
