from django.urls import path
from django.conf import settings
from .views import edit_profile

app_name = 'profiles'

urlpatterns = [
    path('user-profile/<int:pk>/edit/', edit_profile, name='user_profile_edit'),
]