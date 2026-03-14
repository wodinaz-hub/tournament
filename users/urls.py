from django.urls import path
from .views import (
    home,
    register_view,
    login_view,
    logout_view,
    redirect_by_role,
    admin_dashboard,
    approve_user,
    create_tournament,
    edit_tournament,
    jury_dashboard,
    participant_dashboard,
    create_team,
    register_team_for_tournament,
    team_detail,
    add_participant,
    delete_participant,
    delete_team,
    tournament_tasks,
    team_results,
    submit_solution,
)

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('redirect/', redirect_by_role, name='redirect_by_role'),

    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('approve-user/<int:user_id>/', approve_user, name='approve_user'),
    path('create-tournament/', create_tournament, name='create_tournament'),
    path('edit-tournament/<int:tournament_id>/', edit_tournament, name='edit_tournament'),

    path('jury-dashboard/', jury_dashboard, name='jury_dashboard'),

    path('participant-dashboard/', participant_dashboard, name='participant_dashboard'),
    path('create-team/', create_team, name='create_team'),
    path('register-team-for-tournament/<int:tournament_id>/', register_team_for_tournament, name='register_team_for_tournament'),

    path('team/<int:team_id>/', team_detail, name='team_detail'),
    path('team/<int:team_id>/add-participant/', add_participant, name='add_participant'),
    path('team/<int:team_id>/participant/<int:participant_id>/delete/', delete_participant, name='delete_participant'),
    path('team/<int:team_id>/delete/', delete_team, name='delete_team'),
    path('tournament/<int:tournament_id>/tasks/', tournament_tasks, name='tournament_tasks'),
    path('team/<int:team_id>/results/', team_results, name='team_results'),
    path('task/<int:task_id>/submit/', submit_solution, name='submit_solution'),
]