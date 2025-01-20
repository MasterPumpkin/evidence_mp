import csv
import io
from django.contrib.auth.models import User, Group
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.profiles.models import UserProfile
from .models import Project, Milestone, ControlCheck, LeaderEvaluation, OpponentEvaluation, UserPreferences, ScoringScheme
from django.utils import timezone
from django.utils.timezone import now
from django.utils.decorators import method_decorator
from django.db.models import Q
from .forms import (
    MilestoneForm,ProjectForm, ControlCheckForm,
    LeaderEvaluationForm, OpponentEvaluationForm,
    ProjectNotesForm, ProjectOpponentForm,
    UserUpdateForm, ProjectAssignmentForm,
    UserPreferencesForm, StudentProjectForm,
    TeacherProjectForm, StudentMilestoneForm
)
import csv
from django.http import HttpResponse, HttpResponseForbidden
from datetime import datetime
from django.urls import reverse
from django.contrib.auth.models import User
from docxtpl import DocxTemplate
from django.http import HttpResponse
from django.template.defaultfilters import date as date_filter
import datetime
import openpyxl


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
    
    def form_valid(self, form):
        project = self.get_object()

        # Povolit změnu studenta pouze pokud ještě není přiřazen
        if project.student is None or form.cleaned_data.get('student') == project.student:
            return super().form_valid(form)
        else:
            messages.error(self.request, "Studenta nelze změnit.")
            return redirect('projects:detail', args=[self.object.pk])

    def get_success_url(self):
        return reverse('projects:detail', args=[self.object.pk])


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



