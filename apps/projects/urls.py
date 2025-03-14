from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views.evaluation_views import (
    LeaderEvalUpdateView, OpponentEvalUpdateView)
from .views.export_views import (
    export_project_docx, export_projects_xlsx, 
    export_consultation_list, export_project_assignment,
    export_project_detail_pdf, export_control_check_pdf,
    export_leader_eval, export_opponent_eval,
    export_final_report_pdf, export_milestones_pdf,
    project_details_overview, export_project_details_pdf)  # Add the new view import
from .views.import_views import (
    import_milestones_csv, import_users_csv, 
    import_projects, import_result_view,
    import_result, download_passwords_csv)
from .views.milestone_views import (
    MilestoneCreateView, MilestoneUpdateView,
    delete_milestone, StudentMilestoneCreateView,
    StudentMilestoneUpdateView, student_delete_milestone)
from .views.project_views import (
    ProjectListView, TeacherProjectCreateView,
    TeacherProjectUpdateView, StudentProjectCreateView,
    StudentProjectUpdateView, approve_project,
    resign_as_leader, resign_as_opponent,
    ProjectDetailView, ProjectCreateView,
    ProjectUpdateView, delete_controlcheck,
    ControlCheckCreateView, ControlCheckUpdateView,
    ProjectNotesUpdateView, ProjectAssignmentUpdateView,
    take_opponent_role, ProjectOpponentUpdateView,
    generate_consultations, update_milestone_status,
    LeaderReviewView, OpponentReviewView, update_project_status,
    LeaderQuestionsView, OpponentQuestionsView,  # add these
)
from .views.user_views import (
    UserProfileUpdateView, user_preferences_view)


app_name = 'projects'

urlpatterns = [
    path('', ProjectListView.as_view(), name='list'),
    path('new/', ProjectCreateView.as_view(), name='create'),
    path('<int:pk>/', ProjectDetailView.as_view(), name='detail'),
    path('<int:pk>/approve/', approve_project, name='approve'),
    path('<int:pk>/resign/', resign_as_leader, name='resign'),
    path('<int:pk>/resign-opponent/', resign_as_opponent, name='resign_opponent'),
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
    path('<int:pk>/assignment-edit/', ProjectAssignmentUpdateView.as_view(), name='assignment_edit'),
    path('<int:pk>/take-opponent/', take_opponent_role, name='take_opponent'),
    path('<int:pk>/opponent-update/', ProjectOpponentUpdateView.as_view(), name='opponent_update'),
    path('import-users/', import_users_csv, name='import_users'),
    path('import-result/', import_result, name='import_result'),
    path('download-passwords-csv/', download_passwords_csv, name='download_passwords_csv'),
    # path('user-profile/<int:pk>/edit/', UserProfileUpdateView.as_view(), name='user_profile_edit'),
    path('<int:pk>/export-docx/', export_project_docx, name='export_docx'),
    path('import-projects/', import_projects, name='import_projects'),
    path('import-projects/result/', import_result_view, name='import_projects_result'),
    path('export-projects/', export_projects_xlsx, name='export_projects'),
    path('preferences/', user_preferences_view, name='user_preferences'),
    path('<int:pk>/generate-consultations/', generate_consultations, name='generate_consultations'),

    path('create/teacher/', TeacherProjectCreateView.as_view(), name='teacher_project_create'),
    path('create/student/', StudentProjectCreateView.as_view(), name='student_project_create'),

    path('<int:pk>/edit/student/', StudentProjectUpdateView.as_view(), name='student_project_update'),
    path('<int:pk>/edit/teacher/', TeacherProjectUpdateView.as_view(), name='teacher_project_update'),

    # Nové URL pro studenty – přidání/úprava/mazání milníků
    path('<int:project_id>/milestones/student/new/', StudentMilestoneCreateView.as_view(), name='student_milestone_add'),
    path('milestones/<int:pk>/student/edit/', StudentMilestoneUpdateView.as_view(), name='student_milestone_edit'),
    path('milestones/<int:milestone_id>/student/delete/', student_delete_milestone, name='student_milestone_delete'),

    # Exporty
    path('<int:pk>/export/opponent-eval/', export_opponent_eval, name='export_opponent_eval'),
    path('<int:pk>/export/leader-eval/', export_leader_eval, name='export_leader_eval'),
    path('<int:pk>/export/control-checks/', export_consultation_list, name='export_consultation_list'),
    path('<int:pk>/export/assignment/', export_project_assignment, name='export_project_assignment'),

    path('projects/<int:pk>/export/pdf/', export_project_detail_pdf, name='export_project_pdf'),
    path('projects/export/control-check/', export_control_check_pdf, name='export_control_check_pdf'),
    path('<int:pk>/pdf-report/', export_final_report_pdf, name='pdf_final_report'),

    path('update-milestone-status/<int:milestone_id>/', update_milestone_status, name='update_milestone_status'),

    path('<int:pk>/review-leader/', LeaderReviewView.as_view(), name='review_leader'),
    path('<int:pk>/review-opponent/', OpponentReviewView.as_view(), name='review_opponent'),

    path('export-milestones-pdf/', export_milestones_pdf, name='export_milestones_pdf'),
    path('project-details-overview/', project_details_overview, name='project_details_overview'),
    path('project-details-pdf/', export_project_details_pdf, name='project_details_pdf'),  # Add new URL
    path('update-status/<int:pk>/', update_project_status, name='update_status'),

    path('<int:pk>/questions-leader/', LeaderQuestionsView.as_view(), name='questions_leader'),
    path('<int:pk>/questions-opponent/', OpponentQuestionsView.as_view(), name='questions_opponent'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



"""
from .views import (
    ProjectListView, ProjectDetailView, 
    ProjectCreateView, approve_project, 
    ProjectUpdateView, resign_as_leader, 
    MilestoneCreateView, MilestoneUpdateView,
    import_milestones_csv, delete_milestone,
    ControlCheckCreateView, ControlCheckUpdateView,
    LeaderEvalUpdateView, OpponentEvalUpdateView,
    ProjectNotesUpdateView, delete_controlcheck,
    take_opponent_role, ProjectOpponentUpdateView,
    import_users_csv, UserProfileUpdateView,
    export_project_docx, ProjectAssignmentUpdateView,
    import_projects, import_result_view,
    export_projects_xlsx, user_preferences_view,
    generate_consultations,
    TeacherProjectCreateView, StudentProjectCreateView,
    StudentProjectUpdateView, TeacherProjectUpdateView,
    StudentMilestoneCreateView, StudentMilestoneUpdateView,
    student_delete_milestone, resign_as_opponent,
    export_opponent_eval, export_leader_eval,
    export_consultation_list, export_project_assignment,
    export_project_detail_pdf, export_control_check_pdf,
    export_final_report_pdf
)
"""