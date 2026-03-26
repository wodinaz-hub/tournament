from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_convert_captains_to_participants'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='role',
            field=models.CharField(
                choices=[
                    ('participant', 'Учасник'),
                    ('jury', 'Журі'),
                    ('organizer', 'Організатор'),
                    ('admin', 'Адміністратор'),
                ],
                default='participant',
                max_length=20,
            ),
        ),
    ]