@login_required
def export_project_docx(request, pk):
    project = get_object_or_404(Project, pk=pk)

    # Pouze vedoucí nebo superuser (nebo kdokoli, pokud je to volně přístupné)
    if not (request.user == project.leader or request.user.is_superuser):
        messages.error(request, "Nemáte oprávnění exportovat.")
        return redirect('projects:detail', pk=pk)

    # Zjištění oboru studenta
    student_profile = getattr(project.student, 'userprofile', None)
    branch = student_profile.study_branch if student_profile else 'E'  # pokud by student neměl profil, fallback = 'E'

    # Podle oboru vybereme šablonu
    if branch == 'IT':
        doc = DocxTemplate("templates/docx/zadani_projektu_IT.docx")
    else:
        doc = DocxTemplate("templates/docx/zadani_projektu_E.docx")

    # Připrav data pro šablonu
    class_name = student_profile.class_name if student_profile else ""

    # Získání kontrol
    controls_data = []
    for c in project.controls.all():
        controls_data.append({
            'date': c.date.strftime("%d.%m.%Y"),  # formátování
            'content': c.content,
            'evaluation': c.evaluation,
        })

    leader_eval = project.leader_eval if hasattr(project, 'leader_eval') else None
    opponent_eval = project.opponent_eval if hasattr(project, 'opponent_eval') else None

    context = {
        'student_name': f"{project.student.first_name} {project.student.last_name}",
        'class_name': class_name,
        'leader_name': project.leader.get_full_name() if project.leader else "",
        'opponent_name': project.opponent.get_full_name() if project.opponent else "",
        'project_title': project.title,
        'project_description': project.description,

        'controls': controls_data,

        'leader_eval': {
            'area1_text': leader_eval.area1_text if leader_eval else "",
            'area1_points': leader_eval.area1_points if leader_eval else 0,
            # area2, area3 ...
        } if leader_eval else {},
        'opponent_eval': {
            'area1_text': opponent_eval.area1_text if opponent_eval else "",
            'area1_points': opponent_eval.area1_points if opponent_eval else 0,
            # area2 ...
        } if opponent_eval else {},
    }

    doc.render(context)

    # Vygenerujeme soubor
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename=\"projekt_{pk}.docx\"'
    doc.save(response)
    return response



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


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'
    
    def get_queryset(self):
        qs = super().get_queryset()

        user_prefs = getattr(self.request.user, 'userpreferences', None)
        
        if user_prefs and user_prefs.pref_myprojects_default and 'my_projects' not in self.request.GET:
            # Force the param
            # Když user poprvé načte stránku, nastavíme param 'my_projects=1'
            self.request.GET._mutable = True
            self.request.GET['my_projects'] = '1'
            self.request.GET._mutable = False

        # Pokud je user ve skupině 'Student', zobrazí jen své projekty
        if user_in_group(self.request.user, 'Student'):
            qs = qs.filter(student=self.request.user)
        # Pokud je user ve skupině 'Teacher', zobrazí všechny (např.)

        # -- Filtrování podle třídy:
        class_name = self.request.GET.get('class')
        if class_name:
            # student__userprofile__class_name = "3.A" například
            qs = qs.filter(student__userprofile__class_name=class_name)

        # -- Filtrování podle stavu projektu:
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        # -- Filtrování podle vedoucího:
        leader_id = self.request.GET.get('leader')
        if leader_id:
            qs = qs.filter(leader_id=leader_id)

        # -- Filtrování podle oponenta:
        opponent_id = self.request.GET.get('opponent')
        if opponent_id:
            qs = qs.filter(opponent_id=opponent_id)

        # -- Řazení:
        # v parametru ?ordering=title nebo ?ordering=-created_at atd.
        ordering = self.request.GET.get('ordering')
        valid_order_fields = ['title', '-title', 'created_at', '-created_at', 'status', '-status']
        if ordering in valid_order_fields:
            qs = qs.order_by(ordering)

        # Jen moje projekty
        if self.request.GET.get('my_projects') == '1':
            user = self.request.user
            qs = qs.filter(Q(leader=user) | Q(opponent=user))

        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Seznam učitelů, který už máš:
        context['all_teachers'] = (User.objects
                                   .filter(groups__name='Teacher')
                                   .select_related('userprofile'))

        # Seznam **všech tříd** (distinct), např. z UserProfile:
        context['all_classes'] = (UserProfile.objects
                                  .exclude(class_name='')
                                  .values_list('class_name', flat=True)
                                  .distinct()
                                  .order_by('class_name'))

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()
        
        return context


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

        # Připravíme milníky s atributem `short_note`
        milestones_with_short_notes = []
        for milestone in project.milestones.all():
            milestones_with_short_notes.append({
                'title': milestone.title,
                'deadline': milestone.deadline,
                'status': milestone.get_status_display(),
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


class MilestoneCreateView(CreateView):
    model = Milestone
    form_class = MilestoneForm  # Použití vlastního formuláře
    # fields = ['title', 'deadline', 'status', 'note']
    template_name = 'projects/milestone_form.html'

    def dispatch(self, request, *args, **kwargs):
        # Ověřit, že user je Teacher (vedoucí) atp. 
        if not (request.user.is_authenticated and request.user.groups.filter(name='Teacher').exists()):
            messages.error(request, "Nemáte oprávnění přidávat milníky.")
            return redirect('projects:list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        project_id = self.kwargs['project_id']
        project = get_object_or_404(Project, id=project_id)
        # Můžeme ověřit, zda je request.user leader, atp.
        form.instance.project = project
        return super().form_valid(form)

    def get_success_url(self):
        milestone = self.object
        # Po vytvoření se vrátíme na detail projektu
        # return redirect('projects:detail', pk=self.kwargs['project_id'])
        return reverse('projects:detail', kwargs={'pk': milestone.project.id})

class MilestoneUpdateView(UpdateView):
    model = Milestone
    form_class = MilestoneForm  # Použití vlastního formuláře
    # fields = ['title', 'deadline', 'status', 'note']
    template_name = 'projects/milestone_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_authenticated and request.user.groups.filter(name='Teacher').exists()):
            messages.error(request, "Nemáte oprávnění upravovat milníky.")
            milestone = self.get_object()
            return redirect('projects:detail', pk=milestone.project.id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        milestone = self.object
        # return redirect('projects:detail', pk=milestone.project.id)
        return reverse('projects:detail', kwargs={'pk': milestone.project.id})
    



@login_required
def import_milestones_csv(request, project_id):
    """
    Např. ve formuláři 'upload file' -> POST -> 
    python parse -> create Milestone pro kazdy radek
    """
    project = get_object_or_404(Project, pk=project_id)
    if not request.user.groups.filter(name='Teacher').exists():
        messages.error(request, "Jen učitel může importovat milníky.")
        return redirect('projects:detail', pk=project_id)
    
    if request.method == 'POST':
        csv_file = request.FILES.get('file')
        if csv_file is None:
            messages.error(request, "Nebylo vybráno žádné CSV.")
            return redirect('projects:detail', pk=project_id)

        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.reader(decoded_file, delimiter=';')  # nebo ',' atd.
        # Očekáváš např. sloupce: title;deadline;status;note

        for row in reader:
            if len(row) < 1:
                continue

            title = row[0]
            deadline_str = row[1] if len(row) > 1 else None
            status = row[2] if len(row) > 2 else 'not_started'
            note = row[3] if len(row) > 3 else ''

            # Ošetření parsování data
            deadline = None
            if deadline_str:
                try:
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
                except ValueError:
                    messages.error(request, f"Neplatný formát datumu: {deadline_str}. Řádek přeskočen.")
                    continue  # Přeskočí špatně formátované řádky

            Milestone.objects.create(
                project=project,
                title=title,
                deadline=deadline,
                status=status,
                note=note
            )

        messages.success(request, "Milníky naimportovány.")
        return redirect('projects:detail', pk=project_id)
    
    # GET: zobrazit formulář
    return render(request, 'projects/milestone_import.html', {'project': project})




@login_required
def delete_milestone(request, milestone_id):
    """
    Odstraní milník, pokud má uživatel oprávnění (je vedoucí projektu).
    """
    milestone = get_object_or_404(Milestone, id=milestone_id)
    
    # Kontrola oprávnění: uživatel musí být vedoucí projektu
    if milestone.project.leader != request.user:
        return HttpResponseForbidden("Nemáte oprávnění odstranit tento milník.")

    milestone.delete()
    messages.success(request, "Milník byl úspěšně odstraněn.")
    return redirect('projects:detail', pk=milestone.project.id)


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


class LeaderEvalUpdateView(LoginRequiredMixin, UpdateView):
    model = LeaderEvaluation
    form_class = LeaderEvaluationForm
    template_name = 'projects/leader_eval_form.html'

    def get_object(self, queryset=None):
        project_id = self.kwargs['project_id']
        project = get_object_or_404(Project, id=project_id)
        # Zkusíme najít LeaderEvaluation, pokud neexistuje, vytvoříme v paměti
        obj, created = LeaderEvaluation.objects.get_or_create(project=project)
        return obj

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        project = obj.project
        if not (request.user == project.leader or request.user.is_superuser):
            messages.error(request, "Nemáte oprávnění vyplňovat hodnocení vedoucího.")
            return redirect('projects:detail', pk=project.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        # return redirect('projects:detail', pk=self.object.project.pk)
        return reverse('projects:detail', kwargs={'pk': self.object.project.pk})


class OpponentEvalUpdateView(LoginRequiredMixin, UpdateView):
    model = OpponentEvaluation
    form_class = OpponentEvaluationForm
    template_name = 'projects/opponent_eval_form.html'

    def get_object(self, queryset=None):
        project_id = self.kwargs['project_id']
        project = get_object_or_404(Project, id=project_id)
        obj, created = OpponentEvaluation.objects.get_or_create(project=project)
        return obj

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        project = obj.project
        # Jen oponent nebo superuser
        if not (request.user == project.opponent or request.user.is_superuser):
            messages.error(request, "Nemáte oprávnění vyplňovat hodnocení oponenta.")
            return redirect('projects:detail', pk=project.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        # return redirect('projects:detail', pk=self.object.project.pk)
        return reverse('projects:detail', kwargs={'pk': self.object.project.pk})


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


@login_required
def import_users_csv(request):
    """
    Očekává CSV (oddělené středníkem):
    username;first_name;last_name;email;role;class_name;study_branch
    Pokud study_branch chybí, nastaví se 'E'.
    """
    if request.method == 'POST':
        csv_file = request.FILES.get('file')
        if not csv_file:
            messages.error(request, "Není vybrán žádný CSV soubor.")
            return redirect('import_users_csv')

        # Přečteme soubor
        data = csv_file.read().decode('utf-8')
        reader = csv.reader(io.StringIO(data), delimiter=';', quotechar='"')

        student_group = Group.objects.get(name='Student')
        teacher_group = Group.objects.get(name='Teacher')

        count_created = 0
        row_counter = 0
        for row in reader:
            row_counter += 1
            # Očekáváme aspoň 6 sloupců (role, class_name)
            # a 7. sloupec pro study_branch
            if len(row) < 6:
                # Minimální formát je username;fname;lname;email;role;class_name
                # Případně 7. sloupec je study_branch
                messages.warning(request, f"Řádek {row_counter}: Příliš málo sloupců.")
                continue

            username = row[0].strip()
            first_name = row[1].strip()
            last_name = row[2].strip()
            email = row[3].strip()
            role = row[4].strip().lower()  # "student" nebo "teacher"
            class_name = row[5].strip()

            # sloupec 6 = study_branch
            if len(row) > 6:
                study_branch = row[6].strip()
                if not study_branch:  # prázdné
                    study_branch = 'E'
            else:
                study_branch = 'E'

            user, created = User.objects.get_or_create(username=username, defaults={
                'first_name': first_name,
                'last_name': last_name,
                'email': email
            })

            if not created:
                # user už existuje, updatuj jméno
                user.first_name = first_name
                user.last_name = last_name
                user.email = email
                user.save()

            if role == 'student':
                user.groups.set([student_group])
                # profil
                if hasattr(user, 'userprofile'):
                    profile = user.userprofile
                else:
                    profile = UserProfile.objects.create(user=user)
                profile.class_name = class_name
                profile.study_branch = study_branch
                profile.save()

            elif role == 'teacher':
                user.groups.set([teacher_group])

            # Nastav heslo, pokud user nově vznikl (dle tvé logiky)
            if created:
                user.set_password("heslo123")
                user.save()

            count_created += 1

        messages.success(request, f"Import hotov, zpracováno {count_created} řádků.")
        return redirect('somewhere')

    return render(request, 'users/import_users.html')



class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'users/user_profile_form.html'

    def dispatch(self, request, *args, **kwargs):
        # Uživatel může editovat jen sám sebe
        if request.user.pk != int(kwargs['pk']) and not request.user.is_superuser:
            messages.error(request, "Nemůžete měnit údaje jiného uživatele.")
            return redirect('projects:list')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        messages.success(self.request, "Údaje úspěšně aktualizovány.")
        return reverse('projects:list')  # nebo detail uživatele
    

@staff_member_required  # nebo login_required + check user.is_superuser
def import_projects(request):
    """
    CSV formát (quotechar='"', delimiter=';'), řádky:
    student_username;title;description;[leader_username];[opponent_username]
    V případě chyb se řádek přeskočí a zaloguje.
    """
    log_entries = []  # sem budeme ukládat záznamy o přeskočených řádcích

    if request.method == 'POST':
        csv_file = request.FILES.get('file')
        if not csv_file:
            messages.error(request, "Není vybrán žádný CSV soubor.")
            return redirect('projects:import_projects')

        # Čtení CSV s ohledem na uvozovky a středník
        data = csv_file.read().decode('utf-8', errors='replace')
        reader = csv.reader(io.StringIO(data), delimiter=';', quotechar='"')

        count_created = 0
        row_num = 0

        for row in reader:
            row_num += 1
            # Očekávaný minimální počet sloupců = 3 (student, title, description)
            if len(row) < 3:
                log_entries.append(f"Řádek {row_num}: Nedostatečný počet sloupců.")
                continue

            student_username = row[0].strip()
            title = row[1].strip()
            description = row[2].strip()

            leader_username = row[3].strip() if len(row) > 3 else ""
            opponent_username = row[4].strip() if len(row) > 4 else ""

            # Najít studenta
            try:
                student = User.objects.get(username=student_username)
            except User.DoesNotExist:
                log_entries.append(f"Řádek {row_num}: Student '{student_username}' neexistuje.")
                continue

            # Případně leader
            leader = None
            if leader_username:
                try:
                    leader = User.objects.get(username=leader_username)
                except User.DoesNotExist:
                    log_entries.append(f"Řádek {row_num}: Vedoucí '{leader_username}' neexistuje. Přeskakuji.")
                    continue

            # Případně opponent
            opponent = None
            if opponent_username:
                try:
                    opponent = User.objects.get(username=opponent_username)
                except User.DoesNotExist:
                    log_entries.append(f"Řádek {row_num}: Oponent '{opponent_username}' neexistuje. Přeskakuji.")
                    continue

            # Kontrola duplicity (stejný title + stejný student)
            existing = Project.objects.filter(title=title, student=student).exists()
            if existing:
                log_entries.append(f"Řádek {row_num}: Projekt '{title}' pro studenta '{student_username}' už existuje.")
                continue

            # Vytvořit nový Project
            Project.objects.create(
                student=student,
                title=title,
                description=description,
                leader=leader,
                opponent=opponent
            )
            count_created += 1

        messages.success(request, f"Import hotov. Vytvořeno {count_created} projektů.")
        # Můžeme log_entries uložit do session, abychom je zobrazili ve výsledné stránce nebo stáhli jako CSV
        request.session['import_logs'] = log_entries
        return redirect('projects:import_result')

    return render(request, 'projects/import_projects.html')


@staff_member_required
def import_result_view(request):
    """
    Zobrazí log_entries ze session, příp. nabídne stažení jako CSV.
    """
    log_entries = request.session.pop('import_logs', [])
    return render(request, 'projects/import_result.html', {'log_entries': log_entries})


@staff_member_required
def export_projects_xlsx(request):
    """
    Exportuje seznam projektů do XLSX.
    Sloupce: Student, Třída, Název, Vedoucí, Oponent, Stav.
    Případně můžeme přidat filtry.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Projekty"

    # Hlavička
    ws.append(["Student", "Třída", "Název projektu", "Vedoucí", "Oponent", "Stav"])

    projects = Project.objects.all()  # nebo filtr, to je na tobě

    for proj in projects:
        student_name = f"{proj.student.first_name} {proj.student.last_name}" if proj.student else ""
        student_class = ""
        if proj.student and hasattr(proj.student, 'userprofile'):
            student_class = proj.student.userprofile.class_name or ""
        
        leader_name = proj.leader.username if proj.leader else ""
        opponent_name = proj.opponent.username if proj.opponent else ""
        row = [
            student_name,
            student_class,
            proj.title,
            leader_name,
            opponent_name,
            proj.get_status_display(),
        ]
        ws.append(row)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="projekty.xlsx"'

    wb.save(response)
    return response



@login_required
def user_preferences_view(request):
    # pokud user nemá preferences, vytvoříme
    prefs, created = UserPreferences.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, instance=prefs)
        if form.is_valid():
            form.save()
            messages.success(request, "Nastavení uloženo.")
            return redirect('projects:list')
    else:
        form = UserPreferencesForm(instance=prefs)
    return render(request, 'users/user_preferences.html', {'form': form})


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
    from .models import ControlCheck
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


class StudentMilestoneCreateView(CreateView):
    model = Milestone
    form_class = StudentMilestoneForm
    template_name = 'projects/milestone_form.html'

    def dispatch(self, request, *args, **kwargs):
        project = get_object_or_404(Project, pk=self.kwargs['project_id'])

        if request.user != project.student:
            messages.error(request, "Nemáte oprávnění přidávat milníky k tomuto projektu.")
            return redirect('projects:detail', pk=project.pk)

        if project.status == 'approved' or (project.scheme and timezone.now() > project.scheme.student_edit_deadline):
            messages.error(request, "Nelze upravovat milníky po termínu nebo po schválení projektu.")
            return redirect('projects:detail', pk=project.pk)

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        form.instance.project = project
        return super().form_valid(form)

    def get_success_url(self):
        milestone = self.object
        return reverse('projects:detail', kwargs={'pk': milestone.project.id})


class StudentMilestoneUpdateView(UpdateView):
    model = Milestone
    form_class = StudentMilestoneForm
    template_name = 'projects/milestone_form.html'

    def dispatch(self, request, *args, **kwargs):
        milestone = self.get_object()
        project = milestone.project

        if request.user != project.student:
            messages.error(request, "Nemáte oprávnění upravovat tento milník.")
            return redirect('projects:detail', pk=project.pk)

        if project.status == 'approved' or (project.scheme and timezone.now() > project.scheme.student_edit_deadline):
            messages.error(request, "Nelze upravovat milníky po termínu nebo po schválení projektu.")
            return redirect('projects:detail', pk=project.pk)

        return super().dispatch(request, *args, **kwargs)

    
    def get_success_url(self):
        milestone = self.object
        return reverse('projects:detail', kwargs={'pk': milestone.project.id})


@login_required
def student_delete_milestone(request, milestone_id):
    milestone = get_object_or_404(Milestone, id=milestone_id)
    project = milestone.project

    if request.user != project.student:
        messages.error(request, "Nemáte oprávnění odstranit tento milník.")
        return redirect('projects:detail', pk=project.pk)

    if project.status == 'approved' or (project.scheme and timezone.now() > project.scheme.student_edit_deadline):
        messages.error(request, "Nelze odstranit milník po termínu nebo po schválení projektu.")
        return redirect('projects:detail', pk=project.pk)

    milestone.delete()
    messages.success(request, "Milník byl úspěšně odstraněn.")
    return redirect('projects:detail', pk=project.pk)
