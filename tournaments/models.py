# tournaments/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone
import random

from teams.models import Team

MAP_POOL = [
    ("de_mirage", "Mirage"),
    ("de_dust2", "Dust2"),
    ("de_ancient", "Ancient"),
    ("de_train", "Train"),
    ("de_nuke", "Nuke"),
    ("de_inferno", "Inferno"),
    ("de_overpass", "Overpass"),
]


# -------- BAN / PICK отдельной записью --------
class MapBan(models.Model):
    class Action(models.TextChoices):
        BAN = "ban", "Ban"
        PICK = "pick", "Pick"

    match = models.ForeignKey(
        "Match", on_delete=models.CASCADE, related_name="map_bans"
    )
    team = models.ForeignKey("teams.Team", on_delete=models.CASCADE)
    action = models.CharField(
        max_length=8, choices=Action.choices, default=Action.BAN
    )
    map_name = models.CharField(max_length=50, choices=MAP_POOL)
    order = models.PositiveIntegerField()  # порядок операции 1,2,3...
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["match", "order"])]
        # запрещаем бан/пик одной и той же карты дважды в рамках матча
        constraints = [
            models.UniqueConstraint(
                fields=["match", "map_name"], name="unique_map_once_per_match"
            )
        ]

    def __str__(self):
        return f"{self.team} {self.get_action_display()} {self.get_map_name_display()} (#{self.order})"


class Tournament(models.Model):
    STATUS_CHOICES = [
        ("upcoming", "Предстоящий"),
        ("running", "В процессе"),
        ("finished", "Завершён"),
    ]

    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="tournaments/logos/", blank=True, null=True)
    poster = models.ImageField(upload_to="tournaments/posters/", blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="upcoming")

    max_teams = models.PositiveIntegerField(default=16)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    registration_open = models.BooleanField(default=True)
    winner = models.ForeignKey(
        Team, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="won_tournaments"
    )
    admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="managed_tournaments"
    )

    class Meta:
        ordering = ("-start_date", "id")

    def __str__(self):
        return self.name

    @property
    def is_open_for_registration(self):
        return (
            self.status == "upcoming"
            and self.registration_open
            and self.participants.count() < self.max_teams
        )

    @property
    def slots_left(self):
        return max(self.max_teams - self.participants.count(), 0)


class TournamentTeam(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="participants")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="tournaments")
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tournament", "team")

    def __str__(self):
        return f"{self.team} → {self.tournament}"


