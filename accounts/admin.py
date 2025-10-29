# accounts/admin.py
from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# опционально: туры
try:
    from tournaments.models import Tournament
    HAS_TOURNAMENTS = True
except Exception:
    Tournament = None
    HAS_TOURNAMENTS = False

# опционально: команды
try:
    from teams.models import Team
    HAS_TEAMS = True
except Exception:
    Team = None
    HAS_TEAMS = False

User = get_user_model()


# Инлайн: турниры, где пользователь админ
class ManagedTournamentInline(admin.TabularInline):
    if HAS_TOURNAMENTS:
        model = Tournament.admins.through
    extra = 0
    verbose_name = "Турнир (админ)"
    verbose_name_plural = "Турниры, где пользователь админ"


# Инлайн: команды, где пользователь капитан
class CaptainTeamInline(admin.TabularInline):
    if HAS_TEAMS:
        model = Team
        fk_name = "captain"
    extra = 0
    verbose_name = "Команда (капитан)"
    verbose_name_plural = "Команды, где пользователь капитан"


# Снять регистрацию User, если была
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
    managed_tournaments_count.short_description = "Турниров (админ)"

    def captain_of_teams(self, obj):
        if hasattr(obj, "captain_teams"):
            return ", ".join(t.name for t in obj.captain_teams.all()) or "—"
        return "—"
    captain_of_teams.short_description = "Капитан команд"

    def permissions_summary(self, obj):
        if not obj or not getattr(obj, "pk", None):
            return ""
        groups = ", ".join(g.name for g in obj.groups.all()) or "—"
        return f"staff={obj.is_staff}, superuser={obj.is_superuser}, группы=[{groups}]"
