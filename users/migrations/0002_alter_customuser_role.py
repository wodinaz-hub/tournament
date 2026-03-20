from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="role",
            field=models.CharField(
                choices=[
                    ("participant", "Participant"),
                    ("captain", "Captain"),
                    ("jury", "Jury"),
                    ("admin", "Admin"),
                ],
                default="participant",
                max_length=20,
            ),
        ),
    ]
