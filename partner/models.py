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


# ==================== OTP AS A SERVICE (OTPaaS) ====================

class OTPPricingTier(models.Model):
    """
    Tiered pricing for OTP service.
    Monthly volume thresholds determine per-OTP cost.
    """
    name = models.CharField(max_length=50, unique=True, help_text='Tier name e.g. Starter, Growth, Enterprise')
    min_monthly_volume = models.PositiveIntegerField(default=0, help_text='Min OTPs/month for this tier')
    max_monthly_volume = models.PositiveIntegerField(default=0, help_text='Max OTPs/month (0=unlimited)')
    price_per_otp_whatsapp = models.DecimalField(max_digits=8, decimal_places=4, default=0.0300,
        help_text='Cost per WhatsApp OTP in GHS')
    price_per_otp_sms = models.DecimalField(max_digits=8, decimal_places=4, default=0.0500,
        help_text='Cost per SMS OTP in GHS')
    whitelabel_fee_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        help_text='Monthly fee for custom sender ID / whitelabel (0=not available)')
    whitelabel_available = models.BooleanField(default=False,
        help_text='Whether custom sender ID is available on this tier')
    monthly_base_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        help_text='Monthly platform fee (0=pay-per-use only)')
    priority_support = models.BooleanField(default=False)
    sla_uptime = models.DecimalField(max_digits=5, decimal_places=2, default=99.00,
        help_text='SLA uptime guarantee %')
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'min_monthly_volume']
        verbose_name = 'OTP Pricing Tier'

    def __str__(self):
        return f'{self.name} (₵{self.price_per_otp_whatsapp}/WA, ₵{self.price_per_otp_sms}/SMS)'


class OTPClient(models.Model):
    """
    External client (business) using Cashflip's OTP as a Service.
    Can optionally also be a game Operator, or standalone OTP-only client.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('deactivated', 'Deactivated'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.OneToOneField(Operator, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='otp_client', help_text='Link to game operator if this is a GaaS partner')
    company_name = models.CharField(max_length=200, help_text='Business name')
    slug = models.SlugField(max_length=50, unique=True, help_text='URL-safe identifier')
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True, default='')
    website = models.URLField(blank=True, default='')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True)
    pricing_tier = models.ForeignKey(OTPPricingTier, on_delete=models.PROTECT,
        related_name='clients', help_text='Current pricing tier')

    # Rate limiting
    rate_limit_per_minute = models.PositiveIntegerField(default=60,
        help_text='Max OTP requests per minute across all keys')
    rate_limit_per_phone_per_hour = models.PositiveIntegerField(default=5,
        help_text='Max OTPs to same phone number per hour')
    daily_limit = models.PositiveIntegerField(default=10000,
        help_text='Max OTPs per day (0=unlimited)')

    # OTP configuration
    otp_length = models.PositiveSmallIntegerField(default=6, help_text='OTP code length (4-8)')
    otp_expiry_seconds = models.PositiveIntegerField(default=300, help_text='OTP validity in seconds')
    allowed_channels = models.JSONField(default=list,
        help_text='["whatsapp","sms"] — channels this client can use')
    default_channel = models.CharField(max_length=10, default='whatsapp',
        help_text='Default delivery channel')

    # Callback / webhook
    callback_url = models.URLField(blank=True, default='',
        help_text='Webhook URL for delivery status callbacks')
    callback_secret = models.CharField(max_length=128, blank=True, default='',
        help_text='HMAC secret for signing callback payloads')

    # Billing
    prepaid_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
        help_text='Prepaid credit balance in GHS')
    billing_mode = models.CharField(max_length=10, default='prepaid',
        choices=[('prepaid', 'Prepaid'), ('postpaid', 'Postpaid')],
        help_text='Prepaid deducts per OTP; postpaid invoices monthly')
    auto_suspend_on_zero = models.BooleanField(default=True,
        help_text='Auto-suspend when prepaid balance reaches zero')

    # IP restrictions
    ip_whitelist = models.JSONField(default=list, blank=True,
        help_text='List of allowed IPs (empty=allow all)')

    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['company_name']
        verbose_name = 'OTP Client'

    def __str__(self):
        return f'{self.company_name} [{self.get_status_display()}]'

    @property
    def is_live(self):
        return self.status == 'active'


class OTPClientAPIKey(models.Model):
    """
    API key for OTPaaS client authentication.
    Uses same HMAC pattern as partner API but with otp_ prefix.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(OTPClient, on_delete=models.CASCADE, related_name='api_keys')
    label = models.CharField(max_length=100, default='Default')
    api_key = models.CharField(max_length=64, unique=True, db_index=True,
        help_text='Public key sent in X-OTP-Key header')
    api_secret = models.CharField(max_length=128,
        help_text='HMAC secret for signing requests')
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'OTP API Key'

    def __str__(self):
        status = 'active' if self.is_active else 'revoked'
        return f'{self.client.company_name} - {self.label} ({status})'

    @staticmethod
    def generate_key_pair():
        api_key = f'otp_live_{secrets.token_hex(24)}'
        api_secret = secrets.token_hex(48)
        return api_key, api_secret

    def verify_signature(self, body_bytes, signature):
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


