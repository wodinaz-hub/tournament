from statistics import mean

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from tournament.forms import (
    ParticipantForm,
    SubmissionForm,
    TaskForm,
    TeamForm,
    TournamentForm,
    TournamentRegistrationForm,
)
from tournament.models import (
    Evaluation,
    JuryAssignment,
    Participant,
    Submission,
    Task,
    Team,
    Tournament,
    TournamentRegistration,
)

from .forms import LoginForm, RegisterForm
from .models import CustomUser


def home(request):
    if request.user.is_authenticated:
        return redirect('redirect_by_role')
    return redirect('login')


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_approved = user.role == 'participant'
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

    return render(request, 'login.html', {'form': form, 'message': message})


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def redirect_by_role(request):
    user = request.user

    if user.is_superuser or user.role == 'admin':
        return redirect('admin_dashboard')
    if user.role == 'jury':
        return redirect('jury_dashboard')
    return redirect('participant_dashboard')


@login_required
def admin_dashboard(request):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')

    all_users = CustomUser.objects.order_by('role', 'username')
    pending_users = CustomUser.objects.filter(is_approved=False).exclude(role='participant')
    approved_users = CustomUser.objects.filter(is_approved=True)
    tournaments = Tournament.objects.prefetch_related('tasks').all()
    active_tournaments = [tournament for tournament in tournaments if not tournament.is_finished]
    inactive_tournaments = [tournament for tournament in tournaments if tournament.is_finished]
    teams = Team.objects.select_related('captain_user').prefetch_related('registrations__tournament')
    submissions = Submission.objects.select_related('team', 'task', 'task__tournament').all()
    jury_assignments = JuryAssignment.objects.select_related('jury_user', 'submission').all()
    evaluations = Evaluation.objects.select_related('assignment').all()
    registrations = TournamentRegistration.objects.select_related('tournament', 'team', 'registered_by').all()

    context = {
        'all_users': all_users,
        'role_choices': CustomUser.ROLE_CHOICES,
        'now': timezone.now(),
        'pending_users': pending_users,
        'approved_users': approved_users,
        'tournaments': tournaments,
        'active_tournaments': active_tournaments,
        'inactive_tournaments': inactive_tournaments,
        'teams': teams,
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
    user.save(update_fields=['is_approved'])
    return redirect('admin_dashboard')


@login_required
def update_user_role(request, user_id):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return redirect('admin_dashboard')

    user = get_object_or_404(CustomUser, id=user_id)
    new_role = request.POST.get('role')
    allowed_roles = {choice[0] for choice in CustomUser.ROLE_CHOICES}
    if new_role not in allowed_roles:
        return redirect('admin_dashboard')
    if user.is_superuser:
        return redirect('admin_dashboard')

    user.role = new_role
    if new_role == 'participant':
        user.is_approved = True
    user.save(update_fields=['role', 'is_approved'])
    return redirect('admin_dashboard')


@login_required
def delete_user(request, user_id):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return redirect('admin_dashboard')

    user = get_object_or_404(CustomUser, id=user_id)
    if user.id == request.user.id or user.is_superuser:
        return redirect('admin_dashboard')

    user.delete()
    return redirect('admin_dashboard')


@login_required
def approve_registration(request, registration_id):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')

    registration = get_object_or_404(TournamentRegistration, id=registration_id)
    registration.status = TournamentRegistration.Status.APPROVED
    registration.save(update_fields=['status'])
    return redirect('admin_dashboard')


@login_required
def reject_registration(request, registration_id):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')

    registration = get_object_or_404(TournamentRegistration, id=registration_id)
    registration.status = TournamentRegistration.Status.REJECTED
    registration.save(update_fields=['status'])
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
    if tournament.start_date <= timezone.now():
        return redirect('admin_dashboard')

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
def delete_tournament(request, tournament_id):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return redirect('admin_dashboard')

    tournament = get_object_or_404(Tournament, id=tournament_id)
    tournament.delete()
    return redirect('admin_dashboard')


@login_required
def create_task(request, tournament_id=None):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')

    tournament = None
    if tournament_id is not None:
        tournament = get_object_or_404(Tournament, id=tournament_id)
        if tournament.start_date <= timezone.now():
            return redirect('admin_dashboard')

    if request.method == 'POST':
        form = TaskForm(request.POST, tournament=tournament)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            return redirect('admin_dashboard')
    else:
        form = TaskForm(tournament=tournament)

    return render(request, 'create_task.html', {
        'form': form,
        'mode': 'create',
        'tournament': tournament,
    })


@login_required
def edit_task(request, task_id):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')

    task = get_object_or_404(Task, id=task_id)
    if task.tournament.start_date <= timezone.now():
        return redirect('admin_dashboard')

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            return redirect('admin_dashboard')
    else:
        form = TaskForm(instance=task)

    return render(request, 'create_task.html', {
        'form': form,
        'mode': 'edit',
        'task': task,
        'tournament': task.tournament,
    })


@login_required
def delete_task(request, task_id):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return redirect('admin_dashboard')

    task = get_object_or_404(Task, id=task_id)
    task.delete()
    return redirect('admin_dashboard')


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
    return render(request, 'jury_dashboard.html', {'assignments': assignments})


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

    visible_tournaments = [
        tournament
        for tournament in Tournament.objects.filter(is_draft=False).order_by('start_date')
        if not tournament.is_finished
    ]

    registrations = TournamentRegistration.objects.filter(
        Q(team__captain_user=request.user) | Q(team__participants__email=request.user.email)
    ).select_related('tournament', 'team').distinct()

    my_registration_by_tournament_id = {
        reg.tournament_id: reg for reg in registrations
    }

    tournaments_with_state = []
    for tournament in visible_tournaments:
        existing_registration = my_registration_by_tournament_id.get(tournament.id)
        can_register = (
            request.user.role == 'captain'
            and tournament.is_registration_open
            and existing_registration is None
        )
        can_open_tasks = (
            existing_registration is not None
            and existing_registration.status == TournamentRegistration.Status.APPROVED
            and tournament.is_running
        )

        tournaments_with_state.append({
            'tournament': tournament,
            'my_registration': existing_registration,
            'my_team': existing_registration.team if existing_registration else None,
            'can_register': can_register,
            'can_open_tasks': can_open_tasks,
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

    tournament = get_object_or_404(Tournament, id=tournament_id, is_draft=False)
    if not tournament.is_registration_open:
        return redirect('participant_dashboard')

    already_registered = TournamentRegistration.objects.filter(
        tournament=tournament,
        team__captain_user=request.user,
    ).exists()
    if already_registered:
        return redirect('participant_dashboard')

    if tournament.max_teams and TournamentRegistration.objects.filter(tournament=tournament).count() >= tournament.max_teams:
        return redirect('participant_dashboard')

    if request.method == 'POST':
        form = TournamentRegistrationForm(request.POST, user=request.user, tournament=tournament)
        if form.is_valid():
            TournamentRegistration.objects.create(
                tournament=tournament,
                team=form.cleaned_data['team'],
                registered_by=request.user,
                status=TournamentRegistration.Status.PENDING,
            )
            return redirect('participant_dashboard')
    else:
        form = TournamentRegistrationForm(user=request.user, tournament=tournament)

    return render(request, 'register_team_for_tournament.html', {'form': form, 'tournament': tournament})


@login_required
def team_detail(request, team_id):
    if request.user.role != 'captain' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    team_queryset = Team.objects.select_related('captain_user').prefetch_related('registrations__tournament')
    if request.user.is_superuser:
        team = get_object_or_404(team_queryset, id=team_id)
    else:
        team = get_object_or_404(team_queryset, id=team_id, captain_user=request.user)

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

    team_lookup = {'id': team_id}
    if not request.user.is_superuser:
        team_lookup['captain_user'] = request.user
    team = get_object_or_404(Team, **team_lookup)

    if request.method == 'POST':
        form = ParticipantForm(request.POST)
        if form.is_valid():
            participant = form.save(commit=False)
            participant.team = team
            participant.save()
            return redirect('team_detail', team_id=team.id)
    else:
        form = ParticipantForm()

    return render(request, 'add_participant.html', {'form': form, 'team': team})


@login_required
def delete_participant(request, team_id, participant_id):
    if request.user.role != 'captain' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    team_lookup = {'id': team_id}
    if not request.user.is_superuser:
        team_lookup['captain_user'] = request.user
    team = get_object_or_404(Team, **team_lookup)
    participant = get_object_or_404(Participant, id=participant_id, team=team)

    if request.method == 'POST':
        participant.delete()
    return redirect('team_detail', team_id=team.id)


@login_required
def delete_team(request, team_id):
    if request.user.role != 'captain' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    team_lookup = {'id': team_id}
    if not request.user.is_superuser:
        team_lookup['captain_user'] = request.user
    team = get_object_or_404(Team, **team_lookup)

    if request.method == 'POST':
        team.delete()
        return redirect('participant_dashboard')

    return render(request, 'delete_team_confirm.html', {'team': team})


@login_required
def tournament_tasks(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id, is_draft=False)
    if not tournament.is_running:
        return redirect('participant_dashboard')

    has_access = TournamentRegistration.objects.filter(
        tournament=tournament,
        status=TournamentRegistration.Status.APPROVED,
    ).filter(
        Q(team__captain_user=request.user) | Q(team__participants__email=request.user.email)
    ).exists()
    if not has_access and not request.user.is_superuser:
        return redirect('participant_dashboard')

    tasks = Task.objects.filter(tournament=tournament, is_draft=False)
    return render(request, 'tournament_tasks.html', {'tournament': tournament, 'tasks': tasks})


@login_required
def submit_solution(request, task_id):
    task = get_object_or_404(Task.objects.select_related('tournament'), id=task_id, is_draft=False)
    tournament = task.tournament
    if not tournament.is_running:
        return redirect('participant_dashboard')

    team = Team.objects.filter(
        Q(captain_user=request.user) | Q(participants__email=request.user.email),
        registrations__tournament=tournament,
        registrations__status=TournamentRegistration.Status.APPROVED,
    ).distinct().first()
    if not team:
        return redirect('participant_dashboard')

    submission = Submission.objects.filter(team=team, task=task).first()

    if request.method == 'POST':
        form = SubmissionForm(request.POST, instance=submission)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.team = team
            submission.task = task
            submission.save()
            return redirect('team_detail', team_id=team.id)
    else:
        form = SubmissionForm(instance=submission)

    return render(request, 'submit_solution.html', {
        'task': task,
        'team': team,
        'form': form,
        'submission': submission,
    })


@login_required
def team_results(request, team_id):
    if request.user.role not in ['participant', 'captain'] and not request.user.is_superuser:
        return redirect('redirect_by_role')

    team = get_object_or_404(Team, id=team_id)
    if not request.user.is_superuser:
        is_member = (
            team.captain_user_id == request.user.id
            or team.participants.filter(email=request.user.email).exists()
        )
        if not is_member:
            return redirect('participant_dashboard')

    submissions = team.submissions.select_related(
        'task',
        'task__tournament',
    ).prefetch_related(
        'jury_assignments__jury_user',
        'jury_assignments__evaluation',
    )

    result_rows = []
    collected_scores = []
    for submission in submissions:
        row_evaluations = []
        for assignment in submission.jury_assignments.all():
            evaluation = getattr(assignment, 'evaluation', None)
            if evaluation is None:
                continue
            row_evaluations.append({
                'jury_name': assignment.jury_user.username,
                'backend': evaluation.score_backend,
                'frontend': evaluation.score_frontend,
                'functionality': evaluation.score_functionality,
                'ux': evaluation.score_ux,
                'total': evaluation.total_score,
                'comment': evaluation.comment,
                'evaluated_at': evaluation.evaluated_at,
            })

        average_score = mean(item['total'] for item in row_evaluations) if row_evaluations else None
        if average_score is not None:
            collected_scores.append(average_score)

        result_rows.append({
            'submission': submission,
            'evaluations': row_evaluations,
            'average_score': average_score,
            'evaluations_count': len(row_evaluations),
        })

    summary = {
        'submitted_count': submissions.count(),
        'evaluated_count': sum(1 for row in result_rows if row['evaluations_count']),
        'overall_average': mean(collected_scores) if collected_scores else None,
        'best_score': max(collected_scores) if collected_scores else None,
    }

    return render(request, 'team_results.html', {
        'team': team,
        'result_rows': result_rows,
        'summary': summary,
    })
