from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def is_super_admin(user):
    return user.is_superuser


def is_admin_user(user):
    return user.is_superuser or user.role == "admin"


def is_organizer_user(user):
    return user.role == "organizer"


def is_participant_user(user):
    return getattr(user, "role", None) == "participant"


def can_manage_users(user):
    return is_admin_user(user)


def can_create_admins(user):
    return is_admin_user(user)


def can_manage_tournaments(user):
    return is_admin_user(user) or is_organizer_user(user)


def can_review_registrations(user):
    return is_admin_user(user) or is_organizer_user(user)


def can_manage_tournament_instance(user, tournament):
    return is_admin_user(user) or tournament.created_by_id == user.id


def can_manage_registration_instance(user, registration):
    return is_admin_user(user) or registration.tournament.created_by_id == user.id


def can_view_curated_tournament(user, tournament):
    return is_admin_user(user) or tournament.created_by_id == user.id


def get_dashboard_url_for_user(user):
    if is_admin_user(user):
        return reverse("admin_users")
    if is_organizer_user(user):
        return reverse("organizer_dashboard")
    if user.role == "jury":
        return reverse("jury_dashboard")
    return reverse("home")


def get_available_admin_roles(user):
    roles = {"participant", "jury", "organizer"}
    if can_create_admins(user):
        roles.add("admin")
    return roles


def can_export_tournament_results(user, tournament):
    return (
        is_admin_user(user)
        or tournament.created_by_id == user.id
        or tournament.jury_users.filter(id=user.id).exists()
    )


def get_safe_redirect(request, candidate, fallback):
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def get_post_redirect(request, fallback):
    return get_safe_redirect(request, request.POST.get("next"), fallback)
