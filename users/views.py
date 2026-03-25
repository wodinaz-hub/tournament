from statistics import mean

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from tournament.forms import (
    EvaluationForm,
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
    RegistrationMember,
    Submission,
    Task,
    Team,
    Tournament,
    TournamentRegistration,
)
from tournament.services import RegistrationService

from .forms import AdminCreateUserForm, LoginForm, RegisterForm
from .models import CustomUser


def is_super_admin(user):
    return user.is_superuser


def is_admin_user(user):
    return user.is_superuser or user.role == 'admin'


def is_organizer_user(user):
    return user.role == 'organizer'


def can_manage_users(user):
    return is_admin_user(user)


def can_create_admins(user):
    return user.is_superuser


def can_manage_tournaments(user):
    return is_admin_user(user) or is_organizer_user(user)


def can_manage_tournament_instance(user, tournament):
    return is_admin_user(user) or tournament.created_by_id == user.id


def can_manage_registration_instance(user, registration):
    return is_admin_user(user) or registration.tournament.created_by_id == user.id


def get_dashboard_url_for_user(user):
    if is_admin_user(user):
        return reverse('admin_users')
    if is_organizer_user(user):
        return reverse('organizer_dashboard')
    if user.role == 'jury':
        return reverse('jury_dashboard')
    return reverse('home')


def get_available_admin_roles(user):
    roles = {'participant', 'captain', 'jury', 'organizer'}
    if can_create_admins(user):
        roles.add('admin')
    return roles


def build_tournament_leaderboard(tournament):
    approved_registrations = TournamentRegistration.objects.filter(
        tournament=tournament,
        status=TournamentRegistration.Status.APPROVED,
    ).select_related('team')
    submission_qs = Submission.objects.filter(
        task__tournament=tournament,
    ).select_related('team', 'task').prefetch_related(
        'jury_assignments__evaluation',
    )

    submissions_by_team_id = {}
    for submission in submission_qs:
        submissions_by_team_id.setdefault(submission.team_id, []).append(submission)

    leaderboard = []
    for registration in approved_registrations:
        team = registration.team
        submissions = submissions_by_team_id.get(team.id, [])
        submission_averages = []
        evaluations_count = 0

        for submission in submissions:
            scores = []
            for assignment in submission.jury_assignments.all():
                evaluation = getattr(assignment, 'evaluation', None)
                if evaluation is None:
                    continue
                scores.append(evaluation.total_score)
            if scores:
                submission_averages.append(mean(scores))
                evaluations_count += len(scores)

        overall_average = mean(submission_averages) if submission_averages else None
        best_score = max(submission_averages) if submission_averages else None

        leaderboard.append({
            'team': team,
            'overall_average': overall_average,
            'best_score': best_score,
            'scored_tasks': len(submission_averages),
            'submitted_tasks': len(submissions),
            'evaluations_count': evaluations_count,
        })

    leaderboard.sort(
        key=lambda row: (
            row['overall_average'] is None,
            -(row['overall_average'] or 0),
            -(row['best_score'] or 0),
            -row['scored_tasks'],
            -row['submitted_tasks'],
            row['team'].name.lower(),
        )
    )

    previous_signature = None
    place = 0
    for index, row in enumerate(leaderboard, start=1):
        signature = (
            row['overall_average'],
            row['best_score'],
            row['scored_tasks'],
            row['submitted_tasks'],
        )
        if signature != previous_signature:
            place = index
            previous_signature = signature
        row['place'] = place

    return leaderboard


def is_tournament_edit_locked(tournament):
    return (
        not tournament.is_draft
        and tournament.registration_end is not None
        and tournament.registration_end <= timezone.now()
    )


def user_has_registration_access(user, registration):
    return (
        registration.team.captain_user_id == user.id
        or registration.members.filter(user=user).exists()
    )


