from django.urls import path
from .views import ProjectListView, ProjectDetailView, ProjectCreateView, approve_project, ProjectUpdateView, resign_as_leader

app_name = 'projects'

urlpatterns = [
    path('', ProjectListView.as_view(), name='list'),
    path('new/', ProjectCreateView.as_view(), name='create'),
    path('<int:pk>/', ProjectDetailView.as_view(), name='detail'),
    path('<int:pk>/approve/', approve_project, name='approve'),
    path('<int:pk>/resign/', resign_as_leader, name='resign'),
    path('<int:pk>/edit/', ProjectUpdateView.as_view(), name='edit'),
]
