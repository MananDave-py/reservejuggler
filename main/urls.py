from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'main'

urlpatterns = [
    path('login/', views.login_or_register, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', views.intro, name='intro'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('overview/', views.dashboard, name='overview'),
    path('uploads/<int:upload_id>/delete/', views.delete_csv_upload, name='delete_csv_upload'),
    path('uploads/delete-all/', views.delete_all_csv_uploads, name='delete_all_csv_uploads'),
]
