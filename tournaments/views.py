import inspect
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponse
from django.db import transaction
from django.template.loader import render_to_string
from django.templatetags.static import static
from .models import Tournament, TournamentTeam, Match, MapBan, MAP_POOL
from teams.models import Team
from .forms import TournamentForm, TournamentSettingsForm
from .services import generate_full_bracket, set_match_result, update_bracket_progression, get_available_maps, get_final_map, perform_ban
from .permissions import staff_or_tadmin
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datetime import timedelta
from django.views.decorators.http import require_POST
from django.conf import settings
from django.db.models import Max

def staff_required(fn):
    return user_passes_test(lambda u: u.is_staff)(fn)

def _can_manage(user, tournament: Tournament) -> bool:
    return user.is_authenticated and (
        user.is_staff or tournament.admins.filter(id=user.id).exists()
    )

@staff_required
def tournament_create(request):
    if request.method == "POST":
        form = TournamentForm(request.POST, request.FILES)
        if form.is_valid():
            t = form.save(commit=False)
            t.created_by = request.user
            t.save()
            messages.success(request, "Tournament created")
            return redirect("tournaments:overview", pk=t.pk)
    else:
        form = TournamentForm()
    return render(request, "tournaments/tournament_form.html", {
        "form": form,
        "title": "Create tournament",
    })

def tournament_list(request):
    tournaments = Tournament.objects.all().order_by("-start_date")
    return render(request, "tournaments/tournament_list.html", {"tournaments": tournaments})

