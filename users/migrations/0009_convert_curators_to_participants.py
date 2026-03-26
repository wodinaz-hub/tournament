from django.db import migrations


def convert_curators_to_participants(apps, schema_editor):
    CustomUser = apps.get_model("users", "CustomUser")
    Tournament = apps.get_model("tournament", "Tournament")

    CustomUser.objects.filter(role="curator").update(role="participant", is_approved=True)

    through_model = Tournament.curator_users.through
    through_model.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tournament", "0014_team_discord_team_viber"),
        ("users", "0008_alter_customuser_role"),
    ]

    operations = [
        migrations.RunPython(convert_curators_to_participants, migrations.RunPython.noop),
    ]
