from django.urls import path, include
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
    path('steam/connect/', views.connect_steam, name='connect_steam'),
    path('steam/verify/', views.steam_verify, name='steam_verify'),
    path('steam/disconnect/', views.steam_disconnect, name='steam_disconnect'),

]
