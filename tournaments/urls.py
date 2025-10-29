from django.urls import path
from . import views
from .api_views import TournamentListAPIView, TournamentDetailAPIView, ReportMatchAPIView


app_name = "tournaments"

urlpatterns = [
    path("", views.tournament_list, name="list"),
    path("create/", views.tournament_create, name="create"),

    # 👇 вкладки
    path("<int:pk>/overview/", views.tournament_overview, name="overview"),
    path("<int:pk>/bracket/", views.tournament_bracket, name="bracket"),
    path("<int:pk>/matches/", views.tournament_matches, name="matches"),
    path("<int:pk>/teams/", views.tournament_teams, name="teams"),
    path("<int:pk>/results/", views.tournament_results, name="results"),

    # 👇 сервисные маршруты
    path("<int:pk>/generate_bracket/", views.generate_tournament_bracket, name="generate_bracket"),
    path("<int:pk>/toggle_registration/", views.toggle_registration, name="toggle_registration"),
    path("<int:pk>/start/", views.start_tournament, name="start"),
    # 👇 редирект на overview вместо старого detail
    path("<int:pk>/matches/<int:match_id>/report/", views.report_match_result, name="report_match"),
    path("<int:pk>/register/<int:team_id>/", views.register_team, name="register_team"),
    path("<int:pk>/matches/<int:match_id>/", views.match_detail, name="match_detail"),
    path("<int:pk>/matches/<int:match_id>/veto/", views.match_veto, name="match_veto"),
    path('api/tournaments/', TournamentListAPIView.as_view(), name='api_tournament_list'),
    path('api/tournaments/<int:pk>/', TournamentDetailAPIView.as_view(), name='api_tournament_detail'),
    path('api/tournaments/<int:pk>/report/', ReportMatchAPIView.as_view(), name='api_report_match'),
    path("<int:pk>/settings/", views.tournament_settings, name="settings"),

]

