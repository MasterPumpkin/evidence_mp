from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'class_name', 'study_branch')
    list_filter = ('class_name', 'study_branch')
    search_fields = ('user__username', 'class_name', 'study_branch')
