# teams/views.py
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.template.loader import render_to_string
from django.db.models import Count, Q
from .models import Team, TeamMembership, TeamInvite
from .forms import TeamCreateForm

User = get_user_model()


# =============================
# ВСПОМОГАТЕЛЬНЫЕ УТИЛИТЫ
# =============================

def _is_htmx(request) -> bool:
    """Проверка, является ли запрос HTMX-запросом."""
    return request.headers.get("HX-Request") == "true"


# =============================
# ОСНОВНЫЕ СТРАНИЦЫ
# =============================
@login_required
def my_teams(request):
    memberships = (
        TeamMembership.objects
        .filter(user=request.user)
        .select_related('team')
        .annotate(  # ← добавим поле m.pending_invites
            pending_invites=Count(
                'team__invites',
                filter=Q(team__invites__status=TeamInvite.Status.PENDING)
            )
        )
    )
    return render(request, 'teams/my_teams.html', {
        'memberships': memberships,
    })


@login_required
def team_create(request):
    if request.method == "POST":
        form = TeamCreateForm(request.POST, request.FILES)
        if form.is_valid():
            team = form.save(commit=False)
            team.captain = request.user
            team.save()
            TeamMembership.objects.create(user=request.user, team=team, role="captain")
            messages.success(request, "Команда создана!")
            return redirect("teams:team_detail", slug=team.slug)
    else:
        form = TeamCreateForm()
    return render(request, "teams/team_create.html", {"form": form})


def team_detail(request, slug):
    """Главная страница команды."""
    team = get_object_or_404(Team, slug=slug)
    members = team.memberships.select_related("user").order_by("-role", "user__username")

    outgoing_invites = TeamInvite.objects.filter(
        team=team, status=TeamInvite.Status.PENDING
    ).select_related("invited_user").order_by("-created_at")

    invite_link = request.build_absolute_uri(
        reverse("teams:join_by_code", args=[str(team.invite_code)])
    )

    return render(
        request,
        "teams/team_detail.html",
        {
            "team": team,
            "members": members,
            "invite_link": invite_link,
            "outgoing_invites": outgoing_invites,
        },
    )


# =============================
# ЧЛЕНСТВО
# =============================

@login_required
def join_by_code(request, code):
    team = get_object_or_404(Team, invite_code=code)
    tm, created = TeamMembership.objects.get_or_create(
        user=request.user, team=team, defaults={"role": "player"}
    )
    if created:
        messages.success(request, f"Вы вступили в команду [{team.tag}] {team.name}")
    else:
        messages.info(request, "Вы уже состоите в этой команде.")
    return redirect("teams:team_detail", slug=team.slug)


@login_required
def leave_team(request, slug):
    team = get_object_or_404(Team, slug=slug)
    membership = get_object_or_404(TeamMembership, user=request.user, team=team)
    if membership.role == "captain":
        messages.error(request, "Капитан не может выйти. Сначала передайте роль капитана.")
        return redirect("teams:team_detail", slug=team.slug)
    membership.delete()
    messages.success(request, "Вы покинули команду.")
    return redirect("teams:my_teams")


@login_required
def transfer_captain(request, slug, user_id):
    team = get_object_or_404(Team, slug=slug)
    if team.captain_id != request.user.id:
        messages.error(request, "Только капитан может передать капитанство.")
        return redirect("teams:team_detail", slug=team.slug)

    new_cap = get_object_or_404(TeamMembership, team=team, user_id=user_id)
    TeamMembership.objects.filter(team=team, user=team.captain).update(role="player")
    TeamMembership.objects.filter(team=team, user=new_cap.user).update(role="captain")
    team.captain = new_cap.user
    team.save(update_fields=["captain"])
    messages.success(request, "Капитанство передано.")
    return redirect("teams:team_detail", slug=team.slug)


