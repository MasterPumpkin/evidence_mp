from django import forms
from django.contrib.auth.models import User
from .models import Milestone, Project, ControlCheck, LeaderEvaluation, OpponentEvaluation, UserPreferences
from django_ckeditor_5.widgets import CKEditor5Widget
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field
from datetime import date
from apps.projects.models import ScoringScheme

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


class StudentMilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ['title', 'deadline']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
        }
        labels = {
            'title': 'Název milníku',
            'deadline': 'Termín',
        }
        help_texts = {
            'deadline': 'Datum, do kdy je milník plánován',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.deadline:
            self.fields['deadline'].initial = self.instance.deadline.strftime('%Y-%m-%d')


class TeacherProjectForm(forms.ModelForm):
    """Učitel při zakládání projektu vybírá studenta."""
    student = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name='Student'),
        required=False,
        label="Žák",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    delivery_work_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        label=Project._meta.get_field('delivery_work_date').verbose_name,
        help_text=Project._meta.get_field('delivery_work_date').help_text
    )

    delivery_documentation_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        label=Project._meta.get_field('delivery_documentation_date').verbose_name,
        help_text=Project._meta.get_field('delivery_documentation_date').help_text
    )

    class Meta:
        model = Project
        fields = ['title', 'student', 'description', 'assignment', 'delivery_work_date', 'delivery_documentation_date']

    def __init__(self, *args, **kwargs):
        # Získáme extra parametr 'selected_year' a 'user' (přihlášený uživatel)
        selected_year = kwargs.pop('selected_year', None)
        user = kwargs.pop('user', None)
        # Pokud selected_year není předán a je k dispozici předvolba, použijeme ji:
        if not selected_year and user is not None:
            if hasattr(user, 'preferences') and user.preferences.default_year:
                selected_year = user.preferences.default_year
        # Inicializujeme formulář standardním způsobem
        super().__init__(*args, **kwargs)
        # Pokud máme zvolený školní rok, omezíme queryset pro pole 'student'
        if selected_year:
            self.fields['student'].queryset = User.objects.filter(
                groups__name='Student',
                userprofile__school_year=selected_year
            ).order_by('username')
        else:
            self.fields['student'].queryset = User.objects.filter(
                groups__name='Student'
            ).order_by('username')
        # Pokud je již student přiřazen, nastavíme jeho počáteční hodnotu
        if self.instance and self.instance.student:
            self.fields['student'].initial = self.instance.student

        # Přidáme Bootstrap třídu
        self.fields['student'].widget.attrs.update({'class': 'form-control'})




class StudentProjectForm(forms.ModelForm):
    """Student zakládá projekt, nepotřebuje leader/opponent."""
    class Meta:
        model = Project
        fields = ['title', 'description']


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
    export_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        label=LeaderEvaluation._meta.get_field('export_date').verbose_name,
        help_text=LeaderEvaluation._meta.get_field('export_date').help_text
    )
    submission_status = forms.ChoiceField(
        choices=LeaderEvaluation.SUBMISSION_STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        label=LeaderEvaluation._meta.get_field('submission_status').verbose_name,
        help_text=LeaderEvaluation._meta.get_field('submission_status').help_text
    )
    class Meta:
        model = LeaderEvaluation
        fields = [
            'area1_text', 'area1_points',
            'area2_text', 'area2_points',
            'area3_text', 'area3_points',
            'export_date', 'submission_status'
        ]

class OpponentEvaluationForm(forms.ModelForm):
    export_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        label=LeaderEvaluation._meta.get_field('export_date').verbose_name,
        help_text=LeaderEvaluation._meta.get_field('export_date').help_text
    )
    class Meta:
        model = OpponentEvaluation
        fields = [
            'area1_text', 'area1_points',
            'area2_text', 'area2_points',
            'export_date'
        ]


class ProjectNotesForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['internal_notes']
        # widgets = {
        #   'internal_notes': CKEditorWidget(config_name='default'),
        # }
        widgets = {
              "internal_notes": CKEditor5Widget(
                  attrs={"class": "django_ckeditor_5"}, config_name="extends"
              )
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


class UserPreferencesForm(forms.ModelForm):
    class Meta:
        model = UserPreferences
        fields = [
            'pref_myprojects_default',
            'default_year',
            'email_notifications',
            'consultation_text1',
            'consultation_text2',
            'consultation_text3',
            'signature',
        ]
        widgets = {
            'signature': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Načteme všechny dostupné ScoringScheme (školní roky), seřazené podle roku
        schemes = ScoringScheme.objects.all().order_by('year')
        # Vytvoříme seznam tuple ve formátu (year, year)
        choices = [(scheme.year, scheme.year) for scheme in schemes]
        # Nastavíme widget pro pole default_year jako Select s danými volbami
        self.fields['default_year'].widget = forms.Select(choices=choices)
        

class DateInputForm(forms.Form):
    handover_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',  # HTML5 atribut pro kalendář
            'class': 'form-control',
        }),
        label="Datum předání",
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Automatické nastavení dnešního data při vykreslení formuláře
        self.fields['handover_date'].initial = date.today().strftime('%Y-%m-%d')



class ExportForm(forms.Form):
    handover_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Datum předání",
        required=True
    )

    SUBMISSION_CHOICES = [
        ('on_time', 'Odevzdal v řádném termínu'),
        ('late', 'Odevzdal v náhradním termínu'),
        ('not_submitted', 'Neodevzdal v termínu'),
    ]

    submission_status = forms.ChoiceField(
        choices=SUBMISSION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Stav odevzdání",
        required=False  # Volitelné pole
    )

    def __init__(self, *args, **kwargs):
        export_type = kwargs.pop('export_type', None)
        super().__init__(*args, **kwargs)

        # Automatické nastavení dnešního data při vykreslení formuláře
        self.fields['handover_date'].initial = date.today().strftime('%Y-%m-%d')

        # Skryjeme pole submission_status pokud exportujeme konzultační list nebo posudek oponenta
        if export_type in ['export_opponent_eval', 'export_consultation_list']:
            self.fields.pop('submission_status')
