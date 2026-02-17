from django.contrib import admin
from game.models import Currency, CurrencyDenomination, GameConfig, GameSession, FlipResult


class DenominationInline(admin.TabularInline):
    model = CurrencyDenomination
    extra = 1
    fields = ['value', 'banknote_image', 'display_order', 'weight', 'is_zero', 'is_active']


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'symbol', 'is_default', 'is_active']
    list_filter = ['is_active', 'is_default']
    inlines = [DenominationInline]


@admin.register(CurrencyDenomination)
class CurrencyDenominationAdmin(admin.ModelAdmin):
    list_display = ['currency', 'value', 'display_order', 'weight', 'is_zero', 'is_active']
    list_filter = ['currency', 'is_zero', 'is_active']
    list_editable = ['display_order', 'weight', 'is_active']


@admin.register(GameConfig)
class GameConfigAdmin(admin.ModelAdmin):
    list_display = ['currency', 'house_edge_percent', 'min_deposit', 'min_stake', 'pause_cost_percent', 'is_active']
    fieldsets = (
        ('Currency', {'fields': ('currency', 'is_active')}),
        ('Limits', {'fields': ('min_deposit', 'max_cashout', 'min_stake', 'max_session_duration_minutes')}),
        ('House Edge', {'fields': ('house_edge_percent', 'pause_cost_percent')}),
        ('Zero Probability Curve', {
            'fields': ('zero_base_rate', 'zero_growth_rate', 'min_flips_before_zero'),
            'description': 'P(zero) = base_rate + (1-base_rate) * (1 - e^(-k*(flip-min_flips)))'
        }),
    )


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'player', 'currency', 'stake_amount', 'cashout_balance', 'status', 'flip_count', 'created_at']
    list_filter = ['status', 'currency']
    search_fields = ['player__phone', 'player__display_name']
    readonly_fields = ['id', 'server_seed', 'server_seed_hash', 'client_seed', 'nonce']


@admin.register(FlipResult)
class FlipResultAdmin(admin.ModelAdmin):
    list_display = ['session', 'flip_number', 'value', 'is_zero', 'cumulative_balance', 'timestamp']
    list_filter = ['is_zero']
    readonly_fields = ['result_hash']