class OTPSenderID(models.Model):
    """
    Whitelabel sender ID configuration for premium clients.
    Allows clients to send OTP from their own WhatsApp Business number
    or custom SMS sender ID.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(OTPClient, on_delete=models.CASCADE, related_name='sender_ids')
    channel = models.CharField(max_length=10, choices=[('whatsapp', 'WhatsApp'), ('sms', 'SMS')])

    # WhatsApp sender config
    whatsapp_phone_number_id = models.CharField(max_length=50, blank=True, default='',
        help_text='Client WhatsApp Business phone number ID (Meta)')
    whatsapp_access_token = models.TextField(blank=True, default='',
        help_text='Client WhatsApp Business access token (encrypted at rest)')
    whatsapp_template_name = models.CharField(max_length=100, blank=True, default='',
        help_text='Client custom auth template name')
    whatsapp_business_name = models.CharField(max_length=200, blank=True, default='',
        help_text='Display name shown to recipients')

    # SMS sender config
    sms_sender_id = models.CharField(max_length=11, blank=True, default='',
        help_text='Alphanumeric sender ID for SMS (max 11 chars)')
    sms_provider = models.CharField(max_length=20, blank=True, default='twilio',
        choices=[('twilio', 'Twilio'), ('arkesel', 'Arkesel'), ('hubtel', 'Hubtel')])
    sms_provider_config = models.JSONField(default=dict, blank=True,
        help_text='Provider-specific config (account SID, auth token, etc.)')

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    verified_at = models.DateTimeField(null=True, blank=True)
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        help_text='Monthly whitelabel fee charged for this sender ID')
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'OTP Sender ID'
        unique_together = ['client', 'channel']

    def __str__(self):
        if self.channel == 'whatsapp':
            return f'{self.client.company_name} WA: {self.whatsapp_business_name or self.whatsapp_phone_number_id}'
        return f'{self.client.company_name} SMS: {self.sms_sender_id}'


class OTPRequest(models.Model):
    """
    Individual OTP request log. Every OTP send and verify is recorded.
    Used for billing, analytics, debugging, and audit trail.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected (wrong code)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(OTPClient, on_delete=models.CASCADE, related_name='otp_requests', db_index=True)
    api_key = models.ForeignKey(OTPClientAPIKey, on_delete=models.SET_NULL, null=True, blank=True)
    sender_id = models.ForeignKey(OTPSenderID, on_delete=models.SET_NULL, null=True, blank=True,
        help_text='Custom sender used (null=Cashflip default)')

    # Request details
    phone = models.CharField(max_length=20, db_index=True)
    channel = models.CharField(max_length=10, choices=[('whatsapp', 'WhatsApp'), ('sms', 'SMS')])
    code = models.CharField(max_length=8, help_text='Generated OTP code')
    code_hash = models.CharField(max_length=64, blank=True, default='',
        help_text='SHA-256 hash of code for secure storage')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True)
    expires_at = models.DateTimeField()

    # Delivery metadata
    provider_message_id = models.CharField(max_length=100, blank=True, default='',
        help_text='Message ID from WhatsApp/SMS provider')
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_attempts = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(blank=True, default='')

    # Verification
    verified_at = models.DateTimeField(null=True, blank=True)
    verify_attempts = models.PositiveSmallIntegerField(default=0,
        help_text='Number of incorrect verification attempts')
    max_verify_attempts = models.PositiveSmallIntegerField(default=3)

    # Billing
    cost = models.DecimalField(max_digits=8, decimal_places=4, default=0,
        help_text='Cost charged for this OTP')
    billed = models.BooleanField(default=False)

    # Client metadata
    client_ref = models.CharField(max_length=100, blank=True, default='',
        help_text='Client-provided reference for their own tracking')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True,
        help_text='Freeform metadata from client')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'phone', 'status']),
            models.Index(fields=['client', 'created_at']),
            models.Index(fields=['phone', 'created_at']),
        ]
        verbose_name = 'OTP Request'

    def __str__(self):
        return f'OTP {self.phone} via {self.channel} [{self.status}]'

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_verifiable(self):
        return (
            self.status in ('sent', 'delivered')
            and not self.is_expired
            and self.verify_attempts < self.max_verify_attempts
        )


class OTPClientUsage(models.Model):
    """
    Daily aggregated usage per client for billing and analytics.
    One row per client per day.
    """
    client = models.ForeignKey(OTPClient, on_delete=models.CASCADE, related_name='daily_usage')
    date = models.DateField(db_index=True)

    # Volume
    whatsapp_sent = models.PositiveIntegerField(default=0)
    whatsapp_delivered = models.PositiveIntegerField(default=0)
    whatsapp_failed = models.PositiveIntegerField(default=0)
    sms_sent = models.PositiveIntegerField(default=0)
    sms_delivered = models.PositiveIntegerField(default=0)
    sms_failed = models.PositiveIntegerField(default=0)
    total_verified = models.PositiveIntegerField(default=0)
    total_expired = models.PositiveIntegerField(default=0)

    # Costs
    whatsapp_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sms_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = ['client', 'date']
        verbose_name = 'OTP Client Daily Usage'
        verbose_name_plural = 'OTP Client Daily Usage'

    def __str__(self):
        total = self.whatsapp_sent + self.sms_sent
        return f'{self.client.company_name} {self.date}: {total} OTPs, ₵{self.total_cost}'
