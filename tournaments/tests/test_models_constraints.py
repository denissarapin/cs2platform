# tournaments/tests/test_models_constraints.py
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from tournaments.models import Tournament, Match, MapBan, MAP_POOL

@pytest.mark.django_db
def test_mapban_unique_card_per_match(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)

    code = MAP_POOL[0][0]  # например "de_mirage"

    # первый бан проходит
    MapBan.objects.create(match=m, team=a, map_name=code, order=1, action=MapBan.Action.BAN)

    # второй такой же в том же матче должен упасть по UniqueConstraint
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MapBan.objects.create(match=m, team=b, map_name=code, order=2, action=MapBan.Action.BAN)

@pytest.mark.django_db
def test_match_team_a_not_equal_team_b(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    team = make_team("SameTeam")

    # попытка создать матч с одинаковыми командами → CheckConstraint
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Match.objects.create(tournament=t, team_a=team, team_b=team)
