from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Project
from django.utils import timezone


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
        # Nebo můžeš filtr přidat i pro "Teacher"
        return qs

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

