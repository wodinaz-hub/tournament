from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tournament", "0008_tournament_registration_form_description_and_team_limits"),
    ]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="registration_fields_config",
            field=models.JSONField(blank=True, default=list, verbose_name="Поля форми реєстрації"),
        ),
        migrations.AddField(
            model_name="tournamentregistration",
            name="form_answers",
            field=models.JSONField(blank=True, default=dict, verbose_name="Відповіді на поля форми"),
        ),
    ]
