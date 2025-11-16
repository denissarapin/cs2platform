from django.contrib import admin
from .models import Team, TeamMembership

class MembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'tag', 'captain', 'created_at')
    search_fields = ('name', 'tag')
    inlines = [MembershipInline]

@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'team', 'role', 'joined_at')
    search_fields = ('user__username', 'team__name', 'team__tag')