def build_admin_dashboard_context(current_user, admin_create_user_form=None):
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
    registrations = TournamentRegistration.objects.select_related(
        'tournament',
        'team',
        'registered_by',
    ).prefetch_related('members').all()
    for registration in registrations:
        fields_by_key = {
            field['key']: field.get('label', field['key'])
            for field in registration.tournament.registration_fields_config
        }
        members_by_key = {
            field['key']
            for field in registration.tournament.registration_fields_config
            if field.get('type') == 'participants'
        }
        registration.display_form_answers = [
            {
                'label': fields_by_key.get(key, key),
                'value': (
                    ', '.join(
                        f"{member.full_name} ({member.email})"
                        for member in registration.members.all()
                    )
                    if key in members_by_key
                    else value
                ),
            }
            for key, value in registration.form_answers.items()
        ]

    return {
        'all_users': all_users,
        'admin_create_user_form': admin_create_user_form or AdminCreateUserForm(
            available_roles=get_available_admin_roles(current_user),
        ),
        'role_choices': [
            choice for choice in CustomUser.ROLE_CHOICES
            if choice[0] in get_available_admin_roles(current_user)
        ],
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


def build_admin_nav_items():
    return [
        {'url': reverse('admin_users'), 'label': 'Користувачі'},
        {'url': reverse('admin_users') + '?action=create-user', 'label': 'Створити користувача'},
        {'url': reverse('admin_active_tournaments'), 'label': 'Активні турніри'},
        {'url': reverse('admin_inactive_tournaments'), 'label': 'Неактивні турніри'},
        {'url': reverse('admin_active_tournaments') + '?action=create-tournament', 'label': 'Створити турнір'},
        {'url': reverse('admin_teams'), 'label': 'Команди'},
        {'url': reverse('admin_registrations'), 'label': 'Заявки'},
        {'url': reverse('admin_submissions'), 'label': 'Роботи'},
    ]


def render_admin_section(request, section, action=None, admin_create_user_form=None, tournament_form=None):
    if not is_admin_user(request.user):
        return redirect('redirect_by_role')
    if action is None:
        action = request.GET.get('action')
    context = build_admin_dashboard_context(request.user)
    context.update({
        'current_section': section,
        'admin_nav_items': build_admin_nav_items(),
        'current_action': action,
        'admin_create_user_form': admin_create_user_form or AdminCreateUserForm(
            available_roles=get_available_admin_roles(request.user),
        ),
        'tournament_form': tournament_form or TournamentForm(),
    })
    return render(request, 'admin_section.html', context)


def get_safe_redirect(request, candidate, fallback):
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def get_post_redirect(request, fallback):
    return get_safe_redirect(request, request.POST.get('next'), fallback)


def build_public_tournament_rows():
    tournaments = list(
        Tournament.objects.filter(is_draft=False).prefetch_related('tasks').select_related('created_by').order_by(
            'registration_start',
            'start_date',
            'name',
        )
    )
    rows = []
    for tournament in tournaments:
        rows.append({
            'tournament': tournament,
            'approved_count': TournamentRegistration.objects.filter(
                tournament=tournament,
                status=TournamentRegistration.Status.APPROVED,
            ).count(),
            'pending_count': TournamentRegistration.objects.filter(
                tournament=tournament,
                status=TournamentRegistration.Status.PENDING,
            ).count(),
            'leaderboard_preview': build_tournament_leaderboard(tournament)[:3],
        })
    return rows


def home(request):
    tournament_rows = build_public_tournament_rows()
    featured_tournaments = [row for row in tournament_rows if row['tournament'].is_registration_open][:3]
    active_tournaments = [row for row in tournament_rows if row['tournament'].is_running][:3]
    finished_tournaments = [row for row in tournament_rows if row['tournament'].is_finished][:3]
    news_rows = []
    for row in tournament_rows[:4]:
        tournament = row['tournament']
        if tournament.is_registration_open:
            text = 'Відкрита реєстрація. Можна подавати заявки.'
        elif tournament.is_running:
            text = 'Турнір уже триває.'
        elif tournament.is_finished:
            text = 'Турнір завершено. Доступний підсумковий лідерборд.'
        else:
            text = 'Турнір заплановано. Слідкуйте за датами старту.'
        news_rows.append({'tournament': tournament, 'text': text})

    return render(request, 'home.html', {
        'tournament_rows': tournament_rows,
        'featured_tournaments': featured_tournaments,
        'active_tournaments': active_tournaments,
        'finished_tournaments': finished_tournaments,
        'news_rows': news_rows,
    })


def register_view(request):
    next_url = request.GET.get('next') or request.POST.get('next')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'participant'
            user.is_approved = True
            user.save()
            RegistrationMember.objects.filter(
                user__isnull=True,
                email__iexact=user.email,
            ).update(user=user)
            login(request, user)
            return redirect(get_safe_redirect(request, next_url, reverse('home')))
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form, 'next_url': next_url})