class Match(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Назначен"),
        ("running", "В процессе"),
        ("finished", "Завершён"),
    ]

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="matches")
    round = models.PositiveIntegerField(default=1)
    team_a = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="matches_as_a")
    team_b = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="matches_as_b")

    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="scheduled")

    score_a = models.PositiveIntegerField(default=0)
    score_b = models.PositiveIntegerField(default=0)
    winner = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="won_matches")

    # ---------- Поля вето ----------
    VETO_STATE = (
        ("idle", "Idle"),
        ("running", "Running"),
        ("done", "Done"),
    )
    veto_state = models.CharField(max_length=8, choices=VETO_STATE, default="idle")
    veto_timeout = models.PositiveIntegerField(default=30)  # сек. на ход
    veto_deadline = models.DateTimeField(null=True, blank=True)  # до какого времени текущий ход
    veto_started_at = models.DateTimeField(null=True, blank=True)
    # Чей ход:  "A" — team_a, "B" — team_b
    veto_turn = models.CharField(max_length=1, choices=(("A", "A"), ("B", "B")), default="A")

    # Итоговая карта (сохраняем, чтобы не терялась после F5)
    final_map_code = models.CharField(max_length=50, choices=MAP_POOL, null=True, blank=True)

    # Строка подключения к серверу (например "192.168.1.56:27015")
    server_addr = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["round", "id"]
        indexes = [
            models.Index(fields=["tournament", "round"]),
            models.Index(fields=["tournament", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(team_a=models.F("team_b")),
                name="match_team_a_ne_team_b",
            ),
        ]

    def __str__(self):
        return f"{self.team_a or '—'} vs {self.team_b or '—'} ({self.tournament})"

    # ---------- Удобные свойства ----------
    @property
    def is_finished(self):
        return self.status == "finished"

    @property
    def connect_string(self):
        """Строка для кнопки 'connect ...'."""
        return f"connect {self.server_addr}" if self.server_addr else None

    @property
    def current_team(self) -> Team | None:
        """Кто сейчас банит по очередности (A,B,A,B,...)"""
        if not (self.team_a and self.team_b):
            return None
        # по количеству уже сделанных действий определяем, чей ход
        count = self.map_bans.count()
        return self.team_a if count % 2 == 0 else self.team_b

    # ---------- Работа с картами ----------
    def available_map_codes(self) -> list[str]:
        """Коды карт, которые ещё не забанены/не выбраны, если финальная карта уже определена — пустой список."""
        if self.final_map_code:
            return []
        banned = set(self.map_bans.values_list("map_name", flat=True))
        return [code for code, _ in MAP_POOL if code not in banned]

    def start_veto(self, now: timezone.datetime | None = None):
        """Запускает вето, если не запущено."""
        if self.veto_state != "idle":
            return
        now = now or timezone.now()
        self.veto_state = "running"
        self.veto_started_at = now
        self.veto_deadline = now + timezone.timedelta(seconds=self.veto_timeout)
        self.veto_turn = "A"  # начинает team_a
        self.save(update_fields=["veto_state", "veto_started_at", "veto_deadline", "veto_turn"])

    def _after_action_tick(self, now: timezone.datetime | None = None):
        """Обновить дедлайн и проверить, не осталась ли одна карта."""
        now = now or timezone.now()
        avail = self.available_map_codes()
        if len(avail) == 1:
            self.final_map_code = avail[0]
            self.veto_state = "done"
            self.veto_deadline = None

            if not self.server_addr:
                self.server_addr = "192.168.1.56:27015"

            self.save(update_fields=["final_map_code", "veto_state", "veto_deadline", "server_addr"])
        else:
            # Передаём ход сопернику и продлеваем таймер
            self.veto_turn = "B" if self.veto_turn == "A" else "A"
            self.veto_deadline = now + timezone.timedelta(seconds=self.veto_timeout)
            self.save(update_fields=["veto_turn", "veto_deadline"])

    def ban_map(self, code: str, team: Team, action="ban") -> bool:
        """Пытается забанить/запикать карту. Возвращает True/False."""
        if self.veto_state != "running":
            return False
        if team != self.current_team:
            return False
        if code not in self.available_map_codes():
            return False
        order = self.map_bans.count() + 1
        MapBan.objects.create(match=self, team=team, map_name=code, order=order, action=action)
        self._after_action_tick()
        return True

    def auto_ban_if_expired(self, now: timezone.datetime | None = None) -> bool:
        """Если истёк таймер — баним случайную доступную карту за текущую команду."""
        if self.veto_state != "running" or not self.veto_deadline:
            return False
        now = now or timezone.now()
        if now <= self.veto_deadline:
            return False
        avail = self.available_map_codes()
        if not avail:
            return False
        team = self.current_team
        choice = random.choice(avail)
        order = self.map_bans.count() + 1
        MapBan.objects.create(match=self, team=team, map_name=choice, order=order, action=MapBan.Action.BAN)
        self._after_action_tick(now=now)
        return True

    # ---------- Результат ----------
    def set_result(self, a: int, b: int):
        """Ставим счёт, статус и победителя (без ничьих в single-elim)."""
        self.score_a = max(0, int(a))
        self.score_b = max(0, int(b))
        if self.score_a == self.score_b:
            self.winner = None
            if self.status == "finished":
                self.status = "scheduled"
        else:
            self.winner = self.team_a if self.score_a > self.score_b else self.team_b
            self.status = "finished"
        self.save(update_fields=["score_a", "score_b", "winner", "status"])
