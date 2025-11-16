from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

try:
    from tournaments.models import Tournament
    HAS_TOURNAMENTS = True
except Exception:
    Tournament = None
    HAS_TOURNAMENTS = False

try:
    from teams.models import Team
    HAS_TEAMS = True
except Exception:
    Team = None
    HAS_TEAMS = False

User = get_user_model()

class ManagedTournamentInline(admin.TabularInline):
    if HAS_TOURNAMENTS:
        model = Tournament.admins.through
    extra = 0
    verbose_name = "Tournament (admin)"
    verbose_name_plural = "Tournaments administered by user"

class CaptainTeamInline(admin.TabularInline):
    if HAS_TEAMS:
        model = Team
        fk_name = "captain"
    extra = 0
    verbose_name = "Team (captain)"
    verbose_name_plural = "Teams where user is captain"

try:
    admin.site.unregister(User)
except NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = []
    if HAS_TOURNAMENTS and hasattr(Tournament, "admins"):
        inlines.append(ManagedTournamentInline)
    if HAS_TEAMS and hasattr(Team, "captain"):
        inlines.append(CaptainTeamInline)

    list_display = BaseUserAdmin.list_display + ("managed_tournaments_count", "captain_of_teams")
    list_filter = ("is_staff", "is_superuser", "groups")
    search_fields = ("username", "email", "first_name", "last_name")
    readonly_fields = getattr(BaseUserAdmin, "readonly_fields", ()) + ("permissions_summary",)

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Permissions summary", {"fields": ("permissions_summary",)}),
    )

    def managed_tournaments_count(self, obj):
        return getattr(obj, "managed_tournaments", []).count() if hasattr(obj, "managed_tournaments") else 0
    managed_tournaments_count.short_description = "Tournaments (admin)"

    def captain_of_teams(self, obj):
        if hasattr(obj, "captain_teams"):
            return ", ".join(t.name for t in obj.captain_teams.all()) or "—"
        return "—"
    captain_of_teams.short_description = "Teams captain"

    def permissions_summary(self, obj):
        if not obj or not getattr(obj, "pk", None):
            return ""
        groups = ", ".join(g.name for g in obj.groups.all()) or "—"
        return f"staff={obj.is_staff}, superuser={obj.is_superuser}, groups=[{groups}]"
