from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.profiles.models import UserProfile
from ..models import Milestone, Project, ControlCheck, ScoringScheme
from django.utils import timezone
from django.utils.timezone import now
from django.db.models import Q
from ..forms import (
    ControlCheckForm,
    ProjectNotesForm, ProjectOpponentForm,
    ProjectAssignmentForm,
    StudentProjectForm,
    TeacherProjectForm
)
import csv
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
import json

@login_required
@require_POST
def update_milestone_status(request, milestone_id):
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        # print(f"Milestone ID: {milestone_id}")  # Debug výpis
        # print(f"New status: {new_status}")  # Debug výpis

        if new_status not in dict(Milestone.STATUS_CHOICES).keys():
            # print("Invalid status")  # Debug výpis
            return JsonResponse({'success': False, 'error': 'Invalid status'})

        milestone = Milestone.objects.get(id=milestone_id)
        milestone.status = new_status
        milestone.save()
        # print("Status updated successfully")  # Debug výpis
        return JsonResponse({'success': True})

    except Milestone.DoesNotExist:
        # print("Milestone not found")  # Debug výpis
        return JsonResponse({'success': False, 'error': 'Milestone not found'})

    except json.JSONDecodeError:
        # print("Invalid JSON")  # Debug výpis
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    except Exception as e:
        # print(f"Error: {e}")  # Debug výpis
        return JsonResponse({'success': False, 'error': str(e)})



class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'

    def get(self, request, *args, **kwargs):
        query_params = request.GET.copy()

        # Načtení uživatelských preferencí pro my_projects
        user_prefs = getattr(self.request.user, 'preferences', None)
        default_my_projects = '1' if user_prefs and user_prefs.pref_myprojects_default else '0'

        # Pokud uživatel poprvé vstupuje na stránku (není v URL parametr), použij preference
        if 'my_projects' not in request.GET:
            query_params['my_projects'] = default_my_projects
            return redirect(f"{request.path}?{query_params.urlencode()}")
        
        # Nastavení výchozí třídy na prázdnou hodnotu, pokud není zadaná
        if 'class' not in query_params or query_params['class'] == 'None':
            query_params['class'] = ''

        # Přesměrování pouze pokud se změnily GET parametry
        if query_params.urlencode() != request.META['QUERY_STRING']:
            return redirect(f"{request.path}?{query_params.urlencode()}")

        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Project.objects.all()

        # Zpracování parametru "Pouze moje projekty"
        my_projects = self.request.GET.get('my_projects', '0')

        if my_projects == '1':
            qs = qs.filter(Q(leader=self.request.user) | Q(opponent=self.request.user))

        # Pokud je user ve skupině 'Student', zobrazí jen své projekty
        if user_in_group(self.request.user, 'Student'):
            qs = qs.filter(student=self.request.user)
        
        # Filtr třídy (pokud není zadána, použij default)
        class_name = self.request.GET.get('class', '')
        if class_name:
            qs = qs.filter(student__userprofile__class_name=class_name)

        # Filtr podle stavu projektu
        if status := self.request.GET.get('status'):
            qs = qs.filter(status=status)

        # Filtr podle vedoucího
        if leader_id := self.request.GET.get('leader'):
            qs = qs.filter(leader_id=leader_id)

        # Filtr podle oponenta
        if opponent_id := self.request.GET.get('opponent'):
            qs = qs.filter(opponent_id=opponent_id)

        # Řazení výsledků
        if ordering := self.request.GET.get('ordering'):
            qs = qs.order_by(ordering)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            user_prefs = self.request.user.preferences
            context['default_my_projects'] = '1' if user_prefs.pref_myprojects_default else '0'
        except AttributeError:
            context['default_my_projects'] = '0'
            # print(f"Uživatel {self.request.user} nemá nastavené preference!")

        # print(f"Uživatel: {self.request.user}, Preference: {context['default_my_projects']}")

        context['all_teachers'] = User.objects.filter(groups__name='Teacher')
        context['all_classes'] = UserProfile.objects.exclude(class_name='').values_list('class_name', flat=True).distinct().order_by('class_name')

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()

        return context



