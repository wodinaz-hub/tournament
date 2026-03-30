from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tournament", "0017_task_start_at_deadline"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="evaluation_finished_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="Оцінювання завершено",
            ),
        ),
        migrations.AddField(
            model_name="tournament",
            name="evaluation_finished_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="tournaments_evaluation_finished",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Оцінювання завершив",
            ),
        ),
    ]
