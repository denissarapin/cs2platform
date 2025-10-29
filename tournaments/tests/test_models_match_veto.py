import pytest
from django.utils import timezone
from tournaments.models import Tournament, Match, MAP_POOL, MapBan

@pytest.mark.django_db
def test_start_veto_sets_state_deadline_and_turn_A(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=60)
    fixed_now = timezone.now()

    m.start_veto(now=fixed_now)
    m.refresh_from_db()

    assert m.veto_state == "running"
    assert m.veto_started_at == fixed_now
    assert m.veto_deadline == fixed_now + timezone.timedelta(seconds=60)
    assert m.veto_turn == "A"
    # по умолчанию финальной карты нет
    assert m.final_map_code is None

@pytest.mark.django_db
def test_ban_map_respects_turn_and_sets_final_when_one_left(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=30)

    # Оставим только 2 карты в пуле
    all_codes = [c for c, _ in MAP_POOL]
    keep = all_codes[:2]
    preban = all_codes[2:]  # всё остальное забаним заранее

    # Проставим пред-баны (до старта вето это обычные записи в таблице)
    for i, code in enumerate(preban, start=1):
        MapBan.objects.create(match=m, team=a, map_name=code, order=i, action=MapBan.Action.BAN)

    # Стартуем вето — ход определяется чётностью количества уже сделанных действий
    m.start_veto(now=timezone.now())
    m.refresh_from_db()

    # у кого ход сейчас?
    expected_team = a if (m.map_bans.count() % 2 == 0) else b
    assert set(m.available_map_codes()) == set(keep)

    # Баним одну из двух оставшихся карт тем, у кого сейчас ход
    ok = m.ban_map(keep[0], expected_team, action="ban")
    assert ok is True

    m.refresh_from_db()
    # Осталась одна — модель должна зафиксировать финальную карту и завершить вето
    assert m.veto_state == "done"
    assert m.final_map_code == keep[1]
    assert m.available_map_codes() == []
@pytest.mark.django_db
def test_auto_ban_if_expired_bans_and_switches_turn(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=5)

    start = timezone.now()
    m.start_veto(now=start)
    assert m.veto_turn == "A"

    # продвинем время за дедлайн
    later = start + timezone.timedelta(seconds=6)
    changed = m.auto_ban_if_expired(now=later)
    assert changed is True

    m.refresh_from_db()
    # либо финальная карта уже выбралась (если пул стал 1),
    # либо ход переключился на B и дедлайн обновился
    if m.veto_state == "done":
        assert m.final_map_code is not None
    else:
        assert m.veto_turn == "B"
        assert m.veto_deadline and m.veto_deadline > later

@pytest.mark.django_db
def test_connect_string_property(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, server_addr="10.0.0.1:27015")
    assert m.connect_string == "connect 10.0.0.1:27015"
