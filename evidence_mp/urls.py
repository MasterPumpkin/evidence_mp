from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path,include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('projects/', include('apps.projects.urls', namespace='projects')),
    # path('profiles/', include('apps.profiles.urls', namespace='profiles')),
    path('', RedirectView.as_view(url='/projects/', permanent=False)),
    path('accounts/password_change/', 
         auth_views.PasswordChangeView.as_view(template_name='registration/password_change_form.html'),
         name='password_change'),
    path('accounts/password_change/done/', 
         auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), 
         name='password_change_done'),
]