class TeacherProjectCreateView(CreateView):
    model = Project
    form_class = TeacherProjectForm
    template_name = 'projects/project_form.html'

    def dispatch(self, request, *args, **kwargs):
        # Kontrola, zda user je teacher/superuser
        if not (request.user.is_superuser or request.user.groups.filter(name='Teacher').exists()):
            messages.error(request, "Nemáte oprávnění zakládat projekt jako učitel.")
            return redirect('projects:list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Při uložení:
        # 1. Nastavíme scoreboard (active=True)
        try:
            scheme = ScoringScheme.objects.get(active=True)
            form.instance.scheme = scheme
        except ScoringScheme.DoesNotExist:
            messages.error(self.request, "Není definován aktivní scoreboard.")
            return redirect('projects:list')

        # 2. Leader = request.user
        form.instance.leader = self.request.user

        # 3. Student = None (zatím)
        form.instance.student = None

        form.instance.status = 'approved'  # schváleno učitelem

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('projects:detail', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()

        return context 


class TeacherProjectUpdateView(UpdateView):
    model = Project
    form_class = TeacherProjectForm
    template_name = 'projects/project_form.html'

    def dispatch(self, request, *args, **kwargs):
        # jen teacher/superuser
        if not (request.user.is_superuser or request.user.groups.filter(name='Teacher').exists()):
            messages.error(request, "Nemáte oprávnění.")
            return redirect('projects:list')
        return super().dispatch(request, *args, **kwargs)
    
    def get_initial(self):
        initial = super().get_initial()
        project = self.get_object()

        # Pokud existuje uložené datum, předvyplníme ho
        if project.delivery_work_date:
            initial['delivery_work_date'] = project.delivery_work_date.strftime('%Y-%m-%d')
        
        if project.delivery_documentation_date:
            initial['delivery_documentation_date'] = project.delivery_documentation_date.strftime('%Y-%m-%d')

        return initial
    
        
    def form_valid(self, form):
        project = self.get_object()

        # Povolit změnu studenta pouze pokud ještě není přiřazen
        if project.student is None or form.cleaned_data.get('student') == project.student:
            # Aktualizujeme data předání z formuláře
            project.delivery_work_date = form.cleaned_data.get('delivery_work_date')
            project.delivery_documentation_date = form.cleaned_data.get('delivery_documentation_date')

            # Uložíme aktualizovaný projekt
            project.save()

            return super().form_valid(form)
        else:
            messages.error(self.request, "Studenta nelze změnit.")
            return redirect('projects:detail', args=[self.object.pk])


    def get_success_url(self):
        return reverse('projects:detail', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()

        return context 
    

class StudentProjectCreateView(CreateView):
    model = Project
    form_class = StudentProjectForm
    template_name = 'projects/project_form.html'

    def dispatch(self, request, *args, **kwargs):
        # Kontrola, zda user je student
        # (nebo neděláme? Záleží na tobě)
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        # scoreboard
        try:
            scheme = ScoringScheme.objects.get(active=True)
            form.instance.scheme = scheme
        except ScoringScheme.DoesNotExist:
            messages.error(self.request, "Není definován aktivní scoreboard.")
            return redirect('projects:list')

        # Student = request.user
        form.instance.student = self.request.user

        existing = Project.objects.filter(student=self.request.user).exists()
        if existing:
            messages.error(self.request, "Už máte jeden projekt založen.")
            return redirect('projects:list')
        
        # Leader/opponent = None
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('projects:detail', args=[self.object.pk])


class StudentProjectUpdateView(UpdateView):
    model = Project
    form_class = StudentProjectForm
    template_name = 'projects/project_form.html'

    def dispatch(self, request, *args, **kwargs):
        project = self.get_object()

        # (1) Kontrola, zda user == project.student
        if project.student != request.user:
            messages.error(request, "Nemáte oprávnění upravovat tento projekt.")
            return redirect('projects:detail', pk=project.pk)

        # (2) Kontrola, zda projekt NENÍ schválen (tj. leader existuje / status=approved)
        if project.leader is not None or project.status == 'approved':
            messages.error(request, "Projekt již byl schválen, nelze upravovat.")
            return redirect('projects:detail', pk=project.pk)

        # (3) Kontrola deadline
        scheme = project.scheme
        if scheme and scheme.student_edit_deadline:
            if timezone.now() > scheme.student_edit_deadline:
                messages.error(request, "Vypršel termín pro editaci projektu.")
                return redirect('projects:detail', pk=project.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('projects:detail', args=[self.object.pk])


def user_in_group(user, group_name):
    """Pomocná funkce, která zjistí, jestli je uživatel ve skupině group_name."""
    return user.is_authenticated and user.groups.filter(name=group_name).exists()


@login_required
def approve_project(request, pk):
    """Učitel schválí projekt, stane se leaderem, status = 'approved'."""
    project = get_object_or_404(Project, pk=pk)

    # Je vyžadováno přihlášení
    if not request.user.is_authenticated:
        return redirect('login')  # nebo vrátit 403?

    # Zkontrolujeme, zda je user ve skupině Teacher:
    if not user_in_group(request.user, 'Teacher'):
        messages.error(request, "Jen učitel může schvalovat projekty.")
        return redirect('projects:detail', pk=pk)

    # Nastavíme leadera + status
    project.leader = request.user
    project.status = 'approved'
    project.save()

    messages.success(request, "Projekt schválen. Jste jeho vedoucím.")
    return redirect('projects:detail', pk=pk)


def resign_as_leader(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.leader == request.user:
        project.leader = None
        project.status = 'pending_approval'
        project.save()
    return redirect('projects:detail', pk=pk)


def resign_as_opponent(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.opponent == request.user:
        project.opponent = None
        project.save()
    return redirect('projects:detail', pk=pk)



class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'projects/project_detail.html'
    context_object_name = 'project'
    # Tady pak omezíme, aby student mohl vidět jen svůj projekt
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context_object_name = 'project'
        project = context[context_object_name]

        # Přidání dat pro šablonu
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()
        context['can_edit'] = (
            (user.groups.filter(name='Student').exists() and project.student == user and project.status == 'pending_approval') or
            (user.groups.filter(name='Teacher').exists() and project.leader == user and project.status == 'approved')
        )

        # Přidání možných stavů milníků do kontextu
        context['milestone_status_choices'] = Milestone.STATUS_CHOICES

        # Připravíme milníky s atributem `short_note`
        milestones_with_short_notes = []
        for milestone in project.milestones.all():
            milestones_with_short_notes.append({
                'title': milestone.title,
                'deadline': milestone.deadline,
                # 'status': milestone.get_status_display(),
                'status': milestone.status,
                'short_note': milestone.note[:20] + '...' if len(milestone.note) > 20 else milestone.note,
            })

        # Přidání milníků do kontextu
        context['milestones'] = milestones_with_short_notes
        context['now'] = now()

        return context

class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    fields = ['title', 'description']
    template_name = 'projects/project_form.html'

    def dispatch(self, request, *args, **kwargs):
        # Jen student smí zakládat projekt
        if not user_in_group(request.user, 'Student'):
            messages.error(request, "Nemůžete zakládat projekty.")
            return redirect('projects:list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Při uložení nastavíme student = request.user."""
        form.instance.student = self.request.user
        existing = Project.objects.filter(student=self.request.user).exists()
        if existing:
            messages.error(self.request, "Už máte jeden projekt založen.")
            return redirect('projects:list')
        return super().form_valid(form)

    def get_success_url(self):
        return '/projects/'  # nebo reverse('projects:list')



class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    fields = ['title', 'description']  # atd.
    template_name = 'projects/project_form.html'

    def dispatch(self, request, *args, **kwargs):
        project = self.get_object()

        # Kontrola oprávnění: může editovat student (vlastník) nebo vedoucí projektu
        is_student_owner = user_in_group(request.user, 'Student') and project.student == request.user
        is_project_leader = user_in_group(request.user, 'Teacher') and project.leader == request.user

        if not (is_student_owner or is_project_leader):
            messages.error(request, "Nemáte oprávnění upravovat tento projekt.")
            return redirect(project)

        # Pokud projekt není ve stavu `pending_approval`, kontrola pro studenta
        if is_student_owner and project.status != 'pending_approval':
            messages.error(request, "Projekt už byl schválen, nelze jej editovat.")
            return redirect(project)
        

        # if project.edit_deadline and timezone.now() > project.edit_deadline:
        #     messages.error(request, "Vypršela lhůta pro úpravu projektu.")
        #     # return redirect('projects:detail', pk=project.pk)
        #     return redirect(project)

        return super().dispatch(request, *args, **kwargs)
        # return redirect(project)

    def get_success_url(self):
        # return '/projects/'
        return reverse('projects:detail', args=[self.object.pk])



@login_required
def delete_controlcheck(request, controlcheck_id):
    """
    Odstraní kontrolu, pokud má uživatel oprávnění (je vedoucí projektu).
    """
    controlcheck = get_object_or_404(ControlCheck, id=controlcheck_id)
    
    # Kontrola oprávnění: uživatel musí být vedoucí projektu
    if controlcheck.project.leader != request.user:
        return HttpResponseForbidden("Nemáte oprávnění odstranit tuto kontrolu.")

    controlcheck.delete()
    messages.success(request, "Kontrola byla úspěšně odstraněna.")
    return redirect('projects:detail', pk=controlcheck.project.id)


class ControlCheckCreateView(LoginRequiredMixin, CreateView):
    model = ControlCheck
    form_class = ControlCheckForm
    template_name = 'projects/controlcheck_form.html'

    def dispatch(self, request, *args, **kwargs):
        # Ověříme, že user je vedoucí
        project_id = self.kwargs['project_id']
        project = get_object_or_404(Project, id=project_id)
        if not (request.user == project.leader or request.user.is_superuser):
            messages.error(request, "Nemáte oprávnění přidávat kontroly.")
            return redirect('projects:detail', pk=project_id)
        self.project = project
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)

    def get_success_url(self):
        # return redirect('projects:detail', pk=self.project.pk)
        return reverse('projects:detail', kwargs={'pk': self.project.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()

        return context 


class ControlCheckUpdateView(LoginRequiredMixin, UpdateView):
    model = ControlCheck
    form_class = ControlCheckForm
    template_name = 'projects/controlcheck_form.html'

    def dispatch(self, request, *args, **kwargs):
        check = self.get_object()
        project = check.project
        if not (request.user == project.leader or request.user.is_superuser):
            messages.error(request, "Nemáte oprávnění upravovat tuto kontrolu.")
            return redirect('projects:detail', pk=project.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        # Vrátíme se do detailu projektu
        check = self.object
        # return redirect('projects:detail', pk=check.project.pk)
        return reverse('projects:detail', kwargs={'pk': check.project.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()

        return context 


class ProjectNotesUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectNotesForm
    template_name = 'projects/project_notes_form.html'

    def dispatch(self, request, *args, **kwargs):
        project = self.get_object()
        # Přístup jen pro vedoucího nebo superusera
        if not (request.user == project.leader or request.user.is_superuser):
            messages.error(request, "Nemáte oprávnění upravovat interní poznámky.")
            return redirect('projects:detail', pk=project.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('projects:detail', args=[self.object.pk])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()

        return context 
    


class ProjectAssignmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectAssignmentForm
    template_name = 'projects/project_assignment_form.html'

    def dispatch(self, request, *args, **kwargs):
        project = self.get_object()
        # Přístup jen pro vedoucího nebo superusera
        if not (request.user == project.leader or request.user.is_superuser):
            messages.error(request, "Nemáte oprávnění upravovat zadání projektu.")
            return redirect('projects:detail', pk=project.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('projects:detail', args=[self.object.pk])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()

        return context 
  

@login_required
def take_opponent_role(request, pk):
    """
    Učitel klikne na tlačítko v detailu -> stane se oponentem projektu.
    """
    project = get_object_or_404(Project, pk=pk)

    # Musí být učitel (nebo superuser)
    if not request.user.groups.filter(name='Teacher').exists() and not request.user.is_superuser:
        messages.error(request, "Nemáte oprávnění stát se oponentem.")
        return redirect('projects:detail', pk=pk)

    # Nastavím project.opponent = request.user
    project.opponent = request.user
    project.save()
    messages.success(request, "Stali jste se oponentem projektu.")
    return redirect('projects:detail', pk=pk)


class ProjectOpponentUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectOpponentForm
    template_name = 'projects/project_opponent_form.html'

    def dispatch(self, request, *args, **kwargs):
        project = self.get_object()
        # Povolíme jen vedoucímu (nebo adminovi) vybrat oponenta
        if not (request.user == project.leader or request.user.is_superuser):
            messages.error(request, "Nemáte oprávnění přiřadit oponenta.")
            return redirect('projects:detail', pk=project.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('projects:detail', args=[self.object.pk])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()

        return context 



@login_required
def generate_consultations(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not (request.user == project.leader or request.user.is_superuser):
        messages.error(request, "Nemáte oprávnění generovat konzultace.")
        return redirect('projects:detail', pk=pk)

    scheme = project.scheme
    if not scheme:
        messages.error(request, "Není přiřazen scoreboard/ročník. Nelze generovat termíny.")
        return redirect('projects:detail', pk=pk)

    # Najít user preferences
    prefs = getattr(request.user, 'preferences', None)

    # Vytvořit 3 záznamy v milnících nebo ControlCheck (jak preferuješ),
    # tady ukázka s ControlCheck
    # from .models import ControlCheck
    # Example
    texts = [
        prefs.consultation_text1 if prefs else "",
        prefs.consultation_text2 if prefs else "",
        prefs.consultation_text3 if prefs else "",
    ]
    deadlines = [
        scheme.control_deadline1,
        scheme.control_deadline2,
        scheme.control_deadline3,
    ]

    for i in range(3):
        if deadlines[i]:
            ControlCheck.objects.create(
                project=project,
                date=deadlines[i],
                content=texts[i] or f"Konzultace #{i+1}",
                evaluation=""
            )
    messages.success(request, "Konzultace vygenerovány.")
    return redirect('projects:detail', pk=pk)
