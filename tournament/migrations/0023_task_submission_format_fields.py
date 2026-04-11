from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tournament", "0022_tournamentscheduleitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="form_answers",
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name="Додаткові відповіді",
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="submission_fields_config",
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name="Формат відповіді",
            ),
        ),
        migrations.AlterField(
            model_name="submission",
            name="github_link",
            field=models.URLField(
                blank=True,
                verbose_name="GitHub посилання",
            ),
        ),
        migrations.AlterField(
            model_name="submission",
            name="video_link",
            field=models.URLField(
                blank=True,
                verbose_name="Відео посилання",
            ),
        ),
    ]
