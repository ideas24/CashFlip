from django.contrib import admin
from game.models import SiteBranding, Currency, CurrencyDenomination, GameConfig, SimulatedGameConfig, GameSession, FlipResult


@admin.register(SiteBranding)
class SiteBrandingAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'primary_color', 'secondary_color', 'tagline', 'updated_at']
    fieldsets = (
        ('Logos', {
            'fields': ('logo', 'logo_icon', 'loading_animation'),
            'description': 'Upload custom logos. Leave blank to use default SVG assets.',
        }),
        ('Brand Colors', {
            'fields': ('primary_color', 'secondary_color', 'accent_color', 'background_color'),
        }),
        ('Content', {
            'fields': ('tagline',),
        }),
    )

    def has_add_permission(self, request):
        return not SiteBranding.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class DenominationInline(admin.TabularInline):
    model = CurrencyDenomination
    extra = 1
    fields = ['value', 'face_image_upload', 'flip_gif_upload', 'display_order', 'weight', 'is_zero', 'is_active']


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
    fieldsets = (
        (None, {'fields': ('currency', 'value', 'display_order', 'weight', 'is_zero', 'is_active')}),
        ('Uploaded Images (priority)', {
            'fields': ('face_image_upload', 'flip_gif_upload', 'front_image', 'back_image'),
            'description': 'Upload face image and flip GIF. These take priority over static paths below. '
                         'Recommended: 1920×1080 (16:9). On Azure Storage for CDN delivery in production.',
        }),
        ('Static Asset Paths (fallback)', {
            'fields': ('face_image_path', 'flip_gif_path', 'flip_sequence_prefix', 'flip_sequence_frames'),
            'classes': ('collapse',),
            'description': 'Static file paths used as fallback when no uploaded files exist.',
        }),
    )


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


@admin.register(SimulatedGameConfig)
class SimulatedGameConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_enabled', 'outcome_mode', 'apply_to_all_players', 'sessions_used', 'auto_disable_after', 'updated_at']
    list_filter = ['is_enabled', 'outcome_mode', 'apply_to_all_players']
    list_editable = ['is_enabled']
    filter_horizontal = ['targeted_players']
    readonly_fields = ['sessions_used', 'created_at', 'updated_at']

    fieldsets = (
        ('Master Switch', {
            'fields': ('name', 'is_enabled'),
            'description': 'Toggle simulation on/off. Only one config should be enabled at a time.',
        }),
        ('Outcome Control', {
            'fields': ('outcome_mode', 'force_zero_at_flip', 'fixed_zero_probability', 'win_streak_length'),
            'description': (
                'always_win: Every flip wins. '
                'always_lose: Every flip is zero. '
                'force_zero_at: Wins until specific flip#, then zero. '
                'fixed_probability: Override the sigmoid curve with a flat %. '
                'streak_then_lose: Win N flips, then forced zero.'
            ),
        }),
        ('Denomination Override', {
            'fields': ('force_denomination_value',),
            'description': 'Force a specific coin value on every winning flip (leave blank for normal random).',
        }),
        ('Player Targeting', {
            'fields': ('apply_to_all_players', 'targeted_players'),
            'description': 'Apply to everyone or only selected test players.',
        }),
        ('Limit Overrides', {
            'fields': ('override_min_stake', 'override_max_cashout'),
            'description': 'Override game limits for testing (blank = use normal GameConfig values).',
        }),
        ('Test Wallet', {
            'fields': ('grant_test_balance',),
            'description': 'Auto-grant this balance to players on session start if their balance is lower.',
        }),
        ('Safety & Tracking', {
            'fields': ('auto_disable_after', 'sessions_used', 'created_at', 'updated_at'),
            'description': 'Auto-disable after N sessions to prevent leaving simulation on accidentally.',
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        # If enabling this config, disable all others
        if obj.is_enabled:
            SimulatedGameConfig.objects.filter(is_enabled=True).exclude(pk=obj.pk).update(is_enabled=False)
        super().save_model(request, obj, form, change)


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
