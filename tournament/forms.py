import json

from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from .models import (
    Announcement,
    CertificateTemplate,
    Evaluation,
    Participant,
    Submission,
    Task,
    Team,
    Tournament,
    TournamentScheduleItem,
    TournamentRegistration,
)
from .validators import validate_school_name
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
            errors.append(f'Рядок {index}: потрібно щонайменше код поля і назва.')
            continue

        field_key = normalize_registration_field_key(parts[0], parts[1] if len(parts) > 1 else '')
        field_label = parts[1]
        field_type = (parts[2] if len(parts) > 2 and parts[2] else 'text').lower()
        is_required = (parts[3] if len(parts) > 3 and parts[3] else 'required').lower()

        if not field_key:
            errors.append(f'Рядок {index}: код поля може містити лише літери, цифри та _.')
            continue

        if field_type not in REGISTRATION_FIELD_TYPE_CHOICES:
            errors.append(
                f'Рядок {index}: невідомий тип "{field_type}". Доступно: text, textarea, email, number, url, participants.'
            )
            continue

        if is_required not in {'required', 'optional'}:
            errors.append(f'Рядок {index}: обов\'язковість має бути required або optional.')
            continue

        if any(item['key'] == field_key for item in config):
            errors.append(f'Рядок {index}: код поля "{field_key}" вже використовується.')
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


