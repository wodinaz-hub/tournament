from django.db import migrations


def convert_captains_to_participants(apps, schema_editor):
    CustomUser = apps.get_model("users", "CustomUser")
    CustomUser.objects.filter(role="captain").update(role="participant", is_approved=True)


def revert_participants_to_captains(apps, schema_editor):
    CustomUser = apps.get_model("users", "CustomUser")
    CustomUser.objects.filter(role="participant", is_approved=True).update(role="captain")


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_alter_customuser_role"),
    ]

    operations = [
        migrations.RunPython(
            convert_captains_to_participants,
            revert_participants_to_captains,
        ),
    ]
