from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404

from .forms import RegisterForm, LoginForm
from .models import CustomUser

from tournament.models import (
    Tournament,
    Team,
    Participant,
    Task,
    Submission,
    JuryAssignment,
    Evaluation,
    TournamentRegistration,
)
from tournament.forms import (
    TournamentForm,
    TeamForm,
    ParticipantForm,
    TournamentRegistrationForm,
)


def home(request):
    if request.user.is_authenticated:
        return redirect('redirect_by_role')
    return redirect('login')


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)

            if user.role == 'participant':
                user.is_approved = True
            else:
                user.is_approved = False

            user.save()
            return redirect('login')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})


def login_view(request):
    message = ''

    if request.user.is_authenticated:
        return redirect('redirect_by_role')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()

            if not user.is_approved and not user.is_superuser:
                message = 'Ваш акаунт ще не схвалений адміністратором.'
            else:
                login(request, user)
                return redirect('redirect_by_role')
        else:
            message = 'Неправильний логін або пароль.'
    else:
        form = LoginForm()

    return render(request, 'login.html', {
        'form': form,
        'message': message
    })


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def redirect_by_role(request):

    user = request.user

    if user.is_superuser or user.role == 'admin':
        return redirect('admin_dashboard')

    elif user.role == 'jury':
        return redirect('jury_dashboard')

    elif user.role == 'captain':
        return redirect('participant_dashboard')

    else:
        return redirect('participant_dashboard')


@login_required
def admin_dashboard(request):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')

    pending_users = CustomUser.objects.filter(is_approved=False).exclude(role='participant')
    approved_users = CustomUser.objects.filter(is_approved=True)

    tournaments = Tournament.objects.all()
    teams = Team.objects.select_related('captain_user').prefetch_related('registrations__tournament')
    tasks = Task.objects.select_related('tournament').all()
    submissions = Submission.objects.select_related('team', 'task', 'task__tournament').all()
    jury_assignments = JuryAssignment.objects.select_related('jury_user', 'submission').all()
    evaluations = Evaluation.objects.select_related('assignment').all()
    registrations = TournamentRegistration.objects.select_related('tournament', 'team', 'registered_by').all()

    context = {
        'pending_users': pending_users,
        'approved_users': approved_users,
        'tournaments': tournaments,
        'teams': teams,
        'tasks': tasks,
        'submissions': submissions,
        'jury_assignments': jury_assignments,
        'evaluations': evaluations,
        'registrations': registrations,
    }

    return render(request, 'admin_dashboard.html', context)


@login_required
def approve_user(request, user_id):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')

    user = get_object_or_404(CustomUser, id=user_id)

    if user.id == request.user.id and not request.user.is_superuser:
        return redirect('admin_dashboard')

    user.is_approved = True
    user.save()
    return redirect('admin_dashboard')


@login_required
def create_tournament(request):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')

    if request.method == 'POST':
        form = TournamentForm(request.POST)
        if form.is_valid():
            tournament = form.save(commit=False)
            tournament.created_by = request.user
            tournament.save()
            return redirect('admin_dashboard')
    else:
        form = TournamentForm()

    return render(request, 'create_tournament.html', {'form': form, 'mode': 'create'})


@login_required
def edit_tournament(request, tournament_id):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')

    tournament = get_object_or_404(Tournament, id=tournament_id)

    if request.method == 'POST':
        form = TournamentForm(request.POST, instance=tournament)
        if form.is_valid():
            form.save()
            return redirect('admin_dashboard')
    else:
        form = TournamentForm(instance=tournament)

    return render(request, 'create_tournament.html', {
        'form': form,
        'mode': 'edit',
        'tournament': tournament,
    })


@login_required
def jury_dashboard(request):
    if request.user.role != 'jury' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    assignments = JuryAssignment.objects.filter(
        jury_user=request.user
    ).select_related(
        'submission',
        'submission__team',
        'submission__task',
        'submission__task__tournament',
    )

    return render(request, 'jury_dashboard.html', {
        'assignments': assignments
    })


@login_required
def participant_dashboard(request):
    if request.user.role not in ['participant', 'captain'] and not request.user.is_superuser:
        return redirect('redirect_by_role')

    my_teams = Team.objects.filter(
        Q(captain_user=request.user) | Q(participants__email=request.user.email)
    ).select_related('captain_user').prefetch_related(
        'participants',
        'registrations__tournament',
    ).distinct()

    available_tournaments = Tournament.objects.filter(
        status='registration'
    ).order_by('start_date')

    registrations = TournamentRegistration.objects.filter(
        team__captain_user=request.user
    ).select_related('tournament', 'team')

    my_registration_by_tournament_id = {
        reg.tournament_id: reg for reg in registrations
    }

    tournaments_with_state = []
    for tournament in available_tournaments:
        existing_registration = my_registration_by_tournament_id.get(tournament.id)

        tournaments_with_state.append({
            'tournament': tournament,
            'my_registration': existing_registration,
            'my_team': existing_registration.team if existing_registration else None,
            'can_register': existing_registration is None,
        })

    return render(request, 'participant_dashboard.html', {
        'my_teams': my_teams,
        'tournaments_with_state': tournaments_with_state,
    })


