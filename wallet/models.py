import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Wallet(models.Model):
    player = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.ForeignKey('game.Currency', on_delete=models.PROTECT, related_name='wallets')
    locked_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                          help_text='Balance locked in active game sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.player} - {self.currency.symbol}{self.balance}'

    @property
    def available_balance(self):
        return self.balance - self.locked_balance


class WalletTransaction(models.Model):
    TX_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('stake', 'Game Stake'),
        ('win', 'Game Win'),
        ('cashout', 'Cashout'),
        ('pause_fee', 'Pause Fee'),
        ('referral_bonus', 'Referral Bonus'),
        ('ad_bonus', 'Ad Bonus'),
        ('admin_credit', 'Admin Credit'),
        ('admin_debit', 'Admin Debit'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    tx_type = models.CharField(max_length=20, choices=TX_TYPES, db_index=True)
    reference = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='completed')
    balance_before = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'tx_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.tx_type} - {self.amount} ({self.status})'
