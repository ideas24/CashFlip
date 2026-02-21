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
    # Cloudinary URL overrides (set by admin dashboard upload, take priority over FileField)
    logo_cloud_url = models.URLField(max_length=500, blank=True, default='',
        help_text='Cloudinary URL for main logo (overrides logo FileField)')
    logo_icon_cloud_url = models.URLField(max_length=500, blank=True, default='',
        help_text='Cloudinary URL for icon/favicon (overrides logo_icon FileField)')
    loading_animation_cloud_url = models.URLField(max_length=500, blank=True, default='',
        help_text='Cloudinary URL for loading animation (overrides loading_animation FileField)')
    # Regulatory footer
    regulatory_logo = models.FileField(upload_to='branding/', blank=True, default='',
        help_text='Gaming commission logo (SVG/PNG). Default: static/images/Ghana-Gaming-Commission-logo.png')
    regulatory_logo_cloud_url = models.URLField(max_length=500, blank=True, default='',
        help_text='Cloudinary URL for regulatory logo')
    regulatory_text = models.CharField(max_length=300, default='Regulated by the Gaming Commission of Ghana',
        help_text='Text displayed alongside the regulatory logo')
    age_restriction_text = models.CharField(max_length=10, default='18+',
        help_text='Age restriction badge text')
    responsible_gaming_text = models.CharField(max_length=200, default='Bet Responsibly',
        help_text='Responsible gaming message')
    show_regulatory_footer = models.BooleanField(default=True,
        help_text='Show regulatory footer on auth/landing screens')
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


class LegalDocument(models.Model):
    """
    Singleton store for editable legal documents (Privacy Policy, Terms of Service).
    Content is stored as HTML for rich formatting. Editable from admin dashboard.
    """
    privacy_policy = models.TextField(blank=True, default='',
        help_text='Privacy Policy content (HTML)')
    terms_of_service = models.TextField(blank=True, default='',
        help_text='Terms of Service content (HTML)')
    sms_disclosure = models.TextField(blank=True,
        default='By providing your phone number, you consent to receive a one-time verification code via SMS. Standard message and data rates may apply. Carriers are not liable for delayed or undelivered messages.',
        help_text='SMS/messaging disclosure shown on login screen')
    support_email = models.EmailField(blank=True, default='support@cashflip.cash',
        help_text='Support email shown in legal docs')
    support_phone = models.CharField(max_length=30, blank=True, default='',
        help_text='Support phone shown in legal docs')
    company_name = models.CharField(max_length=200, blank=True, default='CashFlip',
        help_text='Legal company name')
    company_address = models.TextField(blank=True, default='',
        help_text='Registered company address')
    license_info = models.TextField(blank=True, default='Licensed and regulated by the Gaming Commission of Ghana.',
        help_text='License/regulatory information')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Legal Document'
        verbose_name_plural = 'Legal Documents'

    def __str__(self):
        return 'Legal Documents'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_legal(cls):
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
    value = models.DecimalField(max_digits=10, decimal_places=2,
        help_text='Face value of the note (visual only, e.g. 1, 5, 10, 50)')
    payout_multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=10.00,
        help_text='Payout as % of stake per flip. E.g. 8 = each flip adds 8% of stake. '
                  'Tune so that avg_multiplier × expected_flips < 100 for house edge.')
    front_image = models.ImageField(
        upload_to='banknotes/front/', null=True, blank=True,
        help_text='Front side of the banknote. Recommended: 960×510 px (2x) or 1440×765 px (3x), PNG/JPEG, < 200KB'
    )
    back_image = models.ImageField(
        upload_to='banknotes/back/', null=True, blank=True,
        help_text='Back side of the banknote. Recommended: 960×510 px (2x) or 1440×765 px (3x), PNG/JPEG, < 200KB'
    )
    face_image_upload = models.FileField(
        upload_to='banknotes/faces/', null=True, blank=True,
        help_text='Upload face image (JPG/PNG). Takes priority over face_image_path. 1920×1080 recommended.'
    )
    flip_gif_upload = models.FileField(
        upload_to='banknotes/gifs/', null=True, blank=True,
        help_text='Upload flip animation GIF. Takes priority over flip_gif_path. 1920×1080 recommended.'
    )
    face_image_path = models.CharField(max_length=255, blank=True, default='',
        help_text='Static path to face image, e.g. images/Cedi-Face/5f.jpg (fallback if no upload)')
    flip_sequence_prefix = models.CharField(max_length=255, blank=True, default='',
        help_text='Static path to flip sequence folder, e.g. images/Cedi-Sequences/5')
    flip_sequence_frames = models.PositiveIntegerField(default=31,
        help_text='Number of frames in the flip sequence (0-indexed PNGs)')
    flip_gif_path = models.CharField(max_length=255, blank=True, default='',
        help_text='Static path to flip GIF, e.g. images/Cedi-Gifs/5cedis.gif (fallback if no upload)')
    flip_video_path = models.CharField(max_length=500, blank=True, default='',
        help_text='Path or Cloudinary URL to flip MP4/WebM video, e.g. videos/5cedis.mp4')
    display_order = models.PositiveIntegerField(default=0)
    is_zero = models.BooleanField(default=False, help_text='Is this the zero/loss denomination?')
    is_active = models.BooleanField(default=True)
    weight = models.PositiveIntegerField(
        default=10, help_text='Relative weight for random selection (higher = more frequent)'
    )
    boost_payout_multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=0,
        help_text='Payout multiplier used in boost mode (0 = auto-calculated from normal × boost_multiplier_factor)')

    class Meta:
        ordering = ['currency', 'display_order', 'value']
        unique_together = ['currency', 'value']

    def __str__(self):
        if self.is_zero:
            return f'{self.currency.code} - ZERO (loss)'
        return f'{self.currency.symbol}{self.value}'


