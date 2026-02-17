import uuid
import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class SiteBranding(models.Model):
    """
    Singleton branding config for Cashflip. Admin-uploadable logos, colors, tagline.
    Defaults to generated SVG assets; admin can override with uploaded files.
    """
    logo = models.FileField(upload_to='branding/', blank=True, default='',
                            help_text='Main logo (SVG/PNG). Default: static/images/cashflip-logo.svg')
    logo_icon = models.FileField(upload_to='branding/', blank=True, default='',
                                 help_text='Square icon/favicon (SVG/PNG). Default: static/images/cashflip-icon.svg')
    loading_animation = models.FileField(upload_to='branding/', blank=True, default='',
                                         help_text='Loading screen animation (GIF/SVG). Blank = CSS glow default')
    primary_color = models.CharField(max_length=7, default='#00BFA6', help_text='Electric Teal')
    secondary_color = models.CharField(max_length=7, default='#F5C842', help_text='Rich Gold')
    accent_color = models.CharField(max_length=7, default='#00E676', help_text='Lime Flash (success)')
    background_color = models.CharField(max_length=7, default='#0D1117', help_text='Midnight Obsidian')
    tagline = models.CharField(max_length=200, default='Flip Notes. Stack Cash. Win Big.',
                               help_text='Displayed on auth/loading screens')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Branding'
        verbose_name_plural = 'Site Branding'

    def __str__(self):
        return 'Cashflip Branding'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_branding(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Currency(models.Model):
    code = models.CharField(max_length=5, unique=True, db_index=True)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=5)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Currencies'
        ordering = ['-is_default', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'

    def save(self, *args, **kwargs):
        if self.is_default:
            Currency.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class CurrencyDenomination(models.Model):
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='denominations')
    value = models.DecimalField(max_digits=10, decimal_places=2)
    banknote_image = models.ImageField(
        upload_to='banknotes/', null=True, blank=True,
        help_text='Upload banknote image for this denomination'
    )
    display_order = models.PositiveIntegerField(default=0)
    is_zero = models.BooleanField(default=False, help_text='Is this the zero/loss denomination?')
    is_active = models.BooleanField(default=True)
    weight = models.PositiveIntegerField(
        default=10, help_text='Relative weight for random selection (higher = more frequent)'
    )

    class Meta:
        ordering = ['currency', 'display_order', 'value']
        unique_together = ['currency', 'value']

    def __str__(self):
        if self.is_zero:
            return f'{self.currency.code} - ZERO (loss)'
        return f'{self.currency.symbol}{self.value}'


class GameConfig(models.Model):
    currency = models.OneToOneField(Currency, on_delete=models.CASCADE, related_name='game_config')
    house_edge_percent = models.DecimalField(max_digits=5, decimal_places=2, default=60.00,
                                              help_text='House retention percentage (e.g. 60 = house keeps 60%)')
    min_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    max_cashout = models.DecimalField(max_digits=12, decimal_places=2, default=10000.00)
    min_stake = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    pause_cost_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10.00,
                                              help_text='Percentage of cashout balance charged to pause')
    zero_base_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0500,
                                          help_text='Base probability of zero (0.05 = 5%)')
    zero_growth_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0800,
                                            help_text='Growth factor k for zero probability curve')
    min_flips_before_zero = models.PositiveIntegerField(default=2,
                                                         help_text='Guaranteed safe flips before zero can appear')
    max_session_duration_minutes = models.PositiveIntegerField(default=120)
    simulated_feed_enabled = models.BooleanField(default=False,
        help_text='Enable simulated live feed for demo/pitching (fake leaderboard entries)')
    simulated_feed_data = models.JSONField(default=list, blank=True,
        help_text='Simulated feed entries: [{"player":"Luc**er","won":true,"amount":"50.00","flips":5}]')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Game Configuration'
        verbose_name_plural = 'Game Configurations'

    def __str__(self):
        return f'Config: {self.currency.code}'


