from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from .models import UserProfile
from .forms import UserForm, UserProfileForm

@login_required
def edit_profile(request, pk):
    profile = get_object_or_404(UserProfile, pk=pk)
    user = profile.user  # Načteme přímo uživatele připojeného k profilu

    if request.method == 'POST':
        u_form = UserForm(request.POST, instance=user)
        p_form = UserProfileForm(request.POST, request.FILES, instance=profile)  # Přidáme request.FILES, pokud je obrázek

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, "Profil byl úspěšně aktualizován.")
            return redirect('profiles:user_profile_edit', pk=pk)
        else:
            messages.error(request, "Prosím zkontrolujte chyby ve formuláři.")
    else:
        u_form = UserForm(instance=user)
        p_form = UserProfileForm(instance=profile)

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'is_teacher': user.groups.filter(name='Teacher').exists(),
    }
    return render(request, 'users/edit_profile.html', context)
