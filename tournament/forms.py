from django import forms

from .models import Participant, Submission, Task, Team, Tournament, TournamentRegistration


class TournamentForm(forms.ModelForm):
    start_date = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
        label='Дата початку',
    )
    end_date = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
        label='Дата завершення',
    )
    registration_start = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
        label='Початок реєстрації',
    )
    registration_end = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
        label='Завершення реєстрації',
    )

    class Meta:
        model = Tournament
        fields = [
            'name',
            'description',
            'start_date',
            'end_date',
            'registration_start',
            'registration_end',
            'max_teams',
            'is_draft',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 5}),
            'max_teams': forms.NumberInput(attrs={'class': 'form-input'}),
            'is_draft': forms.CheckboxInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        registration_start = cleaned_data.get('registration_start')
        registration_end = cleaned_data.get('registration_end')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if registration_start and registration_end and registration_start >= registration_end:
            self.add_error('registration_end', 'Завершення реєстрації має бути пізніше за початок реєстрації.')

        if registration_end and start_date and registration_end > start_date:
            self.add_error('registration_end', 'Реєстрація має завершуватися до початку турніру.')

        if start_date and end_date and end_date <= start_date:
            self.add_error('end_date', 'Турнір має завершуватися після початку.')

        return cleaned_data


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'captain_name', 'captain_email', 'school', 'telegram']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'captain_name': forms.TextInput(attrs={'class': 'form-input'}),
            'captain_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'school': forms.TextInput(attrs={'class': 'form-input'}),
            'telegram': forms.TextInput(attrs={'class': 'form-input'}),
        }


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['full_name', 'email']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
        }


class TournamentRegistrationForm(forms.ModelForm):
    class Meta:
        model = TournamentRegistration
        fields = ['team']
        widgets = {
            'team': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        tournament = kwargs.pop('tournament', None)
        super().__init__(*args, **kwargs)

        queryset = Team.objects.none()

        if user is not None:
            queryset = Team.objects.filter(captain_user=user).order_by('name')

        if tournament is not None:
            used_team_ids = TournamentRegistration.objects.filter(
                tournament=tournament
            ).values_list('team_id', flat=True)
            queryset = queryset.exclude(id__in=used_team_ids)

        self.fields['team'].queryset = queryset


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'tournament',
            'title',
            'description',
            'requirements',
            'must_have',
            'is_draft',
        ]
        widgets = {
            'tournament': forms.Select(attrs={'class': 'form-input'}),
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'requirements': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'must_have': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'is_draft': forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        tournament = kwargs.pop('tournament', None)
        super().__init__(*args, **kwargs)

        if tournament is not None:
            self.fields['tournament'].initial = tournament
            self.fields['tournament'].widget = forms.HiddenInput()
            self.fields['tournament'].queryset = Tournament.objects.filter(id=tournament.id)


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = [
            'github_link',
            'video_link',
            'live_demo',
            'description',
            'is_final',
        ]
        widgets = {
            'github_link': forms.URLInput(attrs={'class': 'form-input'}),
            'video_link': forms.URLInput(attrs={'class': 'form-input'}),
            'live_demo': forms.URLInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 5}),
            'is_final': forms.CheckboxInput(),
        }
