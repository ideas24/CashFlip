from django.urls import path
from dashboard import views

app_name = 'dashboard'

urlpatterns = [
    # Auth
    path('auth/login/', views.admin_login, name='admin_login'),
    path('me/', views.admin_me, name='admin_me'),

    # Dashboard
    path('dashboard/', views.dashboard_stats, name='dashboard_stats'),

    # Players
    path('players/', views.player_list, name='player_list'),
    path('players/<uuid:player_id>/', views.player_update, name='player_update'),

    # Sessions
    path('sessions/', views.session_list, name='session_list'),

    # Transactions
    path('transactions/', views.transaction_list, name='transaction_list'),

    # Finance
    path('finance/', views.finance_overview, name='finance_overview'),
    path('finance/withdrawals/<uuid:wdr_id>/approve/', views.approve_withdrawal, name='approve_withdrawal'),
    path('finance/withdrawals/<uuid:wdr_id>/reject/', views.reject_withdrawal, name='reject_withdrawal'),

    # Partners
    path('partners/', views.partner_list, name='partner_list'),

    # Analytics
    path('analytics/', views.analytics_overview, name='analytics_overview'),

    # Roles
    path('roles/', views.roles_list, name='roles_list'),
    path('roles/<int:role_id>/', views.role_update, name='role_update'),
    path('roles/staff/<uuid:user_id>/', views.staff_update, name='staff_update'),

    # Settings
    path('settings/', views.settings_view, name='settings_view'),
]