@login_required
def remove_member(request, slug, user_id):
    team = get_object_or_404(Team, slug=slug)
    if team.captain_id != request.user.id:
        messages.error(request, "Только капитан может исключать игроков.")
        return redirect("teams:team_detail", slug=team.slug)
    if user_id == team.captain_id:
        messages.error(request, "Нельзя удалить капитана.")
        return redirect("teams:team_detail", slug=team.slug)
    TeamMembership.objects.filter(team=team, user_id=user_id).delete()
    messages.success(request, "Игрок удалён из команды.")
    return redirect("teams:team_detail", slug=team.slug)


# =============================
# ПОИСК И ИНВАЙТЫ
# =============================

@login_required
def user_search(request, slug):
    team = get_object_or_404(Team, slug=slug)
    if team.captain_id != request.user.id:
        return HttpResponseForbidden("Only captain can invite")

    q = (request.GET.get("q") or "").strip()

    # уже в команде / уже приглашены
    existing_ids = TeamMembership.objects.filter(team=team).values_list("user_id", flat=True)
    invited_ids = TeamInvite.objects.filter(
        team=team, status=TeamInvite.Status.PENDING
    ).values_list("invited_user_id", flat=True)

    # базовый набор кандидатов
    candidates = (
        User.objects
        .filter(is_active=True)
        # исключаем «социальные/технические» записи без нормального пароля
        .exclude(password__startswith="!")
        # и без почты, чтобы отсечь импортированные «стим-ники»
        .exclude(email__isnull=True)
        .exclude(email__exact="")
        # не показываем себя, уже добавленных и уже приглашённых
        .exclude(id=request.user.id)
        .exclude(id__in=list(existing_ids) + list(invited_ids))
        .order_by("username")
    )

    if q:
        candidates = candidates.filter(username__istartswith=q)
    else:
        candidates = candidates[:5]  # дефолтные подсказки

    return render(request, "teams/_user_search_results.html", {
        "team": team,
        "candidates": candidates,
    })


@login_required
def send_invite(request, slug):
    """Создание/возобновление инвайта"""
    if request.method != "POST":
        return HttpResponse(status=405)
    team = get_object_or_404(Team, slug=slug)
    if team.captain_id != request.user.id:
        return HttpResponseForbidden("Only captain can invite")

    try:
        user_id = int(request.POST.get("user_id"))
    except (TypeError, ValueError):
        return HttpResponse("Bad user_id", status=400)

    target = get_object_or_404(User, id=user_id)
    if TeamMembership.objects.filter(team=team, user=target).exists():
        return HttpResponse(status=204)

    invite, created = TeamInvite.objects.get_or_create(
        team=team,
        invited_user=target,
        defaults={"invited_by": request.user, "status": TeamInvite.Status.PENDING},
    )

    if not created and invite.status != TeamInvite.Status.PENDING:
        invite.status = TeamInvite.Status.PENDING
        invite.invited_by = request.user
        invite.created_at = timezone.now()
        invite.responded_at = None
        invite.save()

    q = (request.POST.get("q") or "").strip()
    existing_ids = TeamMembership.objects.filter(team=team).values_list("user_id", flat=True)
    invited_ids = TeamInvite.objects.filter(
        team=team, status=TeamInvite.Status.PENDING
    ).values_list("invited_user_id", flat=True)

    candidates = (
        User.objects
        .filter(is_active=True)
        .exclude(password__startswith="!")      # ⬅️ как в user_search
        .exclude(email__isnull=True)            # ⬅️
        .exclude(email__exact="")               # ⬅️
        .exclude(id=request.user.id)            # ⬅️
        .exclude(id__in=list(existing_ids) + list(invited_ids))
        .order_by("username")
    )

    q = (request.POST.get("q") or "").strip()
    if q:
        candidates = candidates.filter(username__istartswith=q)
    else:
        candidates = candidates[:5]

    outgoing = TeamInvite.objects.filter(
        team=team, status=TeamInvite.Status.PENDING
    ).select_related("invited_user").order_by("created_at")

    return render(
        request,
        "teams/_invite_response_bundle.html",
        {"team": team, "candidates": candidates, "outgoing": outgoing},
    )


