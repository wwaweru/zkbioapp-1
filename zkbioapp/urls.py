# zkbioapp/urls.py
from django.urls import path
from . import views

app_name = 'zkbioapp'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('sync/employees/', views.sync_employees, name='sync_employees'),
    path('sync/attendance/', views.sync_attendance, name='sync_attendance'),
    path('sync/erp/', views.sync_erp, name='sync_erp'),
    path('sync/full/', views.full_sync, name='full_sync'),
    path('api/stats/', views.api_stats, name='api_stats'),
]