def login_view(request):
    message = ''
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.user.is_authenticated:
        return redirect(get_safe_redirect(request, next_url, reverse('redirect_by_role')))

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_approved and not user.is_superuser:
                message = 'Ваш акаунт ще не схвалений адміністратором.'
            else:
                login(request, user)
                return redirect(get_safe_redirect(request, next_url, reverse('redirect_by_role')))
        else:
            message = 'Неправильний логін або пароль.'
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form, 'message': message, 'next_url': next_url})


@login_required
def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def redirect_by_role(request):
    user = request.user

    if is_admin_user(user) or is_organizer_user(user):
        return redirect('home')
    if user.role == 'jury':
        return redirect('jury_dashboard')
    return redirect('home')


def public_tournament_detail(request, tournament_id):
    tournament = get_object_or_404(
        Tournament.objects.prefetch_related('tasks').select_related('created_by'),
        id=tournament_id,
        is_draft=False,
    )
    leaderboard = build_tournament_leaderboard(tournament)
    existing_registration = None
    registration_form = None
    can_submit_registration = False
    viewer_can_register = (
        request.user.is_authenticated
        and (request.user.is_superuser or request.user.role in ['participant', 'captain'])
    )

    if request.user.is_authenticated:
        existing_registration = TournamentRegistration.objects.filter(
            tournament=tournament,
            team__captain_user=request.user,
        ).order_by('-created_at').first()

    if viewer_can_register and tournament.is_registration_open:
        registration_form = TournamentRegistrationForm(
            request.POST if request.method == 'POST' else None,
            user=request.user,
            tournament=tournament,
        )
        can_submit_registration = True

        if request.method == 'POST':
            if existing_registration and existing_registration.status in [
                TournamentRegistration.Status.PENDING,
                TournamentRegistration.Status.APPROVED,
            ]:
                return redirect('public_tournament_detail', tournament_id=tournament.id)

            if (
                tournament.max_teams
                and TournamentRegistration.objects.filter(
                    tournament=tournament,
                    status__in=[
                        TournamentRegistration.Status.PENDING,
                        TournamentRegistration.Status.APPROVED,
                    ],
                ).count() >= tournament.max_teams
            ):
                return redirect('public_tournament_detail', tournament_id=tournament.id)

            if registration_form.is_valid():
                if request.user.role == 'participant':
                    request.user.role = 'captain'
                    request.user.save(update_fields=['role'])
                try:
                    RegistrationService.submit_registration(
                        tournament=tournament,
                        registered_by=request.user,
                        captain_user=request.user,
                        team_data=registration_form.cleaned_team_data(),
                        form_answers=registration_form.cleaned_form_answers(),
                        roster=registration_form.cleaned_participants(),
                    )
                except ValidationError as exc:
                    registration_form.add_error(None, exc)
                else:
                    return redirect('participant_dashboard')

    current_path = reverse('public_tournament_detail', args=[tournament.id])
    return render(request, 'public_tournament_detail.html', {
        'tournament': tournament,
        'tasks': tournament.tasks.filter(is_draft=False),
        'leaderboard_preview': leaderboard[:5],
        'leaderboard_total': len(leaderboard),
        'registration_form': registration_form,
        'existing_registration': existing_registration,
        'viewer_can_register': viewer_can_register,
        'can_submit_registration': can_submit_registration,
        'register_url': f"{reverse('register')}?next={current_path}",
        'login_url': f"{reverse('login')}?next={current_path}",
    })


@login_required
def admin_dashboard(request):
    return redirect('admin_users')


@login_required
def admin_users(request):
    return render_admin_section(request, 'users')


@login_required
def admin_active_tournaments(request):
    return render_admin_section(request, 'active_tournaments')


@login_required
def admin_inactive_tournaments(request):
    return render_admin_section(request, 'inactive_tournaments')


@login_required
def admin_teams(request):
    return render_admin_section(request, 'teams')


@login_required
def admin_registrations(request):
    return render_admin_section(request, 'registrations')


@login_required
def admin_submissions(request):
    return render_admin_section(request, 'submissions')


@login_required
def organizer_dashboard(request):
    if not is_organizer_user(request.user):
        return redirect('redirect_by_role')

    tournaments = Tournament.objects.filter(created_by=request.user).prefetch_related('tasks', 'jury_users')
    registrations = TournamentRegistration.objects.filter(
        tournament__created_by=request.user,
    ).select_related('tournament', 'team', 'registered_by')
    return render(request, 'organizer_dashboard.html', {
        'tournaments': tournaments.order_by('-start_date', 'name'),
        'registrations': registrations.order_by('-created_at'),
    })


