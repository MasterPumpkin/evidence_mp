from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path,include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

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

# Přidání routování pro mediální soubory
# if settings.DEBUG:  # Pouze při vývoji
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    path("ckeditor5/", include('django_ckeditor_5.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)