class SimulatedGameConfig(models.Model):
    """
    Admin-toggleable simulation/test config that overrides normal game behaviour.
    Only one active config is used at a time (singleton pattern via get_config).
    When enabled, the game engine checks this before the normal probability curve.
    """
    OUTCOME_CHOICES = [
        ('normal', 'Normal (no override)'),
        ('always_win', 'Always Win (never zero)'),
        ('always_lose', 'Always Lose (always zero)'),
        ('force_zero_at', 'Force Zero at Specific Flip Number'),
        ('fixed_probability', 'Fixed Zero Probability (override curve)'),
        ('streak_then_lose', 'Win Streak Then Lose (win N flips, then zero)'),
    ]

    name = models.CharField(max_length=100, default='Default Test Config',
                            help_text='Label for this test scenario')
    is_enabled = models.BooleanField(default=False, db_index=True,
                                     help_text='Master switch — enable to activate simulation mode')

    # Outcome control
    outcome_mode = models.CharField(max_length=20, choices=OUTCOME_CHOICES, default='normal',
                                    help_text='How flip outcomes are determined')
    force_zero_at_flip = models.PositiveIntegerField(default=0, blank=True,
                                                     help_text='Force zero on this flip number (for force_zero_at mode)')
    fixed_zero_probability = models.DecimalField(max_digits=5, decimal_places=4, default=0,
                                                  help_text='Fixed probability 0.0–1.0 (for fixed_probability mode)')
    win_streak_length = models.PositiveIntegerField(default=5,
                                                     help_text='Number of guaranteed wins before forced loss (streak_then_lose mode)')

    # Denomination control
    force_denomination_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                                    help_text='Force this denomination value on every win flip (blank = random)')

    # Targeting
    apply_to_all_players = models.BooleanField(default=True,
                                               help_text='Apply to all players, or only targeted players below')
    targeted_players = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True,
                                             related_name='simulated_configs',
                                             help_text='If not apply_to_all, only these players get simulation')

    # Limit overrides for testing
    override_min_stake = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                             help_text='Override min stake for test (blank = use normal config)')
    override_max_cashout = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                               help_text='Override max cashout for test (blank = use normal config)')

    # Test wallet
    grant_test_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                             help_text='Auto-grant this balance to targeted players on session start (0 = disabled)')

    # Safety
    auto_disable_after = models.PositiveIntegerField(default=0,
                                                      help_text='Auto-disable after N game sessions (0 = never)')
    sessions_used = models.PositiveIntegerField(default=0, editable=False,
                                                help_text='Sessions played under this config')

    notes = models.TextField(blank=True, default='',
                             help_text='Internal notes about this test scenario')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Simulated Game Config'
        verbose_name_plural = 'Simulated Game Configs'
        ordering = ['-is_enabled', '-updated_at']

    def __str__(self):
        status = 'ACTIVE' if self.is_enabled else 'OFF'
        return f'[{status}] {self.name} ({self.get_outcome_mode_display()})'

    @classmethod
    def get_active_config(cls):
        """Return the first enabled config, or None."""
        return cls.objects.filter(is_enabled=True).first()

    def applies_to_player(self, player):
        """Check if this config applies to the given player."""
        if self.apply_to_all_players:
            return True
        return self.targeted_players.filter(pk=player.pk).exists()

    def increment_usage(self):
        """Track usage and auto-disable if limit reached."""
        self.sessions_used += 1
        if self.auto_disable_after > 0 and self.sessions_used >= self.auto_disable_after:
            self.is_enabled = False
        self.save(update_fields=['sessions_used', 'is_enabled'])


class GameSession(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('cashed_out', 'Cashed Out'),
        ('lost', 'Lost'),
        ('paused', 'Paused'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='game_sessions')
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name='sessions')
    stake_amount = models.DecimalField(max_digits=12, decimal_places=2)
    cashout_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active', db_index=True)
    flip_count = models.PositiveIntegerField(default=0)
    server_seed = models.CharField(max_length=64, blank=True, default='')
    server_seed_hash = models.CharField(max_length=64, blank=True, default='')
    client_seed = models.CharField(max_length=64, blank=True, default='')
    nonce = models.PositiveIntegerField(default=0)
    pause_fee_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['player', 'status']),
        ]

    def __str__(self):
        return f'Session {str(self.id)[:8]} - {self.player} ({self.status})'

    def generate_seeds(self):
        self.server_seed = secrets.token_hex(32)
        self.server_seed_hash = hashlib.sha256(self.server_seed.encode()).hexdigest()
        self.client_seed = secrets.token_hex(16)
        self.save(update_fields=['server_seed', 'server_seed_hash', 'client_seed'])


class FlipResult(models.Model):
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name='flips')
    flip_number = models.PositiveIntegerField()
    denomination = models.ForeignKey(CurrencyDenomination, on_delete=models.PROTECT, null=True)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    is_zero = models.BooleanField(default=False)
    cumulative_balance = models.DecimalField(max_digits=12, decimal_places=2)
    result_hash = models.CharField(max_length=64, blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['session', 'flip_number']
        unique_together = ['session', 'flip_number']

    def __str__(self):
        if self.is_zero:
            return f'Flip #{self.flip_number} - ZERO (loss)'
        return f'Flip #{self.flip_number} - {self.value}'
