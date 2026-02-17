import uuid
import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class Operator(models.Model):
    """
    Partner operator (e.g. Elitebet) who licenses Cashflip as a service.
    Wallet URLs are portal-editable — update when partner provides endpoints.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('deactivated', 'Deactivated'),
    ]
    SETTLEMENT_FREQ = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text='Brand name (e.g. Elitebet)')
    slug = models.SlugField(max_length=50, unique=True, help_text='URL-safe identifier')
    website = models.URLField(blank=True, default='', help_text='e.g. https://elitebetgh.com')
    contact_email = models.EmailField(blank=True, default='')
    contact_phone = models.CharField(max_length=20, blank=True, default='')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True)

    # Seamless wallet URLs — portal-editable
    debit_url = models.URLField(blank=True, default='',
                                help_text='Operator endpoint we call to debit player on bet')
    credit_url = models.URLField(blank=True, default='',
                                 help_text='Operator endpoint we call to credit player on win')
    rollback_url = models.URLField(blank=True, default='',
                                   help_text='Operator endpoint we call to rollback a failed debit')
    wallet_auth_token = models.CharField(max_length=500, blank=True, default='',
                                         help_text='Bearer token we send when calling operator wallet URLs')

    # Commission & settlement
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=20.00,
                                             help_text='Cashflip keeps this % of GGR (e.g. 20.00)')
    settlement_frequency = models.CharField(max_length=10, choices=SETTLEMENT_FREQ, default='weekly')
    min_settlement_amount = models.DecimalField(max_digits=12, decimal_places=2, default=100.00,
                                                help_text='Minimum GGR before settlement is generated')

    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} [{self.get_status_display()}]'

    @property
    def is_live(self):
        return self.status == 'active' and bool(self.debit_url) and bool(self.credit_url)


class OperatorBranding(models.Model):
    """
    Per-operator branding for the embedded game iframe loader.
    """
    operator = models.OneToOneField(Operator, on_delete=models.CASCADE, related_name='branding')
    display_name = models.CharField(max_length=100, blank=True, default='',
                                    help_text='Name shown on loading screen (defaults to operator name)')
    logo = models.ImageField(upload_to='partner/branding/', blank=True,
                             help_text='Operator logo for iframe loader')
    loading_animation = models.FileField(upload_to='partner/branding/', blank=True,
                                         help_text='Loading animation (GIF/SVG). Blank = Cashflip default')
    primary_color = models.CharField(max_length=7, default='#000000', help_text='Operator primary brand color')
    accent_color = models.CharField(max_length=7, default='#F5C842', help_text='Accent color')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Operator Branding'
        verbose_name_plural = 'Operator Brandings'

    def __str__(self):
        return f'Branding: {self.operator.name}'

    @property
    def effective_display_name(self):
        return self.display_name or self.operator.name


class OperatorAPIKey(models.Model):
    """
    HMAC API key for partner authentication.
    Key is shown once on creation; secret is used for HMAC signing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name='api_keys')
    label = models.CharField(max_length=100, default='Default', help_text='Label for this key')
    api_key = models.CharField(max_length=64, unique=True, db_index=True,
                               help_text='Public API key sent in X-API-Key header')
    api_secret = models.CharField(max_length=128, help_text='HMAC secret for signing')
    is_active = models.BooleanField(default=True)
    rate_limit_per_minute = models.PositiveIntegerField(default=120,
                                                        help_text='Max requests per minute')
    ip_whitelist = models.JSONField(default=list, blank=True,
                                    help_text='List of allowed IPs (empty = allow all)')
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
        ordering = ['-created_at']

    def __str__(self):
        status = 'active' if self.is_active else 'revoked'
        return f'{self.operator.name} - {self.label} ({status})'

    @staticmethod
    def generate_key_pair():
        """Generate a new API key + secret pair."""
        api_key = f'cf_live_{secrets.token_hex(24)}'
        api_secret = secrets.token_hex(48)
        return api_key, api_secret

    def verify_signature(self, body_bytes, signature):
        """Verify HMAC-SHA256 signature of request body."""
        expected = hmac.new(
            self.api_secret.encode(),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=['is_active', 'revoked_at'])


class OperatorGameConfig(models.Model):
    """
    Per-operator game configuration. Overrides the global GameConfig.
    """
    operator = models.OneToOneField(Operator, on_delete=models.CASCADE, related_name='game_config')
    currency = models.ForeignKey('game.Currency', on_delete=models.PROTECT,
                                 help_text='Currency this operator uses')
    house_edge_percent = models.DecimalField(max_digits=5, decimal_places=2, default=60.00)
    min_stake = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    max_stake = models.DecimalField(max_digits=12, decimal_places=2, default=1000.00)
    max_cashout = models.DecimalField(max_digits=12, decimal_places=2, default=10000.00)
    zero_base_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0500)
    zero_growth_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0800)
    min_flips_before_zero = models.PositiveIntegerField(default=2)
    pause_cost_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    max_session_duration_minutes = models.PositiveIntegerField(default=120)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Operator Game Config'
        verbose_name_plural = 'Operator Game Configs'

    def __str__(self):
        return f'Game Config: {self.operator.name}'


