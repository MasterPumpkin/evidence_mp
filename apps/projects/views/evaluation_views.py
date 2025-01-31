from django.shortcuts import get_object_or_404, redirect
from django.views.generic import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from ..models import Project, LeaderEvaluation, OpponentEvaluation
from ..forms import (
    LeaderEvaluationForm, OpponentEvaluationForm
)
import csv
from django.urls import reverse



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
    
    def get_initial(self):
        initial = super().get_initial()
        leader_eval = self.get_object()

        # Pokud existuje uložené datum, předvyplníme ho
        if leader_eval.export_date:
            initial['export_date'] = leader_eval.export_date.strftime('%Y-%m-%d')

        return initial
    
    def form_valid(self, form):
        leader_eval = form.save(commit=False)
        leader_eval.export_date = form.cleaned_data['export_date']
        leader_eval.submission_status = form.cleaned_data['submission_status']
        leader_eval.save()
        return super().form_valid(form)

    def get_success_url(self):
        # return redirect('projects:detail', pk=self.object.project.pk)
        return reverse('projects:detail', kwargs={'pk': self.object.project.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()

        return context 


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

    def get_initial(self):
        initial = super().get_initial()
        opponent_eval = self.get_object()

        # Pokud existuje uložené datum, předvyplníme ho
        if opponent_eval.export_date:
            initial['export_date'] = opponent_eval.export_date.strftime('%Y-%m-%d')

        return initial
    
    def form_valid(self, form):
        opponent_eval = form.save(commit=False)
        opponent_eval.export_date = form.cleaned_data['export_date']
        opponent_eval.save()
        return super().form_valid(form)
    
    def get_success_url(self):
        # return redirect('projects:detail', pk=self.object.project.pk)
        return reverse('projects:detail', kwargs={'pk': self.object.project.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()

        return context 
