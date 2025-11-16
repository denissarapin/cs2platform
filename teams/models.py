import uuid
from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils import timezone

class Team(models.Model):
    name = models.CharField(max_length=50, unique=True)
    tag = models.CharField(max_length=8, unique=True)
    slug = models.SlugField(max_length=64, unique=True, blank=True)
    logo = models.ImageField(upload_to='team_logos/', blank=True, null=True)
    captain = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='captain_teams'
    )
    invite_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = f"{self.tag}-{self.name}"
            self.slug = slugify(base)[:64]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.tag}] {self.name}"

class TeamMembership(models.Model):
    ROLE_CHOICES = (
        ('captain', 'Captain'),
        ('player', 'Player'),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='team_memberships'
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='player')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'team')

    def __str__(self):
        return f"{self.user} -> {self.team} ({self.role})"

class TeamInvite(models.Model):
    class Status(models.TextChoices):
        PENDING   = "pending",   "Pending"
        ACCEPTED  = "accepted",  "Accepted"
        DECLINED  = "declined",  "Declined"
        CANCELLED = "cancelled", "Cancelled"

    code         = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    team         = models.ForeignKey(Team, related_name="invites", on_delete=models.CASCADE)
    invited_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="team_invites", on_delete=models.CASCADE)
    invited_by   = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="sent_team_invites", on_delete=models.PROTECT)
    status       = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at   = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("team", "invited_user")
        indexes = [models.Index(fields=["team", "invited_user", "status"])]

    def __str__(self):
        return f"Invite[{self.team}] -> {self.invited_user} ({self.status})"

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.PENDING

    def accept(self):
        from .models import TeamMembership
        if not TeamMembership.objects.filter(team=self.team, user=self.invited_user).exists():
            TeamMembership.objects.create(team=self.team, user=self.invited_user, role="player")
        self.status = self.Status.ACCEPTED
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

    def decline(self):
        self.status = self.Status.DECLINED
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

    def cancel(self):
        self.status = self.Status.CANCELLED
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])