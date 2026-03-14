from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser


class RegisterForm(UserCreationForm):

    ROLE_CHOICES = [
        ('participant', 'Participant'),
        ('captain', 'Captain'),
        ('jury', 'Jury'),
        ('admin', 'Admin'),
    ]

    username = forms.CharField(
        label='Username',
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )

    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-input'})
    )

    role = forms.ChoiceField(
        label='Role',
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'})
    )

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )

    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'role', 'password1', 'password2']


class LoginForm(AuthenticationForm):

    username = forms.CharField(
        label='Username',
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )

    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )