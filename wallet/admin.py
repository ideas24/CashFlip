from django.contrib import admin
from wallet.models import Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['player', 'balance', 'locked_balance', 'currency', 'updated_at']
    search_fields = ['player__phone', 'player__display_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['reference', 'wallet', 'amount', 'tx_type', 'status', 'created_at']
    list_filter = ['tx_type', 'status']
    search_fields = ['reference', 'wallet__player__phone']
    readonly_fields = ['id', 'created_at']
