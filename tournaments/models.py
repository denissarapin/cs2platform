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
    order = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["match", "order"])]
        constraints = [
            models.UniqueConstraint(
                fields=["match", "map_name"], name="unique_map_once_per_match"
            )
        ]

    def __str__(self):
        return f"{self.team} {self.get_action_display()} {self.get_map_name_display()} (#{self.order})"

class Tournament(models.Model):
    STATUS_CHOICES = [
        ("upcoming", "Upcoming"),
        ("running", "Running"),
        ("finished", "Finished"),
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
        ("scheduled", "Scheduled"),
        ("running", "Running"),
        ("finished", "Finished"),
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

    VETO_STATE = (
        ("idle", "Idle"),
        ("running", "Running"),
        ("done", "Done"),
    )
    veto_state = models.CharField(max_length=8, choices=VETO_STATE, default="idle")
    veto_timeout = models.PositiveIntegerField(default=30)
    veto_deadline = models.DateTimeField(null=True, blank=True)
    veto_started_at = models.DateTimeField(null=True, blank=True)
    veto_turn = models.CharField(max_length=1, choices=(("A", "A"), ("B", "B")), default="A")
    final_map_code = models.CharField(max_length=50, choices=MAP_POOL, null=True, blank=True)
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

    @property
    def is_finished(self):
        return self.status == "finished"

    @property
    def connect_string(self):
        return f"connect {self.server_addr}" if self.server_addr else None

    @property
    def current_team(self) -> Team | None:
        if not (self.team_a and self.team_b):
            return None
        count = self.map_bans.count()
        return self.team_a if count % 2 == 0 else self.team_b

    def available_map_codes(self) -> list[str]:
        if self.final_map_code:
            return []
        banned = set(self.map_bans.values_list("map_name", flat=True))
        return [code for code, _ in MAP_POOL if code not in banned]

    def start_veto(self, now: timezone.datetime | None = None):
        if self.veto_state != "idle":
            return
        now = now or timezone.now()
        self.veto_state = "running"
        self.veto_started_at = now
        self.veto_deadline = now + timezone.timedelta(seconds=self.veto_timeout)
        self.veto_turn = "A" 
        self.save(update_fields=["veto_state", "veto_started_at", "veto_deadline", "veto_turn"])

    def _after_action_tick(self, now: timezone.datetime | None = None):
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
            self.veto_turn = "B" if self.veto_turn == "A" else "A"
            self.veto_deadline = now + timezone.timedelta(seconds=self.veto_timeout)
            self.save(update_fields=["veto_turn", "veto_deadline"])

    def ban_map(self, code: str, team: Team, action="ban") -> bool:
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

    def set_result(self, a: int, b: int):
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