@login_required
def create_user_by_admin(request):
    if not is_admin_user(request.user):
        return redirect('redirect_by_role')
    if request.method == 'GET':
        return redirect(reverse('admin_users') + '?action=create-user')
    if request.method != 'POST':
        return HttpResponseNotAllowed(['GET', 'POST'])

    form = AdminCreateUserForm(request.POST, available_roles=get_available_admin_roles(request.user))
    if form.is_valid():
        user = form.save(commit=False)
        user.is_approved = user.role == 'participant'
        user.save()
        fallback = reverse('admin_users') if is_admin_user(request.user) else get_dashboard_url_for_user(request.user)
        return redirect(get_post_redirect(request, fallback))
    return render_admin_section(
        request,
        'users',
        action='create-user',
        admin_create_user_form=form,
    )


@login_required
def approve_user(request, user_id):
    if not can_manage_users(request.user):
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    user = get_object_or_404(CustomUser, id=user_id)
    if user.id == request.user.id and not request.user.is_superuser:
        return redirect(reverse('admin_users'))

    user.is_approved = True
    user.save(update_fields=['is_approved'])
    return redirect(get_post_redirect(request, reverse('admin_users')))


@login_required
def update_user_role(request, user_id):
    if not can_manage_users(request.user):
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return redirect(reverse('admin_users'))

    user = get_object_or_404(CustomUser, id=user_id)
    new_role = request.POST.get('role')
    allowed_roles = get_available_admin_roles(request.user)
    if new_role not in allowed_roles:
        return redirect(reverse('admin_users'))
    if user.is_superuser:
        return redirect(reverse('admin_users'))

    user.role = new_role
    if new_role == 'participant':
        user.is_approved = True
    user.save(update_fields=['role', 'is_approved'])
    return redirect(get_post_redirect(request, reverse('admin_users')))


@login_required
def delete_user(request, user_id):
    if not can_manage_users(request.user):
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return redirect(reverse('admin_users'))

    user = get_object_or_404(CustomUser, id=user_id)
    if user.id == request.user.id or user.is_superuser:
        return redirect(reverse('admin_users'))

    user.delete()
    return redirect(get_post_redirect(request, reverse('admin_users')))


@login_required
def approve_registration(request, registration_id):
    if not can_manage_tournaments(request.user):
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    registration = get_object_or_404(TournamentRegistration, id=registration_id)
    if not can_manage_registration_instance(request.user, registration):
        return redirect('redirect_by_role')
    registration.status = TournamentRegistration.Status.APPROVED
    registration.save(update_fields=['status'])
    fallback = reverse('admin_registrations') if is_admin_user(request.user) else get_dashboard_url_for_user(request.user)
    return redirect(get_post_redirect(request, fallback))


@login_required
def reject_registration(request, registration_id):
    if not can_manage_tournaments(request.user):
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    registration = get_object_or_404(TournamentRegistration, id=registration_id)
    if not can_manage_registration_instance(request.user, registration):
        return redirect('redirect_by_role')
    registration.status = TournamentRegistration.Status.REJECTED
    registration.save(update_fields=['status'])
    fallback = reverse('admin_registrations') if is_admin_user(request.user) else get_dashboard_url_for_user(request.user)
    return redirect(get_post_redirect(request, fallback))


@login_required
def create_tournament(request):
    if not can_manage_tournaments(request.user):
        return redirect('redirect_by_role')

    if request.method == 'GET' and is_admin_user(request.user):
        return redirect(reverse('admin_active_tournaments') + '?action=create-tournament')

    if request.method == 'POST':
        form = TournamentForm(request.POST)
        if form.is_valid():
            tournament = form.save(commit=False)
            tournament.created_by = request.user
            tournament.save()
            form.save_m2m()
            return redirect(reverse('admin_active_tournaments') if is_admin_user(request.user) else get_dashboard_url_for_user(request.user))
        if is_admin_user(request.user):
            return render_admin_section(
                request,
                'active_tournaments',
                action='create-tournament',
                tournament_form=form,
            )
    else:
        form = TournamentForm()

    return render(
        request,
        'create_tournament.html',
        {
            'form': form,
            'mode': 'create',
            'dashboard_url': reverse('admin_active_tournaments') if is_admin_user(request.user) else get_dashboard_url_for_user(request.user),
        },
    )