def tournament_overview(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    participants = t.participants.select_related("team")
    registered_count = participants.count()
    ready_count = registered_count
    registered_pct = int(registered_count / t.max_teams * 100) if t.max_teams else 0
    start = t.start_date
    ready_open = start - timedelta(minutes=45)
    ready_close = start
    registration_close = start
    joined_id = request.GET.get("joined")
    joined_team = Team.objects.filter(pk=joined_id).first() if joined_id else None

    ctx = {
        "tournament": t,
        "participants": participants,
        "active_tab": "overview",
        "can_manage": _can_manage(request.user, t),
        "registered_count": registered_count,
        "ready_count": ready_count,
        "registered_pct": registered_pct,
        "ready_open": ready_open,
        "ready_close": ready_close,
        "registration_close": registration_close,
        "joined_team": joined_team,
        "bracket_url": reverse("tournaments:bracket", args=[t.pk]),
        "revoke_url": "",
    }
    ctx.update(_hero_ctx(request, t))
    return render(request, "tournaments/overview.html", ctx)

@login_required
def tournament_bracket(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    update_bracket_progression(t)
    matches = (
        t.matches
         .select_related("team_a", "team_b", "winner")
         .order_by("round", "id")
    )
    by_round = {}
    for m in matches:
        by_round.setdefault(m.round, []).append(m)
    max_round = matches.aggregate(m=Max("round"))["m"] or 1
    def _round_label(r: int, max_r: int) -> str:
        dist = max_r - r 
        if dist == 0:
            return "Final"
        if dist == 1:
            return "Semi finals"
        if dist == 2:
            return "Quarter finals"
        size = 2 ** (dist + 1) 
        return f"Round of {size}"
    rounds = [
        {"num": r, "label": _round_label(r, max_round), "matches": by_round.get(r, [])}
        for r in sorted(by_round.keys())
    ]
    ctx = {
        "tournament": t,
        "active_tab": "bracket",
        "can_manage": _can_manage(request.user, t),
        "rounds": rounds, 
    }
    ctx.update(_hero_ctx(request, t))
    return render(request, "tournaments/bracket.html", ctx)

def _hero_ctx(request, t):
    cover_url = t.cover.url if getattr(t, "cover", None) else static("img/tournaments/default.jpg")
    logo_url  = t.logo.url  if getattr(t, "logo",  None) else static("img/tournaments/logo.jpg")
    captain_teams = (
        request.user.captain_teams.all()
        if request.user.is_authenticated
        else Team.objects.none()
    )
    registered_count = t.participants.count()
    can_join = (request.user.is_authenticated and t.is_open_for_registration and captain_teams.exists() and (registered_count < t.max_teams))
    user_team_ids = set(captain_teams.values_list("id", flat=True))
    already_registered = t.participants.filter(team_id__in=user_team_ids).exists() if user_team_ids else False
    if already_registered:
        can_join = False
    return {
        "cover_url": cover_url,
        "logo_url": logo_url,
        "captain_teams": captain_teams.order_by("name"),
        "can_join": can_join,
        "already_registered": already_registered,
    }

@staff_or_tadmin
def toggle_registration(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    if t.status != "upcoming":
        messages.error(request, "Registration can only be modified before the tournament starts.")
        return redirect("tournaments:settings", pk=pk)
    t.registration_open = not t.registration_open
    t.save(update_fields=["registration_open"])
    messages.success(request, "Registration " + ("opened" if t.registration_open else "closed"))
    return redirect("tournaments:settings", pk=pk)

@staff_or_tadmin
@require_POST
def start_tournament(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    if t.status == "running":
        return redirect("tournaments:bracket", pk=pk)

    min_teams = getattr(settings, "TOURNAMENT_MIN_TEAMS", 4)
    if t.participants.count() < min_teams:
        messages.error(request, f"You need at least {min_teams} teams to start the tournament.")
        form = TournamentSettingsForm(instance=t)
        for name in ("start_date", "end_date"):
            v = getattr(t, name, None)
            if v:
                form.initial[name] = v.strftime("%Y-%m-%dT%H:%M")
        ctx = {
            "tournament": t,
            "active_tab": "settings",
            "form": form,
            "can_manage": _can_manage(request.user, t),
        }
        ctx.update(_hero_ctx(request, t))
        return render(request, "tournaments/settings.html", ctx, status=200)

    with transaction.atomic():
        generate_full_bracket(t)
        update_bracket_progression(t)
        t.status = "running"
        t.registration_open = False
        t.save(update_fields=["status", "registration_open"])

    messages.success(request, "Tournament started. Bracket generated.")
    return redirect("tournaments:bracket", pk=pk)

@login_required
def tournament_matches(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    matches = (
        t.matches
         .select_related("team_a", "team_b")
         .order_by("round", "id") 
    )
    ctx = {
        "tournament": t,
        "matches": matches,
        "active_tab": "matches",
        "can_manage": _can_manage(request.user, t),
    }
    ctx.update(_hero_ctx(request, t))
    return render(request, "tournaments/matches.html", ctx)

@login_required
def tournament_teams(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    participants = t.participants.select_related("team", "team__captain").order_by("team__name")
    ctx = {
        "tournament": t,
        "participants": participants,
        "active_tab": "teams",
        "can_manage": _can_manage(request.user, t),
    }
    ctx.update(_hero_ctx(request, t))
    return render(request, "tournaments/teams.html", ctx)

@login_required
def tournament_results(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    matches = (
        t.matches
         .filter(status="finished")
         .select_related("team_a", "team_b")
         .order_by("round", "id")
    )
    ctx = {
        "tournament": t,
        "matches": matches,
        "active_tab": "results",
        "can_manage": _can_manage(request.user, t),
    }
    ctx.update(_hero_ctx(request, t))
    return render(request, "tournaments/results.html", ctx)

@login_required
def tournament_settings(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    if not _can_manage(request.user, t):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    if request.method == "POST":
        data = request.POST.copy()
        from .forms import HTML_DT

        def _maybe_set(name, value):
            if name in data:
                return
            if value is None:
                return
            if hasattr(value, "strftime"):
                data[name] = value.strftime(HTML_DT)
            elif isinstance(value, bool):
                if value is True:  
                    data[name] = "on"
            else:
                data[name] = str(value)
        _maybe_set("start_date", getattr(t, "start_date", None))
        _maybe_set("end_date", getattr(t, "end_date", None))
        _maybe_set("status", getattr(t, "status", None))
        _maybe_set("max_teams", getattr(t, "max_teams", None))
        _maybe_set("registration_open", getattr(t, "registration_open", None))

        form = TournamentSettingsForm(data, instance=t)
        if form.is_valid():
            obj = form.save(commit=False)
            bo_name = getattr(form, "_bo_field_name", None)
            if bo_name and bo_name in form.cleaned_data:
                setattr(obj, bo_name, int(form.cleaned_data[bo_name]))
            obj.save()
            messages.success(request, "Tournament settings saved")
            return redirect("tournaments:settings", pk=t.pk)
        else:
            messages.info(request, "Settings not changed")
            return redirect("tournaments:settings", pk=t.pk)

    else:
        form = TournamentSettingsForm(instance=t)
        for name in ("start_date", "end_date"):
            v = getattr(t, name, None)
            if v:
                form.initial[name] = v.strftime("%Y-%m-%dT%H:%M")

    ctx = {
        "tournament": t,
        "active_tab": "settings",
        "form": form,
        "can_manage": _can_manage(request.user, t),
    }
    ctx.update(_hero_ctx(request, t))
    return render(request, "tournaments/settings.html", ctx)

@staff_required
def delete_tournament(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    if request.method == "POST":
        name = t.name
        t.delete()
        messages.success(request, f'Tournament "{name}" has been deleted.')
        return redirect("tournaments:list")
    messages.info(request, "Please confirm deletion by clicking the button.")
    return redirect("tournaments:settings", pk=pk)

@staff_or_tadmin
def generate_tournament_bracket(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    generate_full_bracket(t)
    messages.success(request, "Bracket generated")
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"tournament_matches_{t.id}",
        {
            "type": "matches_update",
            "action": "bracket_generated",
            "message": "Tournament bracket regenerated",
        },
    )
    return redirect("tournaments:bracket", pk=pk)

def send_ws_update(match):
    channel_layer = get_channel_layer()
    payload = {
        "type": "bracket_update",
        "match_id": match.id,
        "html": render_to_string("tournaments/_match.html", {"match": match}),
    }
    group = f"tournament_{match.tournament_id}"

    if inspect.iscoroutinefunction(channel_layer.group_send):
        async_to_sync(channel_layer.group_send)(group, payload)
    else:
        channel_layer.group_send(group, payload)

@staff_or_tadmin
def report_match_result(request, pk, match_id):
    t = get_object_or_404(Tournament, pk=pk)
    m = get_object_or_404(Match, pk=match_id, tournament=t)
    is_htmx = request.headers.get("HX-Request") == "true"

    if request.method == "GET":
        html = render_to_string(
            "tournaments/_report_form.html",
            {"tournament": t, "match": m, "request": request},
        )
        return HttpResponse(html)
    try:
        a = int(request.POST.get("score_a", "0"))
        b = int(request.POST.get("score_b", "0"))
    except ValueError:
        if is_htmx:
            html = render_to_string(
                "tournaments/_report_form.html",
                {
                    "tournament": t,
                    "match": m,
                    "error": "Invalid score format",
                    "request": request,
                }
            )
            return HttpResponse(html, status=400)
        messages.error(request, "Invalid score format")
        return redirect("tournaments:matches", pk=pk)

    set_match_result(m, a, b)
    m.refresh_from_db()
    update_bracket_progression(t)
    updated_matches = t.matches.all().select_related("team_a", "team_b", "winner")
    for mm in updated_matches:
        send_ws_update(mm)
    if is_htmx:
        resp = HttpResponse(status=204)
        resp["HX-Trigger"] = "match-updated"
        return resp

    messages.success(request, "Result saved")
    return redirect("tournaments:matches", pk=pk)

@login_required
def register_team(request, pk, team_id):
    t = get_object_or_404(Tournament, pk=pk)
    team = get_object_or_404(Team, pk=team_id)
    if team.captain != request.user:
        messages.error(request, "Only the captain can register a team")
        return redirect("tournaments:overview", pk=pk)
    if not t.is_open_for_registration:
        messages.error(request, "Registration is closed")
        return redirect("tournaments:overview", pk=pk)
    if t.participants.count() >= t.max_teams:
        messages.error(request, "No more slots available")
        return redirect("tournaments:overview", pk=pk)
    TournamentTeam.objects.get_or_create(tournament=t, team=team)
    url = reverse("tournaments:overview", args=[pk])
    return redirect(f"{url}?joined={team.id}")

@login_required
def match_detail(request, pk, match_id):
    from .models import Tournament, Match, MAP_POOL
    tournament = get_object_or_404(Tournament, pk=pk)
    match = get_object_or_404(Match, pk=match_id, tournament=tournament)

    if match.veto_state == "idle" and match.team_a_id and match.team_b_id:
        match.start_veto()
    match.auto_ban_if_expired()

    if request.method == "POST":
        code = (
            request.POST.get("map_name")
            or request.POST.get("map")
            or request.POST.get("code")
            or request.POST.get("map_code")
            or request.GET.get("map")
            or request.GET.get("code")
        )

        if code:
            match.auto_ban_if_expired()
            team = match.current_team
            if team and code in match.available_map_codes():
                match.ban_map(code, team, action="ban")

        final_map = None
        if match.final_map_code:
            final_map = (
                match.final_map_code,
                dict(MAP_POOL).get(match.final_map_code, match.final_map_code),
            )
        deadline_ts = int(match.veto_deadline.timestamp() * 1000) if match.veto_deadline else None

        html = render_to_string(
            "tournaments/match_detail_inner.html",
            {
                "tournament": tournament,
                "match": match,
                "bans": match.map_bans.select_related("team").order_by("order"),
                "map_pool": MAP_POOL,
                "available_codes": match.available_map_codes(),
                "final_map": final_map,
                "current_team": match.current_team if not final_map else None,
                "deadline_ts": deadline_ts,
                "server_addr": match.server_addr or "192.168.1.56:27015",
                "connect_cmd": f"connect {match.server_addr or '192.168.1.56:27015'}",
                "request": request,
            },
        )
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"match_{match.id}",
            {"type": "match_update", "html": html},
        )
        return redirect("tournaments:match_detail", pk=pk, match_id=match_id)

    final_map = None
    if match.final_map_code:
        final_map = (
            match.final_map_code,
            dict(MAP_POOL).get(match.final_map_code, match.final_map_code),
        )
    deadline_ts = int(match.veto_deadline.timestamp() * 1000) if match.veto_deadline else None

    return render(
        request,
        "tournaments/match_detail.html",
        {
            "tournament": tournament,
            "match": match,
            "active_tab": "matches",
            "bans": match.map_bans.select_related("team").order_by("order"),
            "map_pool": MAP_POOL,
            "available_codes": match.available_map_codes(),
            "final_map": final_map,
            "current_team": match.current_team if not final_map else None,
            "deadline_ts": deadline_ts,
            "server_addr": match.server_addr or "192.168.1.56:27015",
            "connect_cmd": f"connect {match.server_addr or '192.168.1.56:27015'}",
            "can_manage": _can_manage(request.user, tournament),
        },
    )

def get_available_maps(match: Match):
    banned = set(match.map_bans.values_list("map_name", flat=True))
    return [(code, label) for code, label in MAP_POOL if code not in banned]

def get_final_map(match: Match):
    available = get_available_maps(match) 
    if len(available) == 1:
        return available[0]
    return None

def perform_ban(match: Match, team: Team, map_name: str) -> bool:
    available_codes = [code for code, _ in get_available_maps(match)]
    if map_name not in available_codes:
        return False
    MapBan.objects.create(
        match=match,
        team=team,
        map_name=map_name,
        order=match.map_bans.count() + 1,
    )
    return True

@login_required
def match_veto(request, pk, match_id):
    tournament = get_object_or_404(Tournament, pk=pk)
    match = get_object_or_404(Match, pk=match_id, tournament=tournament)
    available = get_available_maps(match)
    available_codes = [x[0] if isinstance(x, (list, tuple)) else x for x in available]
    final_map = get_final_map(match)
    ban_order = match.map_bans.count()
    current_team = None
    if not final_map and match.team_a and match.team_b:
        current_team = match.team_a if ban_order % 2 == 0 else match.team_b

    if request.method == "POST" and not final_map:
        map_choice = request.POST.get("map_name")
        if not map_choice:
            messages.error(request, "Select a map")
            return redirect("tournaments:match_veto", pk=pk, match_id=match.id)

        if current_team and request.user == current_team.captain:
            if perform_ban(match, current_team, map_choice):
                messages.success(request, f"Map {map_choice} banned")
            else:
                messages.error(request, "This map is already unavailable")
        else:
            messages.error(request, "It’s not your turn to ban a map")

        return redirect("tournaments:match_veto", pk=pk, match_id=match.id)

    html = render_to_string(
        "tournaments/_veto_panel.html",
        {
            "tournament": tournament,
            "match": match,
            "available_maps": available,
            "available_codes": available_codes,
            "bans": match.map_bans.select_related("team"),
            "final_map": final_map,
            "map_pool": MAP_POOL,
            "current_team": current_team,
            "can_manage": _can_manage(request.user, tournament),
            "request": request,
        },
    )
    return HttpResponse(html)

