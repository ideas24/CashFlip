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
    path('players/<uuid:player_id>/wallet/adjust/', views.player_wallet_adjust, name='player_wallet_adjust'),

    # Sessions
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/<uuid:session_id>/', views.session_detail, name='session_detail'),

    # Transactions
    path('transactions/', views.transaction_list, name='transaction_list'),

    # Finance
    path('finance/', views.finance_overview, name='finance_overview'),
    path('finance/withdrawals/<uuid:wdr_id>/approve/', views.approve_withdrawal, name='approve_withdrawal'),
    path('finance/withdrawals/<uuid:wdr_id>/reject/', views.reject_withdrawal, name='reject_withdrawal'),

    # Partners
    path('partners/', views.partner_list, name='partner_list'),
    path('partners/<uuid:partner_id>/', views.partner_detail, name='partner_detail'),
    path('partners/<uuid:partner_id>/keys/', views.partner_api_keys, name='partner_api_keys'),
    path('partners/<uuid:partner_id>/keys/<uuid:key_id>/', views.partner_api_key_detail, name='partner_api_key_detail'),

    # Analytics
    path('analytics/', views.analytics_overview, name='analytics_overview'),

    # Roles & Staff
    path('roles/', views.roles_list, name='roles_list'),
    path('roles/create/', views.create_role, name='create_role'),
    path('roles/<int:role_id>/', views.role_update, name='role_update'),
    path('roles/staff/create/', views.create_staff, name='create_staff'),
    path('roles/staff/<uuid:user_id>/', views.staff_update, name='staff_update'),
    path('roles/staff/<uuid:user_id>/delete/', views.delete_staff, name='delete_staff'),

    # Search & Notifications
    path('search/', views.global_search, name='global_search'),
    path('notifications/', views.notifications_list, name='notifications_list'),

    # Settings
    path('settings/', views.settings_view, name='settings_view'),
    path('settings/simulated/', views.simulated_config_manage, name='simulated_config_create'),
    path('settings/simulated/<int:config_id>/', views.simulated_config_manage, name='simulated_config_manage'),
]
