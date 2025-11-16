from django.contrib import admin
from .models import Tournament, TournamentTeam, Match

class TournamentTeamInline(admin.TabularInline):
    model = TournamentTeam
    extra = 0
    autocomplete_fields = ("team",)


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = (
        "name", "start_date", "status", "registration_open",
        "admins_count", "participants_count", "winner"
    )
    list_filter = ("status", "registration_open", "admins")
    search_fields = ("name",)
    filter_horizontal = ("admins",)
    inlines = [TournamentTeamInline]

    def admins_count(self, obj):
        return obj.admins.count()
    admins_count.short_description = "Admins"

    def participants_count(self, obj):
        return obj.participants.count()
    participants_count.short_description = "Teams"
