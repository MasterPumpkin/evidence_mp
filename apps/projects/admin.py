from django.contrib import admin
from .models import (
    ScoringScheme, Project, ControlCheck,
    LeaderEvaluation, OpponentEvaluation,
    UserPreferences
)

@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ('user', 'pref_myprojects_default')
    search_fields = ('user__username',)
    list_filter = ('pref_myprojects_default',)


@admin.register(ScoringScheme)
class ScoringSchemeAdmin(admin.ModelAdmin):
    list_display = ('year', 'active', 'leader_area1_max', 'opponent_area1_max', 
                   'delivery_work_deadline', 'delivery_documentation_deadline')
    list_filter = ('active', 'year')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'student', 'leader', 'opponent', 'scheme', 'delayed_submission_date')
    list_filter = ('status', 'scheme', 'delayed_submission_date')
    search_fields = ('title', 'description')

@admin.register(ControlCheck)
class ControlCheckAdmin(admin.ModelAdmin):
    list_display = ('project', 'date', 'evaluation')
    list_filter = ('date',)
    search_fields = ('project__title', 'content')

@admin.register(LeaderEvaluation)
class LeaderEvalAdmin(admin.ModelAdmin):
    list_display = ('project', 'area1_points', 'area2_points', 'area3_points')

@admin.register(OpponentEvaluation)
class OpponentEvalAdmin(admin.ModelAdmin):
    list_display = ('project', 'area1_points', 'area2_points')