class GameConfig(models.Model):
    currency = models.OneToOneField(Currency, on_delete=models.CASCADE, related_name='game_config')
    house_edge_percent = models.DecimalField(max_digits=5, decimal_places=2, default=70.00,
                                              help_text='House retention percentage (e.g. 70 = house keeps 70%)')
    min_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    max_cashout = models.DecimalField(max_digits=12, decimal_places=2, default=10000.00)
    min_stake = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    payout_mode = models.CharField(max_length=10, default='normal',
        choices=[('normal', 'Normal'), ('boost', 'Boost')],
        help_text='Normal = 70/30 house/player split. Boost = 60/40 (use when participation is down)')
    normal_payout_target = models.DecimalField(max_digits=5, decimal_places=2, default=30.00,
        help_text='Target player payout % in normal mode (30 = players get back 30% of stakes)')
    boost_payout_target = models.DecimalField(max_digits=5, decimal_places=2, default=40.00,
        help_text='Target player payout % in boost mode (40 = players get back 40% of stakes)')
    boost_multiplier_factor = models.DecimalField(max_digits=4, decimal_places=2, default=1.33,
        help_text='Factor to multiply normal multipliers by in boost mode (1.33 = 33% increase)')
    pause_cost_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10.00,
                                              help_text='Percentage of cashout balance charged to pause')
    zero_base_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0500,
                                          help_text='Base probability of zero (0.05 = 5%)')
    zero_growth_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0800,
                                            help_text='Growth factor k for zero probability curve')
    min_flips_before_zero = models.PositiveIntegerField(default=2,
                                                         help_text='Guaranteed safe flips before zero can appear')
    min_flips_before_cashout = models.PositiveIntegerField(default=3,
        help_text='Minimum flips required before player can cash out (prevents risk-free profit)')
    instant_cashout_enabled = models.BooleanField(default=True,
        help_text='Allow players to send winnings directly to MoMo on cashout')
    instant_cashout_min_amount = models.DecimalField(max_digits=10, decimal_places=2, default=5.00,
        help_text='Minimum cashout amount eligible for instant MoMo payout')
    max_session_duration_minutes = models.PositiveIntegerField(default=120)
    auto_flip_seconds = models.PositiveIntegerField(default=8,
        help_text='Seconds before auto-flip triggers if player idles (0 = disabled)')
    # Exponential decay payout engine
    decay_factor = models.DecimalField(max_digits=6, decimal_places=4, default=0.0500,
        help_text='Decay factor k for exponential weight curve. Small k=equal payouts, large k=front-loaded. '
                  'Formula: weight_i = e^(-k * (i-1))')
    max_flips_per_session = models.PositiveIntegerField(default=10,
        help_text='Maximum number of flips allowed per session (budget may end sooner)')
    # Holiday trigger
    holiday_mode_enabled = models.BooleanField(default=False,
        help_text='Enable Holiday trigger: randomly boost payout for selected low-stake players')
    holiday_boost_pct = models.DecimalField(max_digits=5, decimal_places=2, default=70.00,
        help_text='Payout percentage for holiday-boosted players (e.g. 70 = they get 70% back instead of 40%)')
    holiday_frequency = models.PositiveIntegerField(default=1000,
        help_text='1 in N active players gets the holiday boost (e.g. 1000 = 0.1% chance)')
    holiday_max_tier_name = models.CharField(max_length=50, default='Standard', blank=True,
        help_text='Only players in this tier or lower get holiday boost (empty = all tiers)')
    flip_animation_mode = models.CharField(max_length=10, default='css3d',
        choices=[('css3d', 'CSS 3D Flip'), ('gif', 'GIF Animation'), ('png', 'PNG Sequence'), ('video', 'MP4/WebM Video')],
        help_text='Which animation format to use for note flips')
    flip_display_mode = models.CharField(max_length=20, default='face_then_gif',
        choices=[('face_then_gif', 'Face Image then GIF'), ('gif_only', 'GIF Only (static first frame)')],
        help_text='face_then_gif = show face JPG then play GIF on flip. '
                  'gif_only = show GIF first frame as static, play full GIF on flip.')
    flip_animation_speed_ms = models.PositiveIntegerField(default=1500,
        help_text='Duration of the flip animation in milliseconds (e.g. 1500 = 1.5s)')
    flip_sound_enabled = models.BooleanField(default=True,
        help_text='Play money-flipping sound during flip animation')
    flip_sound_url = models.URLField(max_length=500, blank=True, default='',
        help_text='Custom flip sound URL (Cloudinary). Empty = use default /static/sounds/money-flip.mp3')
    win_sound_url = models.URLField(max_length=500, blank=True, default='',
        help_text='Custom win celebration sound URL. Empty = use default /static/sounds/money-win.mp3')
    cashout_sound_url = models.URLField(max_length=500, blank=True, default='',
        help_text='Custom cashout celebration sound URL. Empty = use default /static/sounds/money-cashout.mp3')
    start_flip_image_url = models.URLField(max_length=500, blank=True, default='',
        help_text='Image shown on the first card when a new session starts (Cloudinary). Subsequent cards show denomination glimpses.')
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


