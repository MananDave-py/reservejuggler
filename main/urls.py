from django.urls import path

from . import views

app_name = 'main'

urlpatterns = [
    path('', views.intro, name='intro'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('overview/', views.dashboard, name='overview'),
]
