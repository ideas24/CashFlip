from django.contrib import admin
from payments.models import MobileMoneyAccount, Deposit, Withdrawal


@admin.register(MobileMoneyAccount)
class MobileMoneyAccountAdmin(admin.ModelAdmin):
    list_display = ['player', 'mobile_number', 'network', 'verified_name', 'is_primary', 'is_active', 'created_at']
    list_filter = ['network', 'is_primary', 'is_active']
    search_fields = ['player__phone', 'mobile_number', 'verified_name']
    readonly_fields = ['id', 'verified_at', 'created_at']


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ['player', 'amount', 'method', 'status', 'orchard_reference', 'paystack_reference', 'created_at']
    list_filter = ['method', 'status']
    search_fields = ['player__phone', 'orchard_reference', 'paystack_reference']
    readonly_fields = ['id', 'orchard_response', 'paystack_response', 'created_at', 'completed_at']


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['player', 'amount', 'mobile_number', 'network', 'status', 'payout_reference', 'created_at']
    list_filter = ['status', 'network']
    search_fields = ['player__phone', 'payout_reference', 'mobile_number']
    readonly_fields = ['id', 'orchard_response', 'created_at', 'completed_at']
