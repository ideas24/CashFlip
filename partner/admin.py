from django.contrib import admin
from django.utils.html import format_html

from partner.models import (
    Operator, OperatorBranding, OperatorAPIKey, OperatorGameConfig,
    OperatorPlayer, OperatorSession, OperatorTransaction,
    OperatorWebhookConfig, OperatorWebhookLog, OperatorSettlement,
)


class OperatorBrandingInline(admin.StackedInline):
    model = OperatorBranding
    extra = 0
    max_num = 1
    fields = ['display_name', 'logo', 'loading_animation', 'primary_color', 'accent_color']


class OperatorAPIKeyInline(admin.TabularInline):
    model = OperatorAPIKey
    extra = 0
    fields = ['label', 'api_key', 'is_active', 'rate_limit_per_minute', 'last_used_at', 'created_at']
    readonly_fields = ['api_key', 'last_used_at', 'created_at']


class OperatorGameConfigInline(admin.StackedInline):
    model = OperatorGameConfig
    extra = 0
    max_num = 1
    fieldsets = (
        ('Currency & Limits', {
            'fields': ('currency', 'min_stake', 'max_stake', 'max_cashout', 'house_edge_percent'),
        }),
        ('Zero Probability Curve', {
            'fields': ('zero_base_rate', 'zero_growth_rate', 'min_flips_before_zero'),
            'classes': ('collapse',),
        }),
        ('Session', {
            'fields': ('pause_cost_percent', 'max_session_duration_minutes', 'is_active'),
        }),
    )


class OperatorWebhookConfigInline(admin.StackedInline):
    model = OperatorWebhookConfig
    extra = 0
    max_num = 1
    fields = ['webhook_url', 'subscribed_events', 'is_active']


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'status', 'commission_percent', 'settlement_frequency',
                    'wallet_status', 'created_at']
    list_filter = ['status', 'settlement_frequency']
    search_fields = ['name', 'slug', 'contact_email']
    readonly_fields = ['created_at', 'updated_at']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [OperatorBrandingInline, OperatorAPIKeyInline, OperatorGameConfigInline,
               OperatorWebhookConfigInline]

    fieldsets = (
        ('Operator Info', {
            'fields': ('name', 'slug', 'website', 'contact_email', 'contact_phone', 'status'),
        }),
        ('Seamless Wallet URLs', {
            'fields': ('debit_url', 'credit_url', 'rollback_url', 'wallet_auth_token'),
            'description': 'Update these when the partner provides their wallet endpoints.',
        }),
        ('Commission & Settlement', {
            'fields': ('commission_percent', 'settlement_frequency', 'min_settlement_amount'),
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Wallet')
    def wallet_status(self, obj):
        if obj.is_live:
            return format_html('<span style="color: #00E676;">&#9679; Live</span>')
        if obj.debit_url:
            return format_html('<span style="color: #F5C842;">&#9679; Partial</span>')
        return format_html('<span style="color: #FF6B6B;">&#9679; Not configured</span>')

    actions = ['generate_api_key']

    @admin.action(description='Generate new API key for selected operators')
    def generate_api_key(self, request, queryset):
        for operator in queryset:
            api_key, api_secret = OperatorAPIKey.generate_key_pair()
            OperatorAPIKey.objects.create(
                operator=operator,
                label=f'Key {operator.api_keys.count() + 1}',
                api_key=api_key,
                api_secret=api_secret,
            )
            self.message_user(
                request,
                f'API Key for {operator.name}: {api_key} | Secret: {api_secret} '
                f'(SAVE THIS — secret is not shown again)'
            )


@admin.register(OperatorAPIKey)
class OperatorAPIKeyAdmin(admin.ModelAdmin):
    list_display = ['operator', 'label', 'api_key_short', 'is_active', 'rate_limit_per_minute',
                    'last_used_at', 'created_at']
    list_filter = ['is_active', 'operator']
    readonly_fields = ['api_key', 'api_secret', 'created_at', 'revoked_at', 'last_used_at']

    @admin.display(description='API Key')
    def api_key_short(self, obj):
        return f'{obj.api_key[:20]}...'


@admin.register(OperatorPlayer)
class OperatorPlayerAdmin(admin.ModelAdmin):
    list_display = ['operator', 'ext_player_id', 'display_name', 'is_active', 'created_at', 'last_seen_at']
    list_filter = ['operator', 'is_active']
    search_fields = ['ext_player_id', 'display_name']


@admin.register(OperatorSession)
class OperatorSessionAdmin(admin.ModelAdmin):
    list_display = ['operator', 'operator_player', 'game_session_status', 'ext_session_ref', 'created_at']
    list_filter = ['operator']
    readonly_fields = ['created_at']

    @admin.display(description='Game Status')
    def game_session_status(self, obj):
        return obj.game_session.status


@admin.register(OperatorTransaction)
class OperatorTransactionAdmin(admin.ModelAdmin):
    list_display = ['operator', 'tx_type', 'amount', 'currency_code', 'status', 'tx_ref', 'created_at']
    list_filter = ['operator', 'tx_type', 'status']
    search_fields = ['tx_ref']
    readonly_fields = ['created_at', 'completed_at', 'request_payload', 'response_payload']


@admin.register(OperatorWebhookLog)
class OperatorWebhookLogAdmin(admin.ModelAdmin):
    list_display = ['operator', 'event', 'status', 'response_status_code', 'retries', 'created_at']
    list_filter = ['operator', 'event', 'status']
    readonly_fields = ['created_at', 'delivered_at', 'payload', 'signature', 'response_body']

    actions = ['retry_delivery']

    @admin.action(description='Retry delivery for selected webhooks')
    def retry_delivery(self, request, queryset):
        from partner.tasks import task_deliver_webhook
        count = 0
        for log in queryset.filter(status='failed'):
            log.status = 'pending'
            log.save(update_fields=['status'])
            task_deliver_webhook.delay(str(log.id))
            count += 1
        self.message_user(request, f'Retrying {count} webhook(s)')


@admin.register(OperatorSettlement)
class OperatorSettlementAdmin(admin.ModelAdmin):
    list_display = ['operator', 'period_start', 'period_end', 'total_bets', 'total_wins',
                    'ggr', 'commission_amount', 'net_operator_amount', 'status']
    list_filter = ['operator', 'status']
    readonly_fields = ['created_at', 'approved_at', 'paid_at']

    actions = ['approve_settlements', 'mark_as_paid']

    @admin.action(description='Approve selected settlements')
    def approve_settlements(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(status='pending').update(status='approved', approved_at=timezone.now())
        self.message_user(request, f'Approved {count} settlement(s)')

    @admin.action(description='Mark selected settlements as paid')
    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(status='approved').update(status='paid', paid_at=timezone.now())
        self.message_user(request, f'Marked {count} settlement(s) as paid')
