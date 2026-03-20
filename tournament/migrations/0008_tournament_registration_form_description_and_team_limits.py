from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tournament", "0007_tournament_draft_nullable_dates"),
    ]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="max_team_members",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Максимальна кількість людей у команді"),
        ),
        migrations.AddField(
            model_name="tournament",
            name="min_team_members",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Мінімальна кількість людей у команді"),
        ),
        migrations.AddField(
            model_name="tournament",
            name="registration_form_description",
            field=models.TextField(blank=True, default="", verbose_name="Опис форми реєстрації команди"),
        ),
    ]
