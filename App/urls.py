from django.urls import path
from . import views

urlpatterns = [
    path('', views.home),
    path('dashboard/', views.dashboard),
    path('profile/', views.profile),
    path('recode/', views.recode),
    path('register/', views.register),
    path('login/', views.login),
    path('settings/', views.settings),

]
