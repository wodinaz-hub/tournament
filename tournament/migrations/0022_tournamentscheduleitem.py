from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tournament", "0021_tournament_allowed_contact_methods"),
    ]

    operations = [
        migrations.CreateModel(
            name="TournamentScheduleItem",
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
                (
                    "title",
                    models.CharField(max_length=255, verbose_name="Назва події"),
                ),
                (
                    "starts_at",
                    models.DateTimeField(db_index=True, verbose_name="Дата та час"),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Опис події",
                    ),
                ),
                (
                    "position",
                    models.PositiveIntegerField(default=0, verbose_name="Порядок"),
                ),
                (
                    "tournament",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="schedule_items",
                        to="tournament.tournament",
                        verbose_name="Турнір",
                    ),
                ),
            ],
            options={
                "verbose_name": "Подія розкладу турніру",
                "verbose_name_plural": "Події розкладу турніру",
                "ordering": ["starts_at", "position", "id"],
            },
        ),
    ]
