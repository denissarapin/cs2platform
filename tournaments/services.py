import math
import random

from django.db import transaction

from .models import Match, Tournament, MapBan, MAP_POOL


def get_available_maps(match):
    """Вернёт список карт, которые ещё не забанены."""
    banned = set(match.map_bans.values_list("map_name", flat=True))
    return [m for m, _ in MAP_POOL if m not in banned]


def perform_ban(match, team, map_name):
    """Забанить карту от имени команды."""
    available = get_available_maps(match)
    if map_name not in available:
        return False  # нельзя банить уже убранную карту

    order = match.map_bans.count() + 1
    MapBan.objects.create(match=match, team=team, map_name=map_name, order=order)
    return True


def get_final_map(match):
    """Если осталась одна карта, вернуть (код, название)."""
    available = get_available_maps(match)
    if len(available) == 1:
        code = available[0]
        # ищем читаемое имя по коду в MAP_POOL
        label = next((label for c, label in MAP_POOL if c == code), code)
        return (code, label)
    return None

def generate_full_bracket(tournament: Tournament):
    participants = list(tournament.participants.all())
    teams = [p.team for p in participants]

    if len(teams) < 2:
        raise ValueError("Недостаточно команд для генерации сетки")

    random.shuffle(teams)

    n = len(teams)
    rounds = math.ceil(math.log2(n))
    bracket_size = 2 ** rounds

    while len(teams) < bracket_size:
        teams.append(None)

    tournament.matches.all().delete()

    matches_by_round = {}

    # Раунд 1
    matches = []
    for i in range(0, bracket_size, 2):
        team_a = teams[i]
        team_b = teams[i + 1]
        m = Match.objects.create(
            tournament=tournament,
            round=1,
            team_a=team_a,
            team_b=team_b,
            status="scheduled",
        )
        # ⬇️ Если BYE — сразу продвигаем победителя
        if (team_a and not team_b) or (team_b and not team_a):
            m.winner = team_a or team_b
            m.status = "finished"
            m.save(update_fields=["winner", "status"])
        matches.append(m)
    matches_by_round[1] = matches

    # Следующие раунды
    for r in range(2, rounds + 1):
        matches = []
        num_matches = 2 ** (rounds - r)
        for _ in range(num_matches):
            matches.append(Match.objects.create(
                tournament=tournament,
                round=r,
                team_a=None,
                team_b=None,
                status="scheduled",
            ))
        matches_by_round[r] = matches

    return matches_by_round


def set_match_result(match: Match, score_a: int, score_b: int):
    """
    Обновляет результат матча, ставит победителя и завершает матч.
    (Если ничья — матч возвращается в состояние "scheduled").
    """
    match.score_a = score_a
    match.score_b = score_b

    if score_a == score_b:
        match.status = "scheduled"
        match.winner = None
        match.save(update_fields=["score_a", "score_b", "status", "winner"])
        return

    # Если у матча есть обе команды
    if match.team_a and match.team_b:
        match.winner = match.team_a if score_a > score_b else match.team_b
    else:
        # Если какая-то команда не указана — не ставим winner
        match.winner = None

    match.status = "finished"
    match.save(update_fields=["score_a", "score_b", "status", "winner"])


def update_bracket_progression(tournament: Tournament):
    """
    Переносит победителей матчей в следующий раунд по мере их завершения.
    Работает сразу после любого завершённого матча.
    """
    with transaction.atomic():
        matches = (
            tournament.matches
            .select_related("team_a", "team_b", "winner")
            .order_by("round", "id")
        )

        if not matches.exists():
            return

        by_round = {}
        for m in matches:
            by_round.setdefault(m.round, []).append(m)

        max_round = max(by_round.keys())

        for rnd in range(1, max_round):
            current_round_matches = by_round.get(rnd, [])
            next_round_matches = by_round.get(rnd + 1, [])

            for i, m in enumerate(current_round_matches):
                if m.status != "finished" or not m.winner:
                    continue

                # Находим целевой матч следующего раунда
                next_index = i // 2
                if next_index >= len(next_round_matches):
                    continue

                target = next_round_matches[next_index]

                # Чётные матчи — слот A, нечётные — слот B
                updated = False
                if i % 2 == 0:
                    if target.team_a_id != m.winner_id:
                        target.team_a = m.winner
                        updated = True
                else:
                    if target.team_b_id != m.winner_id:
                        target.team_b = m.winner
                        updated = True

                if updated:
                    target.save(update_fields=["team_a", "team_b"])

        # Финал турнира → ставим победителя турнира
        finals = by_round.get(max_round, [])
        if len(finals) == 1:
            fm = finals[0]
            if fm.status == "finished" and fm.winner_id:
                if tournament.winner_id != fm.winner_id or tournament.status != "finished":
                    tournament.winner = fm.winner
                    tournament.status = "finished"
                    tournament.end_date = tournament.end_date or fm.scheduled_at
                    tournament.save(update_fields=["winner", "status", "end_date"])
