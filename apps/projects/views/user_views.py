from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.views.generic import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import UserPreferences
from ..forms import (
    UserUpdateForm, UserPreferencesForm
)
import csv
from django.urls import reverse
from django.contrib.auth.models import User



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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['is_teacher'] = user.groups.filter(name='Teacher').exists()
        context['is_student'] = user.groups.filter(name='Student').exists()

        return context 
    


@login_required
def user_preferences_view(request):
    # pokud user nemá preferences, vytvoříme
    prefs, created = UserPreferences.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, request.FILES, instance=prefs)
        if form.is_valid():
            form.save()
            messages.success(request, "Nastavení uloženo.")
            return redirect('projects:list')
    else:
        form = UserPreferencesForm(instance=prefs)
    # Přidání informací o roli uživatele do kontextu
    context = {
        'form': form,
        'is_teacher': request.user.groups.filter(name='Teacher').exists(),
        'is_student': request.user.groups.filter(name='Student').exists(),
    }
    # return render(request, 'users/user_preferences.html', {'form': form})
    return render(request, 'users/user_preferences.html', context)

