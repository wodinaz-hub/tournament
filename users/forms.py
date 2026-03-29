from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser


class UniqueEmailMixin:
    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            return email

        queryset = CustomUser.objects.filter(email__iexact=email)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError('Користувач з таким email уже існує.')
        return email


class UniqueUsernameMixin:
    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            return username

        queryset = CustomUser.objects.filter(username__iexact=username)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError('Користувач з таким логіном уже існує.')
        return username


class RegisterForm(UniqueEmailMixin, UniqueUsernameMixin, UserCreationForm):
    username = forms.CharField(
        label='Логін',
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )

    email = forms.EmailField(
        label='Електронна пошта',
        widget=forms.EmailInput(attrs={'class': 'form-input'})
    )

    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )

    password2 = forms.CharField(
        label='Підтвердження пароля',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']


class LoginForm(AuthenticationForm):

    username = forms.CharField(
        label='Логін',
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )

    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )


class AdminCreateUserForm(UniqueEmailMixin, UniqueUsernameMixin, UserCreationForm):
    username = forms.CharField(
        label='Логін',
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )

    email = forms.EmailField(
        label='Електронна пошта',
        widget=forms.EmailInput(attrs={'class': 'form-input'})
    )

    role = forms.ChoiceField(
        label='Роль',
        choices=CustomUser.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'})
    )

    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )

    password2 = forms.CharField(
        label='Підтвердження пароля',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'role', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        available_roles = kwargs.pop('available_roles', None)
        super().__init__(*args, **kwargs)
        if available_roles is not None:
            self.fields['role'].choices = [
                choice for choice in CustomUser.ROLE_CHOICES
                if choice[0] in available_roles
            ]