@login_required
def outgoing_invites(request, slug):
    team = get_object_or_404(Team, slug=slug)
    if team.captain_id != request.user.id:
        return HttpResponseForbidden()
    outgoing = TeamInvite.objects.filter(
        team=team, status=TeamInvite.Status.PENDING
    ).select_related("invited_user").order_by("created_at")
    return render(request, "teams/_invites_outgoing.html", {"team": team, "outgoing": outgoing})


@login_required
def cancel_invite(request, slug, invite_id):
    if request.method != "POST":
        return HttpResponse(status=405)
    team = get_object_or_404(Team, slug=slug)
    if team.captain_id != request.user.id:
        return HttpResponseForbidden()

    invite = get_object_or_404(TeamInvite, id=invite_id, team=team, status=TeamInvite.Status.PENDING)
    invite.cancel()

    outgoing = TeamInvite.objects.filter(
        team=team, status=TeamInvite.Status.PENDING
    ).select_related("invited_user").order_by("created_at")

    return render(request, "teams/_invites_outgoing.html", {"team": team, "outgoing": outgoing})


# =============================
# ПАНЕЛЬ УВЕДОМЛЕНИЙ (ИНВАЙТЫ)
# =============================


@login_required
def invites_count(request):
    count = TeamInvite.objects.filter(
        invited_user=request.user,
        status=TeamInvite.Status.PENDING
    ).count()
    # ⬇️ без OOB на первичной подгрузке
    return render(request, "teams/_notif_count.html", {
        "pending_count": count,
        "oob": False,
    })

@login_required
def invites_panel(request):
    pending = (TeamInvite.objects
               .filter(invited_user=request.user, status=TeamInvite.Status.PENDING)
               .select_related("team", "invited_by")
               .order_by("-created_at"))
    # внутри панели мы ещё и OOB-обновляем бейдж
    return render(request, "teams/_notif_panel.html", {"pending": pending})

# =============================
# ПРИНЯТИЕ / ОТКЛОНЕНИЕ ИНВАЙТА
# =============================

@login_required
def accept_invite(request, code):
    invite = get_object_or_404(TeamInvite, code=code)
    if invite.invited_user_id != request.user.id:
        return HttpResponseForbidden("This invite is not for you.")
    if invite.status != TeamInvite.Status.PENDING:
        if _is_htmx(request):
            return invites_panel(request)
        messages.info(request, "Приглашение уже обработано.")
        return redirect("teams:my_teams")

    invite.accept()

    if _is_htmx(request):
        resp = invites_panel(request)
        resp.render()
        oob = render_to_string(
            "teams/_notif_count.html",
            {"count": TeamInvite.objects.filter(invited_user=request.user, status=TeamInvite.Status.PENDING).count()},
        )
        resp.content = resp.content + oob.encode("utf-8")
        return resp

    messages.success(request, f"Вы вступили в [{invite.team.tag}] {invite.team.name}.")
    return redirect("teams:team_detail", slug=invite.team.slug)


@login_required
def decline_invite(request, code):
    invite = get_object_or_404(TeamInvite, code=code)
    if invite.invited_user_id != request.user.id:
        return HttpResponseForbidden("This invite is not for you.")
    if invite.status == TeamInvite.Status.PENDING:
        invite.decline()

    if _is_htmx(request):
        resp = invites_panel(request)
        resp.render()
        oob = render_to_string(
            "teams/_notif_count.html",
            {"count": TeamInvite.objects.filter(invited_user=request.user, status=TeamInvite.Status.PENDING).count()},
        )
        resp.content = resp.content + oob.encode("utf-8")
        return resp

    messages.info(request, "Приглашение отклонено.")
    return redirect("teams:my_teams")
