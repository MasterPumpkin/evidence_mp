from django.contrib import admin
from .models import Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'student', 'leader', 'opponent')
    list_filter = ('status',)
    search_fields = ('title', 'description')
