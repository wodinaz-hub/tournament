from django.contrib import admin
from .models import (
    Tournament,
    Team,
    Participant,
    Task,
    Submission,
    JuryAssignment,
    Evaluation,
)

admin.site.register(Tournament)
admin.site.register(Team)
admin.site.register(Participant)
admin.site.register(Task)
admin.site.register(Submission)
admin.site.register(JuryAssignment)
admin.site.register(Evaluation)