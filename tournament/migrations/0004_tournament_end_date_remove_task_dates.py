from datetime import timedelta

from django.db import migrations, models


def populate_tournament_end_date(apps, schema_editor):
    Tournament = apps.get_model("tournament", "Tournament")
    for tournament in Tournament.objects.all():
        tournament.end_date = tournament.start_date + timedelta(days=1)
        tournament.save(update_fields=["end_date"])


class Migration(migrations.Migration):

    dependencies = [
        ("tournament", "0003_tournamentregistration_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="end_date",
            field=models.DateTimeField(
                null=True,
                verbose_name="Дата завершення",
            ),
        ),
        migrations.RunPython(
            populate_tournament_end_date,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="tournament",
            name="end_date",
            field=models.DateTimeField(verbose_name="Дата завершення"),
        ),
        migrations.RemoveField(
            model_name="task",
            name="deadline",
        ),
        migrations.RemoveField(
            model_name="task",
            name="start_time",
        ),
        migrations.AlterModelOptions(
            name="task",
            options={
                "ordering": ["title"],
                "verbose_name": "Завдання",
                "verbose_name_plural": "Завдання",
            },
        ),
    ]
