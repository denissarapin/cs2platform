# teams/urls.py
from django.urls import path
from . import views

app_name = 'teams'

urlpatterns = [
    path('', views.my_teams, name='my_teams'),
    path('create/', views.team_create, name='team_create'),
    path('<slug:slug>/', views.team_detail, name='team_detail'),
    path('join/<uuid:code>/', views.join_by_code, name='join_by_code'),
    path('<slug:slug>/leave/', views.leave_team, name='leave_team'),
    path('<slug:slug>/transfer/<int:user_id>/', views.transfer_captain, name='transfer_captain'),
    path('<slug:slug>/remove/<int:user_id>/', views.remove_member, name='remove_member'),

    # HTMX: поиск и инвайты
    path('<slug:slug>/user-search/', views.user_search, name='user_search'),
    path('<slug:slug>/send-invite/', views.send_invite, name='send_invite'),
    path('<slug:slug>/outgoing/', views.outgoing_invites, name='outgoing_invites'),
    path('<slug:slug>/cancel-invite/<int:invite_id>/', views.cancel_invite, name='cancel_invite'),

    # Панель уведомлений + счётчик
    path('invites/panel/', views.invites_panel, name='invites_panel'),
    path('invites/count/', views.invites_count, name='invites_count'),

    # Принять/отклонить
    path('invites/accept/<uuid:code>/', views.accept_invite, name='accept_invite'),
    path('invites/decline/<uuid:code>/', views.decline_invite, name='decline_invite'),
]
