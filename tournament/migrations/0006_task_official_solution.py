from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tournament", "0005_replace_status_with_draft_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="official_solution",
            field=models.TextField(
                blank=True,
                null=True,
                verbose_name="Офіційна відповідь / розбір",
            ),
        ),
    ]