class OperatorPlayer(models.Model):
    """
    Maps operator's external player ID to internal Cashflip Player.
    One external player per operator.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name='players')
    ext_player_id = models.CharField(max_length=200, db_index=True,
                                     help_text='Player ID in the operator\'s system')
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='operator_mappings')
    display_name = models.CharField(max_length=200, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['operator', 'ext_player_id']
        indexes = [
            models.Index(fields=['operator', 'ext_player_id']),
        ]

    def __str__(self):
        return f'{self.operator.name}:{self.ext_player_id} → {self.player}'


class OperatorSession(models.Model):
    """
    Links a GameSession to an operator context.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name='sessions')
    operator_player = models.ForeignKey(OperatorPlayer, on_delete=models.CASCADE, related_name='sessions')
    game_session = models.OneToOneField('game.GameSession', on_delete=models.CASCADE,
                                        related_name='operator_session')
    ext_session_ref = models.CharField(max_length=200, blank=True, default='',
                                       help_text='External reference from operator')
    debit_tx_ref = models.CharField(max_length=100, blank=True, default='',
                                    help_text='Our tx ref for the debit call')
    credit_tx_ref = models.CharField(max_length=100, blank=True, default='',
                                     help_text='Our tx ref for the credit call')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.operator.name} session {str(self.id)[:8]}'


class OperatorTransaction(models.Model):
    """
    Ledger for seamless wallet calls to/from operator.
    """
    TX_TYPES = [
        ('debit', 'Debit (bet)'),
        ('credit', 'Credit (win)'),
        ('rollback', 'Rollback'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name='transactions')
    operator_session = models.ForeignKey(OperatorSession, on_delete=models.CASCADE,
                                         related_name='transactions', null=True, blank=True)
    operator_player = models.ForeignKey(OperatorPlayer, on_delete=models.CASCADE, related_name='transactions')
    tx_type = models.CharField(max_length=10, choices=TX_TYPES, db_index=True)
    tx_ref = models.CharField(max_length=100, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency_code = models.CharField(max_length=5, default='GHS')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default='')
    retries = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['operator', 'tx_type', 'status']),
        ]

    def __str__(self):
        return f'{self.tx_type} {self.amount} {self.currency_code} ({self.status})'


class OperatorWebhookConfig(models.Model):
    """
    Webhook endpoint configuration per operator.
    """
    EVENT_CHOICES = [
        ('game.started', 'Game Started'),
        ('game.flip', 'Flip Result'),
        ('game.won', 'Game Won (cashout)'),
        ('game.lost', 'Game Lost (zero)'),
        ('game.expired', 'Game Expired'),
        ('settlement.ready', 'Settlement Ready'),
    ]

    operator = models.OneToOneField(Operator, on_delete=models.CASCADE, related_name='webhook_config')
    webhook_url = models.URLField(help_text='URL to receive webhook events')
    subscribed_events = models.JSONField(default=list,
                                         help_text='List of event types to send')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Webhook Config'
        verbose_name_plural = 'Webhook Configs'

    def __str__(self):
        return f'Webhook: {self.operator.name}'


class OperatorWebhookLog(models.Model):
    """
    Delivery log for each webhook event sent.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name='webhook_logs')
    event = models.CharField(max_length=30, db_index=True)
    payload = models.JSONField(default=dict)
    signature = models.CharField(max_length=128, blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    response_status_code = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default='')
    retries = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.event} → {self.operator.name} ({self.status})'


class OperatorSettlement(models.Model):
    """
    Periodic GGR settlement between Cashflip and operator.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('disputed', 'Disputed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name='settlements')
    period_start = models.DateField()
    period_end = models.DateField()
    total_bets = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_wins = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    ggr = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                              help_text='Gross Gaming Revenue = total_bets - total_wins')
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                             help_text='Snapshot of rate at settlement time')
    commission_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                            help_text='Amount Cashflip keeps')
    net_operator_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                              help_text='Amount due to operator')
    currency_code = models.CharField(max_length=5, default='GHS')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-period_end']
        unique_together = ['operator', 'period_start', 'period_end']

    def __str__(self):
        return f'{self.operator.name} settlement {self.period_start} to {self.period_end} ({self.status})'