@login_required
def edit_tournament(request, tournament_id):
    if not can_manage_tournaments(request.user):
        return redirect('redirect_by_role')

    tournament = get_object_or_404(Tournament, id=tournament_id)
    if not can_manage_tournament_instance(request.user, tournament):
        return redirect('redirect_by_role')
    if is_tournament_edit_locked(tournament):
        return redirect(get_dashboard_url_for_user(request.user))

    if request.method == 'POST':
        form = TournamentForm(request.POST, instance=tournament)
        if form.is_valid():
            form.save()
            return redirect(reverse('admin_active_tournaments') if is_admin_user(request.user) else get_dashboard_url_for_user(request.user))
    else:
        form = TournamentForm(instance=tournament)

    return render(request, 'create_tournament.html', {
        'form': form,
        'mode': 'edit',
        'tournament': tournament,
        'tasks': tournament.tasks.all(),
        'dashboard_url': reverse('admin_active_tournaments') if is_admin_user(request.user) else get_dashboard_url_for_user(request.user),
    })


@login_required
def delete_tournament(request, tournament_id):
    if not can_manage_tournaments(request.user):
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return redirect(get_dashboard_url_for_user(request.user))

    tournament = get_object_or_404(Tournament, id=tournament_id)
    if not can_manage_tournament_instance(request.user, tournament):
        return redirect('redirect_by_role')
    tournament.delete()
    fallback = reverse('admin_active_tournaments') if is_admin_user(request.user) else get_dashboard_url_for_user(request.user)
    return redirect(get_post_redirect(request, fallback))


@login_required
def create_task(request, tournament_id=None):
    if not can_manage_tournaments(request.user):
        return redirect('redirect_by_role')

    tournament = None
    if tournament_id is not None:
        tournament = get_object_or_404(Tournament, id=tournament_id)
        if not can_manage_tournament_instance(request.user, tournament):
            return redirect('redirect_by_role')
        if is_tournament_edit_locked(tournament):
            return redirect(get_dashboard_url_for_user(request.user))

    if request.method == 'POST':
        form = TaskForm(request.POST, tournament=tournament)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            return redirect('edit_tournament', tournament_id=task.tournament_id)
    else:
        form = TaskForm(tournament=tournament)

    return render(request, 'create_task.html', {
        'form': form,
        'mode': 'create',
        'tournament': tournament,
        'back_url': (
            reverse('edit_tournament', args=[tournament.id])
            if tournament is not None else (
                reverse('admin_active_tournaments') if is_admin_user(request.user) else get_dashboard_url_for_user(request.user)
            )
        ),
    })


@login_required
def edit_task(request, task_id):
    if not can_manage_tournaments(request.user):
        return redirect('redirect_by_role')

    task = get_object_or_404(Task, id=task_id)
    if not can_manage_tournament_instance(request.user, task.tournament):
        return redirect('redirect_by_role')
    if is_tournament_edit_locked(task.tournament):
        return redirect(get_dashboard_url_for_user(request.user))

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            return redirect('edit_tournament', tournament_id=task.tournament_id)
    else:
        form = TaskForm(instance=task)

    return render(request, 'create_task.html', {
        'form': form,
        'mode': 'edit',
        'task': task,
        'tournament': task.tournament,
        'back_url': reverse('edit_tournament', args=[task.tournament_id]),
    })


@login_required
def delete_task(request, task_id):
    if not can_manage_tournaments(request.user):
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return redirect(get_dashboard_url_for_user(request.user))

    task = get_object_or_404(Task, id=task_id)
    if not can_manage_tournament_instance(request.user, task.tournament):
        return redirect('redirect_by_role')
    task.delete()
    fallback = reverse('admin_active_tournaments') if is_admin_user(request.user) else get_dashboard_url_for_user(request.user)
    return redirect(get_post_redirect(request, fallback))


@login_required
def jury_dashboard(request):
    if request.user.role != 'jury' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    tournaments = Tournament.objects.filter(is_draft=False).prefetch_related(
        'tasks__submissions__team',
    ).order_by('-start_date')
    if not request.user.is_superuser:
        tournaments = tournaments.filter(jury_users=request.user)

    tournament_rows = []
    for tournament in tournaments:
        submissions = Submission.objects.filter(
            task__tournament=tournament,
        ).select_related('team', 'task')
        tournament_rows.append({
            'tournament': tournament,
            'teams_count': submissions.values('team_id').distinct().count(),
            'submissions_count': submissions.count(),
        })

    return render(request, 'jury_dashboard.html', {'tournament_rows': tournament_rows})


