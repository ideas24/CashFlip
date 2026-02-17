from django.urls import path
from payments import views

app_name = 'payments'

urlpatterns = [
    path('deposit/mobile-money/', views.deposit_mobile_money, name='deposit_momo'),
    path('deposit/card/', views.deposit_card, name='deposit_card'),
    path('withdraw/', views.withdraw, name='withdraw'),
    path('wallet/', views.wallet_balance, name='wallet_balance'),
    path('transactions/', views.transaction_history, name='transactions'),
    path('webhooks/orchard/', views.orchard_webhook, name='orchard_webhook'),
    path('webhooks/paystack/', views.paystack_webhook, name='paystack_webhook'),
]