@login_required
def create_team(request):

    if request.user.role != 'captain' and not request.user.is_superuser:
        return redirect('participant_dashboard')

    if Team.objects.filter(captain_user=request.user).exists():
        return redirect('participant_dashboard')

    if request.method == 'POST':

        form = TeamForm(request.POST)

        if form.is_valid():

            team = form.save(commit=False)
            team.captain_user = request.user

            if not team.captain_name:
                team.captain_name = request.user.username

            if not team.captain_email:
                team.captain_email = request.user.email

            team.save()

            return redirect('participant_dashboard')

    else:

        form = TeamForm(initial={
            'captain_name': request.user.username,
            'captain_email': request.user.email,
        })

    return render(request, 'create_team.html', {'form': form})

@login_required
def register_team_for_tournament(request, tournament_id):
    if request.user.role != 'captain' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    tournament = get_object_or_404(Tournament, id=tournament_id, status='registration')

    already_registered = TournamentRegistration.objects.filter(
        tournament=tournament,
        team__captain_user=request.user
    ).exists()

    if already_registered:
        return redirect('participant_dashboard')

    if request.method == 'POST':
        form = TournamentRegistrationForm(
            request.POST,
            user=request.user,
            tournament=tournament,
        )
        if form.is_valid():
            team = form.cleaned_data['team']

            TournamentRegistration.objects.create(
                tournament=tournament,
                team=team,
                registered_by=request.user,
                status='pending',
            )
            return redirect('participant_dashboard')
    else:
        form = TournamentRegistrationForm(
            user=request.user,
            tournament=tournament,
        )

    return render(request, 'register_team_for_tournament.html', {
        'form': form,
        'tournament': tournament,
    })


@login_required
def team_detail(request, team_id):
    if request.user.role != 'captain' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    team = get_object_or_404(
        Team.objects.select_related('captain_user').prefetch_related('registrations__tournament'),
        id=team_id,
        captain_user=request.user
    )
    participants = team.participants.all().order_by('full_name')
    submissions = team.submissions.select_related('task', 'task__tournament').all()

    return render(request, 'team_detail.html', {
        'team': team,
        'participants': participants,
        'submissions': submissions,
    })


@login_required
def add_participant(request, team_id):
    if request.user.role != 'captain' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    team = get_object_or_404(Team, id=team_id, captain_user=request.user)

    if request.method == 'POST':
        form = ParticipantForm(request.POST)
        if form.is_valid():
            participant = form.save(commit=False)
            participant.team = team
            participant.save()
            return redirect('team_detail', team_id=team.id)
    else:
        form = ParticipantForm()

    return render(request, 'add_participant.html', {
        'form': form,
        'team': team,
    })

@login_required
def delete_participant(request, team_id, participant_id):
    if request.user.role != 'captain' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    team = get_object_or_404(Team, id=team_id, captain_user=request.user)
    participant = get_object_or_404(Participant, id=participant_id, team=team)

    if request.method == 'POST':
        participant.delete()
        return redirect('team_detail', team_id=team.id)

    return redirect('team_detail', team_id=team.id)


@login_required
def delete_team(request, team_id):
    if request.user.role != 'captain' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    team = get_object_or_404(
        Team,
        id=team_id,
        captain_user=request.user
    )

    if request.method == 'POST':
        team.delete()
        return redirect('participant_dashboard')

    return render(request, 'delete_team_confirm.html', {
        'team': team
    })


@login_required
def tournament_tasks(request, tournament_id):

    tournament = get_object_or_404(Tournament, id=tournament_id)

    if tournament.status != 'running':
        return redirect('participant_dashboard')

    tasks = Task.objects.filter(
        tournament=tournament,
        status='active',
    )

    return render(request, 'tournament_tasks.html', {
        'tournament': tournament,
        'tasks': tasks
    })


@login_required
def submit_solution(request, task_id):

    task = get_object_or_404(Task, id=task_id)

    if task.tournament.status != 'running':
        return redirect('participant_dashboard')

    team = Team.objects.filter(
        captain_user=request.user
    ).first()

    if not team:
        return redirect('participant_dashboard')

    if request.method == 'POST':

        github = request.POST.get('github')
        video = request.POST.get('video')

        Submission.objects.update_or_create(
            team=team,
            task=task,
            defaults={
                'github_link': github,
                'video_link': video,
            },
        )

        return redirect('team_detail', team.id)

    return render(request, 'submit_solution.html', {
        'task': task,
    })


@login_required
def team_results(request, team_id):

    team = get_object_or_404(
        Team,
        id=team_id,
        captain_user=request.user
    )

    evaluations = Evaluation.objects.filter(
        assignment__submission__team=team
    ).select_related(
        'assignment__submission__task'
    )

    return render(request, 'team_results.html', {
        'team': team,
        'evaluations': evaluations
    })