@login_required
def jury_tournament_detail(request, tournament_id):
    if request.user.role != 'jury' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    tournament = get_object_or_404(Tournament, id=tournament_id, is_draft=False)
    if not request.user.is_superuser and not tournament.jury_users.filter(id=request.user.id).exists():
        return redirect('jury_dashboard')
    submissions = Submission.objects.filter(
        task__tournament=tournament,
    ).select_related('team', 'task').prefetch_related(
        'jury_assignments__jury_user',
        'jury_assignments__evaluation',
    ).order_by('team__name', 'task__title')

    pending_team_map = {}
    evaluated_team_map = {}
    for submission in submissions:
        assignment = JuryAssignment.objects.filter(
            jury_user=request.user,
            submission=submission,
        ).first()
        evaluation = getattr(assignment, 'evaluation', None) if assignment else None
        target_map = evaluated_team_map if evaluation else pending_team_map
        team_bucket = target_map.setdefault(submission.team_id, {
            'team': submission.team,
            'submissions': [],
        })
        team_bucket['submissions'].append({
            'submission': submission,
            'my_evaluation': evaluation,
            'evaluation_form': EvaluationForm(
                instance=evaluation,
                prefix=f'eval-{submission.id}',
            ),
        })

    return render(request, 'jury_tournament_detail.html', {
        'tournament': tournament,
        'pending_team_rows': list(pending_team_map.values()),
        'evaluated_team_rows': list(evaluated_team_map.values()),
    })


@login_required
def submit_evaluation(request, submission_id):
    if request.user.role != 'jury' and not request.user.is_superuser:
        return redirect('redirect_by_role')
    if request.method != 'POST':
        return redirect('jury_dashboard')

    submission = get_object_or_404(
        Submission.objects.select_related('task', 'task__tournament'),
        id=submission_id,
    )
    if (
        not request.user.is_superuser
        and not submission.task.tournament.jury_users.filter(id=request.user.id).exists()
    ):
        return redirect('jury_dashboard')
    assignment, _ = JuryAssignment.objects.get_or_create(
        jury_user=request.user,
        submission=submission,
    )
    evaluation = getattr(assignment, 'evaluation', None)
    form = EvaluationForm(
        request.POST,
        instance=evaluation,
        prefix=f'eval-{submission.id}',
    )
    if form.is_valid():
        saved_evaluation = form.save(commit=False)
        saved_evaluation.assignment = assignment
        saved_evaluation.save()

    return redirect('jury_tournament_detail', tournament_id=submission.task.tournament_id)


@login_required
def participant_dashboard(request):
    return profile_view(request)


@login_required
def profile_view(request):
    if request.user.role not in ['participant', 'captain'] and not request.user.is_superuser:
        return redirect('redirect_by_role')

    my_teams = Team.objects.filter(
        Q(captain_user=request.user) | Q(participants__email=request.user.email)
    ).select_related('captain_user').prefetch_related(
        'participants',
        'registrations__tournament',
    ).distinct()

    visible_tournaments = list(
        Tournament.objects.filter(is_draft=False).order_by('-start_date')
    )

    my_registrations = list(TournamentRegistration.objects.select_related(
        'tournament',
        'team',
        'team__captain_user',
    ).prefetch_related('team__participants', 'members').filter(
        Q(team__captain_user=request.user) | Q(members__user=request.user)
    ).distinct())

    my_registration_by_tournament_id = {}
    for reg in my_registrations:
        current = my_registration_by_tournament_id.get(reg.tournament_id)
        if current is None:
            my_registration_by_tournament_id[reg.tournament_id] = reg
            continue
        if current.status == TournamentRegistration.Status.REJECTED and reg.status != TournamentRegistration.Status.REJECTED:
            my_registration_by_tournament_id[reg.tournament_id] = reg

    tournaments_with_state = []
    for tournament in visible_tournaments:
        existing_registration = my_registration_by_tournament_id.get(tournament.id)
        active_registration = (
            existing_registration
            if existing_registration is not None
            and existing_registration.status != TournamentRegistration.Status.REJECTED
            else None
        )
        can_register = (
            request.user.role in ['participant', 'captain']
            and tournament.is_registration_open
            and active_registration is None
        )
        can_open_tasks = (
            active_registration is not None
            and active_registration.status == TournamentRegistration.Status.APPROVED
            and (tournament.is_running or tournament.is_finished)
        )

        tournaments_with_state.append({
            'tournament': tournament,
            'my_registration': existing_registration,
            'my_team': active_registration.team if active_registration else None,
            'can_register': can_register,
            'can_open_tasks': can_open_tasks,
            'can_view_leaderboard': (
                active_registration is not None
                and active_registration.status == TournamentRegistration.Status.APPROVED
                and tournament.start_date <= timezone.now()
            ),
        })

    return render(request, 'profile.html', {
        'profile_user': request.user,
        'my_teams': my_teams,
        'tournaments_with_state': tournaments_with_state,
    })