class StakeTier(models.Model):
    """Maps stake ranges to denomination subsets for tiered gameplay."""
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='stake_tiers')
    name = models.CharField(max_length=50, help_text='Tier display name (e.g. Standard, Premium, VIP)')
    min_stake = models.DecimalField(max_digits=12, decimal_places=2,
        help_text='Minimum stake for this tier (inclusive)')
    max_stake = models.DecimalField(max_digits=12, decimal_places=2,
        help_text='Maximum stake for this tier (inclusive)')
    denominations = models.ManyToManyField(CurrencyDenomination, blank=True,
        related_name='stake_tiers',
        help_text='Which denominations appear when playing at this stake level')
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['currency', 'display_order', 'min_stake']
        verbose_name = 'Stake Tier'
        verbose_name_plural = 'Stake Tiers'

    def __str__(self):
        return f'{self.currency.code} {self.name} ({self.min_stake}-{self.max_stake})'


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
    payout_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0,
        help_text='Total payout budget for this session = stake × payout_pct. Denomination face values deducted from this.')
    remaining_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0,
        help_text='Remaining payout budget (decreases as player flips). Zero when exhausted.')
    payout_pct_used = models.DecimalField(max_digits=5, decimal_places=2, default=0,
        help_text='The actual payout percentage used for this session (may be boosted by holiday trigger)')
    is_holiday_boosted = models.BooleanField(default=False,
        help_text='Whether this session received the holiday boost')
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


