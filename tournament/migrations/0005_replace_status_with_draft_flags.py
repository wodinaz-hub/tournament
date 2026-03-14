from django.db import migrations, models


def copy_statuses_to_drafts(apps, schema_editor):
    Tournament = apps.get_model("tournament", "Tournament")
    Task = apps.get_model("tournament", "Task")

    for tournament in Tournament.objects.all():
        tournament.is_draft = tournament.status == "draft"
        tournament.save(update_fields=["is_draft"])

    for task in Task.objects.all():
        task.is_draft = task.status == "draft"
        task.save(update_fields=["is_draft"])


class Migration(migrations.Migration):

    dependencies = [
        ("tournament", "0004_tournament_end_date_remove_task_dates"),
    ]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="is_draft",
            field=models.BooleanField(default=True, verbose_name="Чернетка"),
        ),
        migrations.AddField(
            model_name="task",
            name="is_draft",
            field=models.BooleanField(default=True, verbose_name="Чернетка"),
        ),
        migrations.RunPython(copy_statuses_to_drafts, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="tournament",
            name="status",
        ),
        migrations.RemoveField(
            model_name="task",
            name="status",
        ),
    ]
