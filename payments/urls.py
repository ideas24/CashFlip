from django.urls import path
from payments import views

app_name = 'payments'

urlpatterns = [
    # Mobile money verification
    path('verify-momo/', views.verify_momo, name='verify_momo'),

    # Payment method management
    path('momo-accounts/', views.list_momo_accounts, name='list_momo'),
    path('momo-accounts/add/', views.add_momo_account, name='add_momo'),
    path('momo-accounts/set-primary/', views.set_primary_momo, name='set_primary_momo'),
    path('momo-accounts/remove/', views.remove_momo_account, name='remove_momo'),

    # Deposits
    path('deposit/mobile-money/', views.deposit_mobile_money, name='deposit_momo'),
    path('deposit/card/', views.deposit_card, name='deposit_card'),

    # Withdrawals
    path('withdraw/', views.withdraw, name='withdraw'),

    # Wallet
    path('wallet/', views.wallet_balance, name='wallet_balance'),
    path('wallet/summary/', views.wallet_summary, name='wallet_summary'),
    path('wallet/transfer/', views.transfer_to_player, name='transfer'),
    path('transactions/', views.transaction_history, name='transactions'),

    # Payment status checks (via Orchard verification proxy)
    path('status/deposit/<str:reference>/', views.deposit_status, name='deposit_status'),
    path('status/withdrawal/<str:reference>/', views.withdrawal_status, name='withdrawal_status'),

    # Webhooks
    path('webhooks/orchard/', views.orchard_webhook, name='orchard_webhook'),
    path('webhooks/paystack/', views.paystack_webhook, name='paystack_webhook'),

    # Paystack callback endpoints (proxy router redirects here)
    path('paystack-success/', views.paystack_success, name='paystack_success'),
    path('paystack-cancel/', views.paystack_cancel, name='paystack_cancel'),
]
