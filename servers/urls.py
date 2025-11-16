from django.urls import path
from . import views

app_name = "servers"

urlpatterns = [
    path("", views.servers_home, name="home"),
    path("<slug:mode>/", views.mode_page, name="mode"), 
]