def parse_schedule_definition(raw_value):
    config = []
    errors = []

    for index, raw_line in enumerate((raw_value or '').splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = [part.strip() for part in line.split('|', 2)]
        if len(parts) < 2:
            errors.append(f'Рядок {index}: потрібно вказати дату, час і назву події.')
            continue

        raw_datetime = parts[0]
        title = parts[1]
        description = parts[2] if len(parts) > 2 else ''

        if not title:
            errors.append(f'Рядок {index}: вкажіть назву події.')
            continue

        try:
            starts_at = datetime.strptime(raw_datetime, '%Y-%m-%dT%H:%M')
        except ValueError:
            errors.append(f'Рядок {index}: некоректна дата або час події.')
            continue

        if timezone.is_naive(starts_at):
            starts_at = timezone.make_aware(starts_at, timezone.get_current_timezone())

        config.append({
            'starts_at': trim_datetime_to_minute(starts_at),
            'title': title,
            'description': description,
        })

    if errors:
        raise ValidationError(errors)

    return config


def serialize_schedule_definition(items):
    lines = []
    for item in items or []:
        starts_at = item.get('starts_at')
        if isinstance(starts_at, datetime):
            starts_at = to_local_form_datetime(starts_at).strftime('%Y-%m-%dT%H:%M')
        lines.append(f"{starts_at}|{item.get('title', '')}|{item.get('description', '')}")
    return '\n'.join(lines)


def trim_datetime_to_minute(value):
    if not isinstance(value, datetime):
        return value
    return value.replace(second=0, microsecond=0)


def to_local_form_datetime(value):
    if not isinstance(value, datetime):
        return value
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return trim_datetime_to_minute(value)


class TournamentForm(forms.ModelForm):
    allowed_contact_methods = forms.MultipleChoiceField(
        required=False,
        label="Доступні месенджери для зв'язку з командою",
        choices=Team.ContactMethod.choices,
        widget=forms.CheckboxSelectMultiple(),
    )
    registration_fields_definition = forms.CharField(
        required=False,
        label='Додаткові поля анкети',
        help_text='Кожен рядок: код_поля|Назва поля|тип|required або optional. Типи: text, textarea, email, number, url.',
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 6}),
    )
    schedule_definition = forms.CharField(
        required=False,
        label='Розклад турніру',
        help_text='Кожен рядок: YYYY-MM-DDTHH:MM|Назва події|Опис події.',
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 6}),
    )
    start_date = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local', 'class': 'form-input'},
        ),
        label='Дата початку',
    )
    end_date = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local', 'class': 'form-input'},
        ),
        label='Дата завершення',
    )
    registration_start = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local', 'class': 'form-input'},
        ),
        label='Початок реєстрації',
    )
    registration_end = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local', 'class': 'form-input'},
        ),
        label='Завершення реєстрації',
    )

    class Meta:
        model = Tournament
        fields = [
            'name',
            'description',
            'registration_form_description',
            'registration_fields_definition',
            'allowed_contact_methods',
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
        schedule_items = []
        if getattr(self.instance, 'pk', None):
            schedule_items = [
                {
                    'starts_at': item.starts_at,
                    'title': item.title,
                    'description': item.description,
                }
                for item in self.instance.schedule_items.all()
            ]
        self.fields['schedule_definition'].initial = serialize_schedule_definition(schedule_items)
        self.fields['allowed_contact_methods'].initial = (
            getattr(self.instance, 'effective_allowed_contact_methods', None)
            or Tournament.DEFAULT_CONTACT_METHODS
        )
        for field_name in [
            'name',
            'description',
            'registration_form_description',
            'registration_fields_definition',
            'schedule_definition',
            'allowed_contact_methods',
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
        schedule_definition = cleaned_data.get('schedule_definition', '')
        allowed_contact_methods = cleaned_data.get('allowed_contact_methods') or []
        cleaned_data['allowed_contact_methods'] = allowed_contact_methods

        try:
            cleaned_data['registration_fields_config'] = parse_registration_fields_definition(
                registration_fields_definition
            )
        except ValidationError as exc:
            for error in exc.messages:
                self.add_error('registration_fields_definition', error)

        try:
            cleaned_data['schedule_items_config'] = parse_schedule_definition(schedule_definition)
        except ValidationError as exc:
            for error in exc.messages:
                self.add_error('schedule_definition', error)

        if not allowed_contact_methods:
            self.add_error('allowed_contact_methods', "Залиште принаймні один спосіб зв'язку для команди.")

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
                self.add_error(field_name, 'Це поле є обов’язковим для опублікованого турніру.')

        if not cleaned_data.get('schedule_items_config'):
            self.add_error('schedule_definition', 'Для опублікованого турніру додайте хоча б одну подію розкладу.')

        if registration_start and registration_end and registration_start >= registration_end:
            self.add_error('registration_end', 'Завершення реєстрації має бути пізніше за початок реєстрації.')

        if registration_end and start_date and registration_end > start_date:
            self.add_error('registration_end', 'Реєстрація має завершуватися до початку турніру.')

        if start_date and end_date and end_date <= start_date:
            self.add_error('end_date', 'Турнір має завершуватися після початку.')

        if (
            min_team_members is not None
            and max_team_members is not None
            and min_team_members > max_team_members
        ):
            self.add_error('max_team_members', 'Максимальна кількість людей у команді має бути не меншою за мінімальну.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.registration_fields_config = self.cleaned_data.get('registration_fields_config', [])
        instance.allowed_contact_methods = self.cleaned_data.get(
            'allowed_contact_methods',
            Tournament.DEFAULT_CONTACT_METHODS,
        )
        if commit:
            instance.save()
            self.save_m2m()
            instance.schedule_items.all().delete()
            schedule_items = self.cleaned_data.get('schedule_items_config', [])
            if schedule_items:
                TournamentScheduleItem.objects.bulk_create(
                    [
                        TournamentScheduleItem(
                            tournament=instance,
                            starts_at=item['starts_at'],
                            title=item['title'],
                            description=item.get('description', ''),
                            position=index,
                        )
                        for index, item in enumerate(schedule_items)
                    ]
                )
        return instance


class TeamForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_contact_method'].required = False
        self.fields['preferred_contact_value'].required = False
        if self.instance and self.instance.pk:
            if not self.initial.get('preferred_contact_method'):
                self.initial['preferred_contact_method'] = self.instance.effective_contact_method
            if not self.initial.get('preferred_contact_value'):
                self.initial['preferred_contact_value'] = self.instance.effective_contact_value

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['captain_name'] = (cleaned_data.get('captain_name') or '').strip()
        cleaned_data['captain_email'] = (cleaned_data.get('captain_email') or '').strip().lower()
        cleaned_data['school'] = (cleaned_data.get('school') or '').strip()
        cleaned_data['preferred_contact_value'] = (cleaned_data.get('preferred_contact_value') or '').strip()

        try:
            cleaned_data['school'] = validate_school_name(cleaned_data.get('school'))
        except ValidationError as exc:
            self.add_error('school', exc)

        preferred_contact_method = cleaned_data.get('preferred_contact_method') or ''
        preferred_contact_value = cleaned_data.get('preferred_contact_value') or ''
        if not preferred_contact_method:
            self.add_error('preferred_contact_method', "Оберіть зручний спосіб зв'язку.")
        if not preferred_contact_value:
            self.add_error('preferred_contact_value', "Вкажіть контакт для зв'язку.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        preferred_contact_method = self.cleaned_data.get('preferred_contact_method') or ''
        preferred_contact_value = (self.cleaned_data.get('preferred_contact_value') or '').strip()
        instance.preferred_contact_method = preferred_contact_method or None
        instance.preferred_contact_value = preferred_contact_value or None
        instance.telegram = preferred_contact_value if preferred_contact_method == Team.ContactMethod.TELEGRAM else None
        instance.discord = preferred_contact_value if preferred_contact_method == Team.ContactMethod.DISCORD else None
        instance.viber = preferred_contact_value if preferred_contact_method == Team.ContactMethod.VIBER else None
        if commit:
            instance.save()
            self.save_m2m()
        return instance

    class Meta:
        model = Team
        fields = [
            'name',
            'captain_name',
            'captain_email',
            'school',
            'preferred_contact_method',
            'preferred_contact_value',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'captain_name': forms.TextInput(attrs={'class': 'form-input'}),
            'captain_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'school': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_contact_method': forms.Select(attrs={'class': 'form-input'}),
            'preferred_contact_value': forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': "@team, username#0001, +380...",
                }
            ),
        }
        labels = {
            'captain_name': "Ім'я контактної особи (капітан)",
            'captain_email': 'Електронна пошта контактної особи (капітан)',
            'preferred_contact_method': "Зручний спосіб зв'язку",
            'preferred_contact_value': "Контакт для зв'язку",
        }


class ParticipantForm(forms.ModelForm):
    def clean_full_name(self):
        return (self.cleaned_data.get('full_name') or '').strip()

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()

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
            label="Ім'я контактної особи (капітан)",
            widget=forms.TextInput(attrs={'class': 'form-input'}),
        )
        self.fields['captain_email'] = forms.EmailField(
            label='Електронна пошта контактної особи (капітан)',
            widget=forms.EmailInput(attrs={'class': 'form-input'}),
        )
        self.fields['school'] = forms.CharField(
            required=False,
            label='Школа',
            widget=forms.TextInput(attrs={'class': 'form-input'}),
        )
        self.fields['preferred_contact_method'] = forms.ChoiceField(
            required=True,
            label="Зручний спосіб зв'язку",
            choices=[],
            widget=forms.Select(attrs={'class': 'form-input'}),
        )
        self.fields['preferred_contact_value'] = forms.CharField(
            required=False,
            label="Контакт для зв'язку",
            widget=forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': "@team, username#0001, +380...",
                }
            ),
        )

        allowed_contact_methods = (
            self.tournament.effective_allowed_contact_methods if self.tournament else Tournament.DEFAULT_CONTACT_METHODS
        )
        self.fields['preferred_contact_method'].choices = [
            ('', 'Оберіть спосіб'),
            *[
                (value, label)
                for value, label in Team.ContactMethod.choices
                if value in allowed_contact_methods
            ],
        ]

        if existing_team is not None:
            self.fields['team_name'].initial = existing_team.name
            self.fields['captain_name'].initial = existing_team.captain_name
            self.fields['captain_email'].initial = existing_team.captain_email
            self.fields['school'].initial = existing_team.school
            if existing_team.effective_contact_method in allowed_contact_methods:
                self.fields['preferred_contact_method'].initial = existing_team.effective_contact_method
            self.fields['preferred_contact_value'].initial = existing_team.effective_contact_value
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
        cleaned_data['preferred_contact_method'] = (cleaned_data.get('preferred_contact_method') or '').strip()
        cleaned_data['preferred_contact_value'] = (cleaned_data.get('preferred_contact_value') or '').strip()

        if not cleaned_data['team_name']:
            self.add_error('team_name', 'Вкажіть назву команди.')
        if not cleaned_data['captain_name']:
            self.add_error('captain_name', "Вкажіть ім'я контактної особи (капітана).")
        if not cleaned_data['captain_email']:
            self.add_error('captain_email', 'Вкажіть електронну пошту контактної особи (капітана).')
        try:
            cleaned_data['school'] = validate_school_name(cleaned_data.get('school'))
        except ValidationError as exc:
            self.add_error('school', exc)
        if not cleaned_data['preferred_contact_method']:
            self.add_error('preferred_contact_method', "Оберіть зручний спосіб зв'язку.")
        if not cleaned_data['preferred_contact_value']:
            self.add_error('preferred_contact_value', "Вкажіть контакт для зв'язку.")

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
            'preferred_contact_method': self.cleaned_data.get('preferred_contact_method', ''),
            'preferred_contact_value': self.cleaned_data.get('preferred_contact_value', ''),
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
    start_at = forms.DateTimeField(
        required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local', 'class': 'form-input'},
        ),
        label='Початок завдання',
    )
    deadline = forms.DateTimeField(
        required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local', 'class': 'form-input'},
        ),
        label='Дедлайн здачі',
    )

    class Meta:
        model = Task
        fields = [
            'tournament',
            'title',
            'description',
            'requirements',
            'must_have',
            'start_at',
            'deadline',
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
            'start_at',
            'deadline',
            'official_solution',
        ]:
            self.fields[field_name].required = False

        if tournament is not None:
            self.fields['tournament'].initial = tournament
            self.fields['tournament'].widget = forms.HiddenInput()
            self.fields['tournament'].queryset = Tournament.objects.filter(id=tournament.id)
            if not getattr(self.instance, 'pk', None):
                self.fields['start_at'].initial = to_local_form_datetime(tournament.start_date)
                self.fields['deadline'].initial = to_local_form_datetime(tournament.end_date)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('is_draft'):
            return cleaned_data

        required_fields = {
            'title': (cleaned_data.get('title') or '').strip(),
            'description': (cleaned_data.get('description') or '').strip(),
            'requirements': (cleaned_data.get('requirements') or '').strip(),
            'must_have': (cleaned_data.get('must_have') or '').strip(),
            'start_at': cleaned_data.get('start_at'),
            'deadline': cleaned_data.get('deadline'),
        }
        for field_name, value in required_fields.items():
            if not value:
                self.add_error(field_name, 'Це поле є обов’язковим для опублікованого завдання.')

        start_at = cleaned_data.get('start_at')
        deadline = cleaned_data.get('deadline')
        tournament = cleaned_data.get('tournament') or getattr(self.instance, 'tournament', None)
        normalized_start_at = trim_datetime_to_minute(start_at)
        normalized_deadline = trim_datetime_to_minute(deadline)
        tournament_start = trim_datetime_to_minute(getattr(tournament, 'start_date', None))
        tournament_end = trim_datetime_to_minute(getattr(tournament, 'end_date', None))

        if normalized_start_at and normalized_deadline and normalized_deadline <= normalized_start_at:
            self.add_error('deadline', 'Дедлайн має бути пізніше за старт завдання.')

        if tournament is not None:
            if tournament_start and normalized_start_at and normalized_start_at < tournament_start:
                self.add_error('start_at', 'Старт завдання не може бути раніше старту турніру.')
            if tournament_end and normalized_deadline and normalized_deadline > tournament_end:
                self.add_error('deadline', 'Дедлайн завдання не може бути пізніше завершення турніру.')

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
            self.fields['tournament'].empty_label = 'Усі турніри / загальне оголошення'
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
            self.fields['tournament'].empty_label = 'Глобальний шаблон для всіх турнірів'



