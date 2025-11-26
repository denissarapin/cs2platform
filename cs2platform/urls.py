from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.conf import settings

def home(request):
    return render(request, "home.html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("teams/", include("teams.urls", namespace="teams")),
    path("servers/", include("servers.urls", namespace="servers")),
    path("tournaments/", include("tournaments.urls", namespace="tournaments")),
    path("accounts/", include("accounts.urls")),
]
