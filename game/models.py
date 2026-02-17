import uuid
import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


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
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Game Configuration'
        verbose_name_plural = 'Game Configurations'

    def __str__(self):
        return f'Config: {self.currency.code}'


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