@login_required
def my_team_view(request):
    if request.user.role not in ['participant', 'captain'] and not request.user.is_superuser:
        return redirect('redirect_by_role')

    team = Team.objects.filter(
        Q(captain_user=request.user) | Q(participants__email=request.user.email)
    ).order_by('name').first()
    if team is not None:
        return redirect('team_detail', team_id=team.id)
    return redirect('create_team')


@login_required
def create_team(request):
    if request.user.role not in ['participant', 'captain'] and not request.user.is_superuser:
        return redirect('profile')

    next_url = request.GET.get('next') or request.POST.get('next')

    if Team.objects.filter(captain_user=request.user).exists():
        return redirect(get_safe_redirect(request, next_url, reverse('participant_dashboard')))

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
            return redirect(get_safe_redirect(request, next_url, reverse('participant_dashboard')))
    else:
        form = TeamForm(initial={
            'captain_name': request.user.username,
            'captain_email': request.user.email,
        })

    return render(request, 'create_team.html', {'form': form, 'next_url': next_url, 'mode': 'create'})


@login_required
def register_team_for_tournament(request, tournament_id):
    if request.user.role not in ['participant', 'captain'] and not request.user.is_superuser:
        return redirect('redirect_by_role')

    tournament = get_object_or_404(Tournament, id=tournament_id, is_draft=False)
    if not tournament.is_registration_open:
        return redirect('profile')

    already_registered = TournamentRegistration.objects.filter(
        tournament=tournament,
        team__captain_user=request.user,
        status__in=[
            TournamentRegistration.Status.PENDING,
            TournamentRegistration.Status.APPROVED,
        ],
    ).exists()
    if already_registered:
        return redirect('profile')

    if (
        tournament.max_teams
        and TournamentRegistration.objects.filter(
            tournament=tournament,
            status__in=[
                TournamentRegistration.Status.PENDING,
                TournamentRegistration.Status.APPROVED,
            ],
        ).count()
        >= tournament.max_teams
    ):
        return redirect('profile')

    if request.method == 'POST':
        form = TournamentRegistrationForm(request.POST, user=request.user, tournament=tournament)
        if form.is_valid():
            if request.user.role == 'participant':
                request.user.role = 'captain'
                request.user.save(update_fields=['role'])
            try:
                RegistrationService.submit_registration(
                    tournament=tournament,
                    registered_by=request.user,
                    captain_user=request.user,
                    team_data=form.cleaned_team_data(),
                    form_answers=form.cleaned_form_answers(),
                    roster=form.cleaned_participants(),
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                return redirect('participant_dashboard')
    else:
        form = TournamentRegistrationForm(user=request.user, tournament=tournament)

    return render(request, 'register_team_for_tournament.html', {'form': form, 'tournament': tournament})


@login_required
def team_detail(request, team_id):
    team_queryset = Team.objects.select_related('captain_user').prefetch_related('registrations__tournament')
    if request.user.is_superuser:
        team = get_object_or_404(team_queryset, id=team_id)
    elif request.user.role == 'captain':
        team = get_object_or_404(team_queryset, id=team_id, captain_user=request.user)
    else:
        team = get_object_or_404(team_queryset, id=team_id, participants__email=request.user.email)

    submissions = team.submissions.select_related('task', 'task__tournament').all()
    return render(request, 'team_detail.html', {
        'team': team,
        'participants_count': team.participants.count(),
        'submissions': submissions,
        'participant_form': ParticipantForm(),
        'can_manage_team': request.user.is_superuser or team.captain_user_id == request.user.id,
        'can_edit_team': request.user.is_superuser or team.captain_user_id == request.user.id,
        'can_leave_team': (
            not request.user.is_superuser
            and team.captain_user_id != request.user.id
            and team.participants.filter(email=request.user.email).exists()
        ),
    })


@login_required
def edit_team(request, team_id):
    team_lookup = {'id': team_id}
    if not request.user.is_superuser:
        team_lookup['captain_user'] = request.user
    team = get_object_or_404(Team, **team_lookup)

    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            return redirect('team_detail', team_id=team.id)
    else:
        form = TeamForm(instance=team)

    return render(request, 'create_team.html', {
        'form': form,
        'next_url': reverse('team_detail', args=[team.id]),
        'mode': 'edit',
    })


@login_required
def team_participants(request, team_id):
    team_queryset = Team.objects.select_related('captain_user').prefetch_related('participants')
    if request.user.is_superuser:
        team = get_object_or_404(team_queryset, id=team_id)
    elif request.user.role == 'captain':
        team = get_object_or_404(team_queryset, id=team_id, captain_user=request.user)
    else:
        team = get_object_or_404(team_queryset, id=team_id, participants__email=request.user.email)

    participants = team.participants.all().order_by('full_name')
    return render(request, 'team_participants.html', {
        'team': team,
        'participants': participants,
        'can_manage_team': request.user.is_superuser or team.captain_user_id == request.user.id,
        'can_leave_team': (
            not request.user.is_superuser
            and team.captain_user_id != request.user.id
            and team.participants.filter(email=request.user.email).exists()
        ),
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
def leave_team(request, team_id):
    if request.user.role != 'participant' and not request.user.is_superuser:
        return redirect('redirect_by_role')

    team = get_object_or_404(Team, id=team_id)
    participant = get_object_or_404(Participant, team=team, email=request.user.email)

    if request.method == 'POST':
        participant.delete()
    return redirect('participant_dashboard')


@login_required
def tournament_tasks(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id, is_draft=False)
    if not (tournament.is_running or tournament.is_finished):
        return redirect('participant_dashboard')

    approved_registrations = TournamentRegistration.objects.filter(
        tournament=tournament,
        status=TournamentRegistration.Status.APPROVED,
    ).select_related('team', 'team__captain_user').prefetch_related('team__participants', 'members')
    my_registration = next(
        (registration for registration in approved_registrations if user_has_registration_access(request.user, registration)),
        None,
    )
    has_access = my_registration is not None
    if not has_access and not request.user.is_superuser:
        return redirect('participant_dashboard')

    tasks = Task.objects.filter(tournament=tournament, is_draft=False)
    leaderboard = build_tournament_leaderboard(tournament)
    my_team = my_registration.team if my_registration is not None else None
    preview_rows = leaderboard[:5]
    return render(request, 'tournament_tasks.html', {
        'tournament': tournament,
        'tasks': tasks,
        'leaderboard_preview': preview_rows,
        'leaderboard_total': len(leaderboard),
        'my_team': my_team,
        'can_submit_solutions': tournament.is_running,
        'show_official_solutions': tournament.is_finished,
    })


@login_required
def tournament_leaderboard(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id, is_draft=False)
    approved_registrations = TournamentRegistration.objects.filter(
        tournament=tournament,
        status=TournamentRegistration.Status.APPROVED,
    ).select_related('team', 'team__captain_user').prefetch_related('team__participants', 'members')
    my_registration = next(
        (registration for registration in approved_registrations if user_has_registration_access(request.user, registration)),
        None,
    )
    if my_registration is None and not request.user.is_superuser:
        return redirect('participant_dashboard')

    leaderboard = build_tournament_leaderboard(tournament)
    my_team = my_registration.team if my_registration is not None else None

    return render(request, 'tournament_leaderboard.html', {
        'tournament': tournament,
        'leaderboard': leaderboard,
        'my_team': my_team,
    })


@login_required
def submit_solution(request, task_id):
    task = get_object_or_404(Task.objects.select_related('tournament'), id=task_id, is_draft=False)
    tournament = task.tournament
    if not tournament.is_running:
        return redirect('participant_dashboard')

    approved_registrations = TournamentRegistration.objects.filter(
        tournament=tournament,
        status=TournamentRegistration.Status.APPROVED,
    ).select_related('team', 'team__captain_user').prefetch_related('team__participants', 'members')
    my_registration = next(
        (registration for registration in approved_registrations if user_has_registration_access(request.user, registration)),
        None,
    )
    team = my_registration.team if my_registration is not None else None
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