class Badge(models.Model):
    """Achievement badges that players can earn."""
    BADGE_TYPES = [
        ('first_win', 'First Win'),
        ('streak_3', '3-Win Streak'),
        ('streak_5', '5-Win Streak'),
        ('streak_7', '7-Win Streak'),
        ('high_roller', 'High Roller (₵100+ stake)'),
        ('big_cashout', 'Big Cashout (₵50+)'),
        ('mega_cashout', 'Mega Cashout (₵200+)'),
        ('flip_master', 'Flip Master (100 flips)'),
        ('veteran', 'Veteran (50 sessions)'),
        ('daily_player', 'Daily Player (7 day streak)'),
        ('lucky_7', 'Lucky 7 (won on flip #7)'),
        ('whale', 'Whale (₵500+ single stake)'),
        ('social', 'Social (referred a friend)'),
        ('depositor', 'First Deposit'),
    ]

    code = models.CharField(max_length=30, unique=True, choices=BADGE_TYPES)
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    emoji = models.CharField(max_length=10, default='🏆')
    xp_value = models.PositiveIntegerField(default=10, help_text='XP points awarded')
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'code']

    def __str__(self):
        return f'{self.emoji} {self.name}'


class PlayerBadge(models.Model):
    """Track which badges a player has earned."""
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='awards')
    earned_at = models.DateTimeField(auto_now_add=True)
    session = models.ForeignKey('GameSession', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ['player', 'badge']
        ordering = ['-earned_at']

    def __str__(self):
        return f'{self.player} - {self.badge.name}'


class DailyBonusConfig(models.Model):
    """Admin-configurable daily bonus wheel settings."""
    is_enabled = models.BooleanField(default=True)
    segments = models.JSONField(default=list, blank=True,
        help_text='Wheel segments: [{"label":"₵0.50","value":0.50,"color":"#ffd700","weight":30}, ...]')
    cooldown_hours = models.PositiveIntegerField(default=24, help_text='Hours between spins')
    max_spins_per_day = models.PositiveIntegerField(default=1)
    require_deposit = models.BooleanField(default=False, help_text='Require at least one deposit to spin')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Daily Bonus Config'

    def __str__(self):
        return f'Daily Bonus ({"Enabled" if self.is_enabled else "Disabled"})'

    @classmethod
    def get_config(cls):
        return cls.objects.first()

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class DailyBonusSpin(models.Model):
    """Track daily bonus wheel spins."""
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bonus_spins')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    segment_label = models.CharField(max_length=50)
    spun_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-spun_at']

    def __str__(self):
        return f'{self.player} - {self.segment_label} ({self.amount})'


class FeatureConfig(models.Model):
    """Global feature toggles manageable from admin console."""
    badges_enabled = models.BooleanField(default=True, help_text='Achievement badges system')
    daily_wheel_enabled = models.BooleanField(default=True, help_text='Daily bonus wheel')
    sounds_enabled = models.BooleanField(default=True, help_text='Casino sound effects')
    haptics_enabled = models.BooleanField(default=True, help_text='Mobile haptic feedback')
    social_proof_enabled = models.BooleanField(default=True, help_text='Live win toast notifications')
    streak_badge_enabled = models.BooleanField(default=True, help_text='Win streak fire badge')
    confetti_enabled = models.BooleanField(default=True, help_text='Win/loss confetti particles')
    deposit_sound_enabled = models.BooleanField(default=True, help_text='Soothing sound on deposit CTA')
    social_proof_min_amount = models.DecimalField(max_digits=10, decimal_places=2, default=10.00,
        help_text='Minimum win amount to show social proof toast')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Feature Configuration'

    def __str__(self):
        return 'Feature Configuration'

    @classmethod
    def get_config(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
