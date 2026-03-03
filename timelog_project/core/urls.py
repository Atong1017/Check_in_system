from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # General
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Staff & all roles
    path('clock/', views.clock_view, name='clock'),
    path('journal/', views.journal_view, name='journal'),
    path('correction/', views.correction_create, name='correction_create'),
    path('profile/', views.profile_view, name='profile'),

    # Agent
    path('agent/', views.agent_daily, name='agent_daily'),
    path('agent/monthly/', views.agent_monthly, name='agent_monthly'),
    path('agent/clock/', views.agent_clock_employee, name='agent_clock_employee'),
    path('agent/assign/', views.agent_assign_table, name='agent_assign_table'),
    path('agent/end/<int:session_id>/', views.agent_end_session, name='agent_end_session'),
    path('agent/employee/add/', views.agent_add_employee, name='agent_add_employee'),
    path('agent/correction/<int:attendance_id>/review/', views.agent_approve_correction, name='agent_approve_correction'),
    path('agent/corrections/', views.agent_corrections, name='agent_corrections'),
    path('agent/corrections/<int:attendance_id>/', views.agent_correction_detail, name='agent_correction_detail'),

    # Mami
    path('mami/employee/<int:user_id>/', views.mami_employee_detail, name='mami_employee_detail'),
    path('mami/salary/', views.mami_salary, name='mami_salary'),
    path('mami/salary/delete/<int:salary_id>/', views.mami_salary_delete, name='mami_salary_delete'),
]
