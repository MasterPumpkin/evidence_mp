from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, UpdateView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Project, Milestone
from django.utils import timezone
from ..forms import (
    MilestoneForm,StudentMilestoneForm
)
import csv
from django.http import HttpResponseForbidden
from django.urls import reverse



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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()
        project_id = self.kwargs['project_id']
        project = get_object_or_404(Project, id=project_id)
        context['project'] = project
        return context 

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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()
        milestone = self.get_object()
        project = get_object_or_404(Project, id=milestone.project.id)
        context['project'] = project

        return context 



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
