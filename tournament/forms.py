import json

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import (
    Announcement,
    CertificateTemplate,
    Evaluation,
    Participant,
    Submission,
    Task,
    Team,
    Tournament,
    TournamentRegistration,
)
from users.models import CustomUser


REGISTRATION_FIELD_TYPE_CHOICES = {
    'text': forms.CharField,
    'textarea': forms.CharField,
    'email': forms.EmailField,
    'number': forms.IntegerField,
    'url': forms.URLField,
    'participants': forms.CharField,
}


def normalize_registration_field_key(value, fallback_label=''):
    source = (value or fallback_label or '').strip().lower()
    normalized_chars = []
    for char in source:
        if char.isalnum():
            normalized_chars.append(char)
        elif char in {' ', '-', '.'}:
            normalized_chars.append('_')
        elif char == '_':
            normalized_chars.append(char)

    normalized = ''.join(normalized_chars).strip('_')
    while '__' in normalized:
        normalized = normalized.replace('__', '_')
    return normalized


def parse_registration_fields_definition(raw_value):
    config = []
    errors = []

    for index, raw_line in enumerate((raw_value or '').splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = [part.strip() for part in line.split('|')]
        if len(parts) < 2:
            errors.append(f'Р СЏРґРѕРє {index}: РїРѕС‚СЂС–Р±РЅРѕ С‰РѕРЅР°Р№РјРµРЅС€Рµ РєРѕРґ РїРѕР»СЏ С– РЅР°Р·РІР°.')
            continue

        field_key = normalize_registration_field_key(parts[0], parts[1] if len(parts) > 1 else '')
        field_label = parts[1]
        field_type = (parts[2] if len(parts) > 2 and parts[2] else 'text').lower()
        is_required = (parts[3] if len(parts) > 3 and parts[3] else 'required').lower()

        if not field_key:
            errors.append(f'Р СЏРґРѕРє {index}: РєРѕРґ РїРѕР»СЏ РјРѕР¶Рµ РјС–СЃС‚РёС‚Рё Р»РёС€Рµ Р»С–С‚РµСЂРё, С†РёС„СЂРё С‚Р° _.')
            continue

        if field_type not in REGISTRATION_FIELD_TYPE_CHOICES:
            errors.append(
                f'Р СЏРґРѕРє {index}: РЅРµРІС–РґРѕРјРёР№ С‚РёРї "{field_type}". Р”РѕСЃС‚СѓРїРЅРѕ: text, textarea, email, number, url, participants.'
            )
            continue

        if is_required not in {'required', 'optional'}:
            errors.append(f'Р СЏРґРѕРє {index}: РѕР±РѕРІ\'СЏР·РєРѕРІС–СЃС‚СЊ РјР°С” Р±СѓС‚Рё required Р°Р±Рѕ optional.')
            continue

        if any(item['key'] == field_key for item in config):
            errors.append(f'Р СЏРґРѕРє {index}: РєРѕРґ РїРѕР»СЏ "{field_key}" РІР¶Рµ РІРёРєРѕСЂРёСЃС‚РѕРІСѓС”С‚СЊСЃСЏ.')
            continue

        config.append({
            'key': field_key,
            'label': field_label,
            'type': field_type,
            'required': is_required == 'required',
        })

    if errors:
        raise ValidationError(errors)

    return config


def serialize_registration_fields_definition(config):
    lines = []
    for item in config or []:
        requirement = 'required' if item.get('required') else 'optional'
        lines.append(
            f"{item.get('key', '')}|{item.get('label', '')}|{item.get('type', 'text')}|{requirement}"
        )
    return '\n'.join(lines)


class TournamentForm(forms.ModelForm):
    registration_fields_definition = forms.CharField(
        required=False,
        label='Р”РѕРґР°С‚РєРѕРІС– РїРѕР»СЏ Р°РЅРєРµС‚Рё',
        help_text='РљРѕР¶РµРЅ СЂСЏРґРѕРє: РєРѕРґ_РїРѕР»СЏ|РќР°Р·РІР° РїРѕР»СЏ|С‚РёРї|required Р°Р±Рѕ optional. РўРёРїРё: text, textarea, email, number, url.',
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 6}),
    )
    start_date = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local', 'class': 'form-input'},
        ),
        label='Р”Р°С‚Р° РїРѕС‡Р°С‚РєСѓ',
    )
    end_date = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local', 'class': 'form-input'},
        ),
        label='Р”Р°С‚Р° Р·Р°РІРµСЂС€РµРЅРЅСЏ',
    )
    registration_start = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local', 'class': 'form-input'},
        ),
        label='РџРѕС‡Р°С‚РѕРє СЂРµС”СЃС‚СЂР°С†С–С—',
    )
    registration_end = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local', 'class': 'form-input'},
        ),
        label='Р—Р°РІРµСЂС€РµРЅРЅСЏ СЂРµС”СЃС‚СЂР°С†С–С—',
    )

    class Meta:
        model = Tournament
        fields = [
            'name',
            'description',
            'registration_form_description',
            'registration_fields_definition',
            'start_date',
            'end_date',
            'registration_start',
            'registration_end',
            'min_team_members',
            'max_team_members',
            'max_teams',
            'jury_users',
            'is_draft',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 5}),
            'registration_form_description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'min_team_members': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'max_team_members': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'max_teams': forms.NumberInput(attrs={'class': 'form-input'}),
            'jury_users': forms.SelectMultiple(attrs={'class': 'form-input', 'size': 6}),
            'is_draft': forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = self.instance.registration_fields_config if getattr(self.instance, 'pk', None) else []
        self.fields['registration_fields_definition'].initial = serialize_registration_fields_definition(config)
        for field_name in [
            'name',
            'description',
            'registration_form_description',
            'registration_fields_definition',
            'start_date',
            'end_date',
            'registration_start',
            'registration_end',
            'min_team_members',
            'max_team_members',
            'jury_users',
        ]:
            self.fields[field_name].required = False
        self.fields['jury_users'].queryset = CustomUser.objects.filter(
            role='jury',
            is_approved=True,
        ).order_by('username')

    def clean(self):
        cleaned_data = super().clean()
        is_draft = cleaned_data.get('is_draft')
        registration_start = cleaned_data.get('registration_start')
        registration_end = cleaned_data.get('registration_end')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        min_team_members = cleaned_data.get('min_team_members')
        max_team_members = cleaned_data.get('max_team_members')
        name = (cleaned_data.get('name') or '').strip()
        description = (cleaned_data.get('description') or '').strip()

        cleaned_data['name'] = name
        cleaned_data['description'] = description
        registration_fields_definition = cleaned_data.get('registration_fields_definition', '')

        try:
            cleaned_data['registration_fields_config'] = parse_registration_fields_definition(
                registration_fields_definition
            )
        except ValidationError as exc:
            for error in exc.messages:
                self.add_error('registration_fields_definition', error)

        if is_draft:
            return cleaned_data

        required_fields = {
            'name': name,
            'description': description,
            'start_date': start_date,
            'end_date': end_date,
            'registration_start': registration_start,
            'registration_end': registration_end,
        }
        for field_name, value in required_fields.items():
            if value in [None, '']:
                self.add_error(field_name, 'Р¦Рµ РїРѕР»Рµ С” РѕР±РѕРІвЂ™СЏР·РєРѕРІРёРј РґР»СЏ РѕРїСѓР±Р»С–РєРѕРІР°РЅРѕРіРѕ С‚СѓСЂРЅС–СЂСѓ.')

        if registration_start and registration_end and registration_start >= registration_end:
            self.add_error('registration_end', 'Р—Р°РІРµСЂС€РµРЅРЅСЏ СЂРµС”СЃС‚СЂР°С†С–С— РјР°С” Р±СѓС‚Рё РїС–Р·РЅС–С€Рµ Р·Р° РїРѕС‡Р°С‚РѕРє СЂРµС”СЃС‚СЂР°С†С–С—.')

        if registration_end and start_date and registration_end > start_date:
            self.add_error('registration_end', 'Р РµС”СЃС‚СЂР°С†С–СЏ РјР°С” Р·Р°РІРµСЂС€СѓРІР°С‚РёСЃСЏ РґРѕ РїРѕС‡Р°С‚РєСѓ С‚СѓСЂРЅС–СЂСѓ.')

        if start_date and end_date and end_date <= start_date:
            self.add_error('end_date', 'РўСѓСЂРЅС–СЂ РјР°С” Р·Р°РІРµСЂС€СѓРІР°С‚РёСЃСЏ РїС–СЃР»СЏ РїРѕС‡Р°С‚РєСѓ.')

        if (
            min_team_members is not None
            and max_team_members is not None
            and min_team_members > max_team_members
        ):
            self.add_error('max_team_members', 'РњР°РєСЃРёРјР°Р»СЊРЅР° РєС–Р»СЊРєС–СЃС‚СЊ Р»СЋРґРµР№ Сѓ РєРѕРјР°РЅРґС– РјР°С” Р±СѓС‚Рё РЅРµ РјРµРЅС€РѕСЋ Р·Р° РјС–РЅС–РјР°Р»СЊРЅСѓ.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.registration_fields_config = self.cleaned_data.get('registration_fields_config', [])
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'captain_name', 'captain_email', 'school', 'telegram', 'discord', 'viber']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'captain_name': forms.TextInput(attrs={'class': 'form-input'}),
            'captain_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'school': forms.TextInput(attrs={'class': 'form-input'}),
            'telegram': forms.TextInput(attrs={'class': 'form-input'}),
            'discord': forms.TextInput(attrs={'class': 'form-input'}),
            'viber': forms.TextInput(attrs={'class': 'form-input'}),
        }


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['full_name', 'email']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
        }


class TournamentRegistrationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        self.user = user
        self.tournament = kwargs.pop('tournament', None)
        super().__init__(*args, **kwargs)

        existing_team = Team.objects.filter(captain_user=user).order_by('name').first() if user is not None else None
        self.existing_team = existing_team

        self.fields['team_name'] = forms.CharField(
            label='Назва команди',
            widget=forms.TextInput(attrs={'class': 'form-input'}),
        )
        self.fields['captain_name'] = forms.CharField(
            label="Ім'я контактної особи",
            widget=forms.TextInput(attrs={'class': 'form-input'}),
        )
        self.fields['captain_email'] = forms.EmailField(
            label='Електронна пошта контактної особи',
            widget=forms.EmailInput(attrs={'class': 'form-input'}),
        )
        self.fields['school'] = forms.CharField(
            required=False,
            label='Школа',
            widget=forms.TextInput(attrs={'class': 'form-input'}),
        )
        self.fields['telegram'] = forms.CharField(
            required=False,
            label='Телеграм',
            widget=forms.TextInput(attrs={'class': 'form-input'}),
        )
        self.fields['discord'] = forms.CharField(
            required=False,
            label='Діскорд',
            widget=forms.TextInput(attrs={'class': 'form-input'}),
        )
        self.fields['viber'] = forms.CharField(
            required=False,
            label='Вайбер',
            widget=forms.TextInput(attrs={'class': 'form-input'}),
        )

        if existing_team is not None:
            self.fields['team_name'].initial = existing_team.name
            self.fields['captain_name'].initial = existing_team.captain_name
            self.fields['captain_email'].initial = existing_team.captain_email
            self.fields['school'].initial = existing_team.school
            self.fields['telegram'].initial = existing_team.telegram
            self.fields['discord'].initial = existing_team.discord
            self.fields['viber'].initial = existing_team.viber
        elif user is not None:
            self.fields['captain_name'].initial = user.username
            self.fields['captain_email'].initial = user.email

        for field_config in (self.tournament.registration_fields_config if self.tournament else []):
            self.fields[self.answer_field_name(field_config['key'])] = self.build_dynamic_field(field_config)

    @staticmethod
    def answer_field_name(field_key):
        return f'field_{field_key}'

    def build_dynamic_field(self, field_config):
        if field_config['type'] == 'participants':
            return forms.CharField(
                label=field_config['label'],
                required=field_config.get('required', False),
                widget=forms.HiddenInput(
                    attrs={
                        'class': 'participants-json-input',
                        'data_field_type': 'participants',
                        'data_min_members': self.tournament.min_team_members or '',
                        'data_max_members': self.tournament.max_team_members or '',
                    }
                ),
            )

        field_class = REGISTRATION_FIELD_TYPE_CHOICES[field_config['type']]
        kwargs = {
            'label': field_config['label'],
            'required': field_config.get('required', False),
            'widget': forms.Textarea(attrs={'class': 'form-input', 'rows': 4})
            if field_config['type'] == 'textarea'
            else None,
        }
        if kwargs['widget'] is None:
            kwargs.pop('widget')
        else:
            kwargs['widget'].attrs.setdefault('class', 'form-input')

        if field_config['type'] == 'number':
            kwargs['widget'] = forms.NumberInput(attrs={'class': 'form-input'})
        elif field_config['type'] == 'email':
            kwargs['widget'] = forms.EmailInput(attrs={'class': 'form-input'})
        elif field_config['type'] == 'url':
            kwargs['widget'] = forms.URLInput(attrs={'class': 'form-input'})
        elif field_config['type'] == 'text':
            kwargs['widget'] = forms.TextInput(attrs={'class': 'form-input'})

        return field_class(**kwargs)

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['team_name'] = (cleaned_data.get('team_name') or '').strip()
        cleaned_data['captain_name'] = (cleaned_data.get('captain_name') or '').strip()
        cleaned_data['captain_email'] = (cleaned_data.get('captain_email') or '').strip().lower()
        cleaned_data['school'] = (cleaned_data.get('school') or '').strip()
        cleaned_data['telegram'] = (cleaned_data.get('telegram') or '').strip()
        cleaned_data['discord'] = (cleaned_data.get('discord') or '').strip()
        cleaned_data['viber'] = (cleaned_data.get('viber') or '').strip()

        if not cleaned_data['team_name']:
            self.add_error('team_name', 'Вкажіть назву команди.')
        if not cleaned_data['captain_name']:
            self.add_error('captain_name', "Вкажіть ім'я контактної особи.")
        if not cleaned_data['captain_email']:
            self.add_error('captain_email', 'Вкажіть електронну пошту контактної особи.')

        for field_config in (self.tournament.registration_fields_config if self.tournament else []):
            if field_config['type'] != 'participants':
                continue

            field_name = self.answer_field_name(field_config['key'])
            raw_value = cleaned_data.get(field_name)
            if not raw_value:
                if field_config.get('required', False):
                    self.add_error(field_name, 'Додайте учасників команди.')
                cleaned_data[field_name] = []
                continue

            try:
                payload = json.loads(raw_value)
            except json.JSONDecodeError:
                self.add_error(field_name, 'Не вдалося прочитати список учасників.')
                continue

            if not isinstance(payload, list):
                self.add_error(field_name, 'Список учасників має бути списком.')
                continue

            participants = []
            for index, item in enumerate(payload, start=1):
                if not isinstance(item, dict):
                    self.add_error(field_name, "Кожен учасник має містити ім'я та email.")
                    continue

                full_name = (item.get('full_name') or '').strip()
                email = (item.get('email') or '').strip().lower()
                if not full_name:
                    self.add_error(field_name, f"Учасник {index}: вкажіть ім'я.")
                if not email:
                    self.add_error(field_name, f'Учасник {index}: вкажіть email.')
                else:
                    try:
                        validate_email(email)
                    except ValidationError:
                        self.add_error(field_name, f'Учасник {index}: некоректний формат email.')

                participants.append({
                    'full_name': full_name,
                    'email': email,
                })

            if self.errors.get(field_name):
                continue

            participant_emails = [item['email'] for item in participants]
            if len(participant_emails) != len(set(participant_emails)):
                self.add_error(field_name, 'Email не повинен повторюватися в межах однієї команди.')

            if cleaned_data.get('captain_email') and cleaned_data['captain_email'] in participant_emails:
                self.add_error(field_name, 'Email контактної особи не може дублюватися серед учасників.')

            total_members = 1 + len(participants)
            if self.tournament.min_team_members is not None and total_members < self.tournament.min_team_members:
                self.add_error(
                    field_name,
                    f'У команді замало людей. Потрібно щонайменше: {self.tournament.min_team_members}.',
                )
            if self.tournament.max_team_members is not None and total_members > self.tournament.max_team_members:
                self.add_error(
                    field_name,
                    f'У команді забагато людей. Максимум дозволено: {self.tournament.max_team_members}.',
                )

            cleaned_data[field_name] = participants

        return cleaned_data

    def cleaned_team_data(self):
        return {
            'name': self.cleaned_data['team_name'],
            'captain_name': self.cleaned_data['captain_name'],
            'captain_email': self.cleaned_data['captain_email'],
            'school': self.cleaned_data.get('school', ''),
            'telegram': self.cleaned_data.get('telegram', ''),
            'discord': self.cleaned_data.get('discord', ''),
            'viber': self.cleaned_data.get('viber', ''),
        }

    def cleaned_form_answers(self):
        answers = {}
        for field_config in (self.tournament.registration_fields_config if self.tournament else []):
            field_name = self.answer_field_name(field_config['key'])
            value = self.cleaned_data.get(field_name)
            if field_config['type'] == 'participants':
                answers[field_config['key']] = value or []
            else:
                answers[field_config['key']] = '' if value is None else str(value)
        return answers

    def cleaned_participants(self):
        for field_config in (self.tournament.registration_fields_config if self.tournament else []):
            if field_config['type'] == 'participants':
                return self.cleaned_data.get(self.answer_field_name(field_config['key']), [])
        return None


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'tournament',
            'title',
            'description',
            'requirements',
            'must_have',
            'official_solution',
            'is_draft',
        ]
        widgets = {
            'tournament': forms.Select(attrs={'class': 'form-input'}),
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'requirements': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'must_have': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'official_solution': forms.Textarea(attrs={'class': 'form-input', 'rows': 5}),
            'is_draft': forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        tournament = kwargs.pop('tournament', None)
        super().__init__(*args, **kwargs)
        for field_name in [
            'title',
            'description',
            'requirements',
            'must_have',
            'official_solution',
        ]:
            self.fields[field_name].required = False

        if tournament is not None:
            self.fields['tournament'].initial = tournament
            self.fields['tournament'].widget = forms.HiddenInput()
            self.fields['tournament'].queryset = Tournament.objects.filter(id=tournament.id)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('is_draft'):
            return cleaned_data

        required_fields = {
            'title': (cleaned_data.get('title') or '').strip(),
            'description': (cleaned_data.get('description') or '').strip(),
            'requirements': (cleaned_data.get('requirements') or '').strip(),
            'must_have': (cleaned_data.get('must_have') or '').strip(),
        }
        for field_name, value in required_fields.items():
            if not value:
                self.add_error(field_name, 'Р¦Рµ РїРѕР»Рµ С” РѕР±РѕРІвЂ™СЏР·РєРѕРІРёРј РґР»СЏ РѕРїСѓР±Р»С–РєРѕРІР°РЅРѕРіРѕ Р·Р°РІРґР°РЅРЅСЏ.')

        return cleaned_data


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


class EvaluationForm(forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = [
            'score_backend',
            'score_frontend',
            'score_functionality',
            'score_ux',
            'comment',
        ]
        widgets = {
            'score_backend': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100}),
            'score_frontend': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100}),
            'score_functionality': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100}),
            'score_ux': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100}),
            'comment': forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
        }


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'message', 'tournament']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'message': forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'tournament': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        allow_global = kwargs.pop('allow_global', True)
        tournament_queryset = kwargs.pop('tournament_queryset', Tournament.objects.none())
        super().__init__(*args, **kwargs)
        self.fields['tournament'].required = not allow_global
        self.fields['tournament'].queryset = tournament_queryset
        if allow_global:
            self.fields['tournament'].empty_label = 'РЈСЃС– С‚СѓСЂРЅС–СЂРё / Р·Р°РіР°Р»СЊРЅРµ РѕРіРѕР»РѕС€РµРЅРЅСЏ'
class CertificateTemplateForm(forms.ModelForm):
    class Meta:
        model = CertificateTemplate
        fields = ['tournament', 'certificate_type', 'background_image']
        widgets = {
            'tournament': forms.Select(attrs={'class': 'form-input'}),
            'certificate_type': forms.Select(attrs={'class': 'form-input'}),
            'background_image': forms.ClearableFileInput(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        allow_global = kwargs.pop('allow_global', True)
        tournament_queryset = kwargs.pop('tournament_queryset', Tournament.objects.none())
        super().__init__(*args, **kwargs)
        self.fields['tournament'].required = not allow_global
        self.fields['tournament'].queryset = tournament_queryset
        if allow_global:
            self.fields['tournament'].empty_label = 'Р“Р»РѕР±Р°Р»СЊРЅРёР№ С€Р°Р±Р»РѕРЅ РґР»СЏ РІСЃС–С… С‚СѓСЂРЅС–СЂС–РІ'



