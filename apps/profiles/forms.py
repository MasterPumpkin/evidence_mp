from django import forms
from django.contrib.auth.models import User
from .models import UserProfile

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    # def __init__(self, *args, **kwargs):
    #     user = kwargs.get('instance', None)
    #     super().__init__(*args, **kwargs)
        # Skupiny a třídu nepovolíme editovat, ty jsou v adminu.
        # Nic speciálního nepotřebujeme tady, jen fields = ...


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['title', 'abbreviation']  # plus cokoliv jiného (class_name, obor…)
