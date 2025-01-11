from django.urls import path
from .views import (
    ProjectListView, ProjectDetailView, 
    ProjectCreateView, approve_project, 
    ProjectUpdateView, resign_as_leader, 
    MilestoneCreateView, MilestoneUpdateView,
    import_milestones_csv, delete_milestone,
    ControlCheckCreateView, ControlCheckUpdateView,
    LeaderEvalUpdateView, OpponentEvalUpdateView,
    ProjectNotesUpdateView, delete_controlcheck
)

app_name = 'projects'

urlpatterns = [
    path('', ProjectListView.as_view(), name='list'),
    path('new/', ProjectCreateView.as_view(), name='create'),
    path('<int:pk>/', ProjectDetailView.as_view(), name='detail'),
    path('<int:pk>/approve/', approve_project, name='approve'),
    path('<int:pk>/resign/', resign_as_leader, name='resign'),
    path('<int:pk>/edit/', ProjectUpdateView.as_view(), name='edit'),
    # Milníky
    path('<int:project_id>/milestones/new/', MilestoneCreateView.as_view(), name='milestone_add'),
    path('milestones/<int:pk>/edit/', MilestoneUpdateView.as_view(), name='milestone_edit'),
    path('<int:project_id>/milestones/import/', import_milestones_csv, name='milestone_import'),
    path('milestones/<int:milestone_id>/delete/', delete_milestone, name='milestone_delete'),
     # Kontroly
    path('<int:project_id>/checks/new/', ControlCheckCreateView.as_view(), name='check_create'),
    path('checks/<int:pk>/edit/', ControlCheckUpdateView.as_view(), name='check_edit'),
    path('checks/<int:controlcheck_id>/delete/', delete_controlcheck, name='controlcheck_delete'),
    # Hodnocení vedoucího
    path('<int:project_id>/leader-eval/', LeaderEvalUpdateView.as_view(), name='leader_eval'),
    # Hodnocení oponenta
    path('<int:project_id>/opponent-eval/', OpponentEvalUpdateView.as_view(), name='opponent_eval'),
    path('<int:pk>/notes/', ProjectNotesUpdateView.as_view(), name='notes_edit'),
]
