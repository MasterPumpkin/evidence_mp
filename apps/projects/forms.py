from django import forms
from django.contrib.auth.models import User
from .models import Milestone, Project, ControlCheck, LeaderEvaluation, OpponentEvaluation
from ckeditor.widgets import CKEditorWidget
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field

class MilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ['title', 'deadline', 'status', 'note']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
        }
        labels = {
            'title': 'Název milníku',
            'deadline': 'Termín',
            'status': 'Stav',
            'note': 'Poznámka',
        }
        help_texts = {
            'deadline': 'Datum, do kdy je milník plánován',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.deadline:
            self.fields['deadline'].initial = self.instance.deadline.strftime('%Y-%m-%d')



class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'description', 'scheme', 'internal_notes']
        # internal_notes je WYSIWYG, můžeš použít widget CKEditor:
        # widgets = {
        #     'internal_notes': CKEditorWidget(),  # pokud máš django-ckeditor
        # }

class ControlCheckForm(forms.ModelForm):
    class Meta:
        model = ControlCheck
        fields = ['date', 'content', 'evaluation']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
        }

class LeaderEvaluationForm(forms.ModelForm):
    class Meta:
        model = LeaderEvaluation
        fields = [
            'area1_text', 'area1_points',
            'area2_text', 'area2_points',
            'area3_text', 'area3_points'
        ]

class OpponentEvaluationForm(forms.ModelForm):
    class Meta:
        model = OpponentEvaluation
        fields = [
            'area1_text', 'area1_points',
            'area2_text', 'area2_points'
        ]


class ProjectNotesForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['internal_notes']
        widgets = {
           'internal_notes': CKEditorWidget(config_name='default'),
        }
        labels = {
            'internal_notes': '',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('content', label=False),  # Skryje popis pole
        )


class ProjectOpponentForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['opponent']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Omezíme výběr pro opponent jen na učitele
        self.fields['opponent'].queryset = User.objects.filter(groups__name='Teacher')
        self.fields['opponent'].required = False


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        user = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)
        # Skupiny a třídu nepovolíme editovat, ty jsou v adminu.
        # Nic speciálního nepotřebujeme tady, jen fields = ...


class ProjectAssignmentForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['assignment']
        # widgets = {
        #    'internal_notes': CKEditorWidget(config_name='default'),
        # }
        labels = {
            'assignment': '',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('assignment', label=False),  # Skryje popis pole
        )