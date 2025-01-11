import csv
import io
from django.contrib.auth.models import User, Group
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.profiles.models import UserProfile
from .models import Project, Milestone, ControlCheck, LeaderEvaluation, OpponentEvaluation
from django.utils import timezone
from django.utils.decorators import method_decorator
from .forms import (
    MilestoneForm,ProjectForm, ControlCheckForm,
    LeaderEvaluationForm, OpponentEvaluationForm,
    ProjectNotesForm, ProjectOpponentForm,
    UserUpdateForm
)
import csv
from django.http import HttpResponse, HttpResponseForbidden
from datetime import datetime
from django.urls import reverse
from django.contrib.auth.models import User


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


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'
    
    def get_queryset(self):
        qs = super().get_queryset()

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

        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Seznam učitelů – budeme je zobrazovat v dropdownu
        context['all_teachers'] = User.objects.filter(groups__name='Teacher')
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
        

        if project.edit_deadline and timezone.now() > project.edit_deadline:
            messages.error(request, "Vypršela lhůta pro úpravu projektu.")
            # return redirect('projects:detail', pk=project.pk)
            return redirect(project)

        return super().dispatch(request, *args, **kwargs)
        # return redirect(project)

    def get_success_url(self):
        return '/projects/'


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
    Očekává CSV s řádky:
    username;first_name;last_name;email;role;class_name
    kde role je 'student' nebo 'teacher'.
    """
    if request.method == 'POST':
        csv_file = request.FILES.get('file')
        if not csv_file:
            messages.error(request, "Není vybrán žádný CSV soubor.")
            return redirect('import_users_csv')

        data = csv_file.read().decode('utf-8')
        reader = csv.reader(io.StringIO(data), delimiter=';')

        student_group = Group.objects.get(name='Student')
        teacher_group = Group.objects.get(name='Teacher')

        count_created = 0
        for row in reader:
            if len(row) < 5:
                continue

            username = row[0].strip()
            fname = row[1].strip()
            lname = row[2].strip()
            email = row[3].strip()
            role = row[4].strip().lower()  # 'student' / 'teacher'
            class_name = row[5].strip() if len(row) > 5 else ''

            # Kontrola, zda user už existuje
            user, created = User.objects.get_or_create(username=username, defaults={
                'first_name': fname,
                'last_name': lname,
                'email': email
            })

            if not created:
                # User už existuje, můžeme updatovat jméno/ email
                user.first_name = fname
                user.last_name = lname
                user.email = email
                user.save()

            # Přidání do skupiny
            if role == 'student':
                user.groups.set([student_group])  # nebo .add()
                # Vytvoříme userprofile, nastavíme třídu
                if hasattr(user, 'userprofile'):
                    user.userprofile.class_name = class_name
                    user.userprofile.save()
                else:
                    UserProfile.objects.create(user=user, class_name=class_name)

            elif role == 'teacher':
                user.groups.set([teacher_group])

            # Nastavit heslo - varianty:
            # a) Vygenerovat náhodné
            # b) Nastavit default heslo (např. "heslo123") - pro demo
            if created:
                user.set_password("heslo123")  # Lepší by bylo generovat
                user.save()

            count_created += 1

        messages.success(request, f"Načteno {count_created} uživatelů.")
        return redirect('projects:list')

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