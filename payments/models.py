import uuid

from django.conf import settings
from django.db import models


class MobileMoneyAccount(models.Model):
    """
    Verified mobile money payment method.
    The verified_name from Orchard AII is the source of truth.
    Same momo name used for deposit MUST be the payout account.
    """
    NETWORK_CHOICES = [
        ('MTN', 'MTN'),
        ('VOD', 'Telecel (Vodafone)'),
        ('AIR', 'AirtelTigo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='momo_accounts')
    mobile_number = models.CharField(max_length=20, db_index=True)
    network = models.CharField(max_length=5, choices=NETWORK_CHOICES)
    verified_name = models.CharField(max_length=200, help_text='Name returned by Orchard AII verification')
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    verified_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', '-created_at']
        unique_together = ['player', 'mobile_number']
        indexes = [
            models.Index(fields=['player', 'is_active']),
        ]

    def __str__(self):
        return f'{self.verified_name} - {self.mobile_number} ({self.network})'

    def save(self, *args, **kwargs):
        # If this is the first account or marked primary, ensure only one primary
        if self.is_primary:
            MobileMoneyAccount.objects.filter(
                player=self.player, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        # If no primary exists, make this one primary
        if not MobileMoneyAccount.objects.filter(player=self.player, is_primary=True).exclude(pk=self.pk).exists():
            self.is_primary = True
        super().save(*args, **kwargs)


class Deposit(models.Model):
    METHOD_CHOICES = [
        ('mobile_money', 'Mobile Money'),
        ('card', 'Card'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deposits')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency_code = models.CharField(max_length=5, default='GHS')
    method = models.CharField(max_length=15, choices=METHOD_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True)
    orchard_reference = models.CharField(max_length=50, blank=True, default='', db_index=True)
    paystack_reference = models.CharField(max_length=50, blank=True, default='', db_index=True)
    paystack_authorization_url = models.URLField(blank=True, default='')
    mobile_number = models.CharField(max_length=20, blank=True, default='')
    network = models.CharField(max_length=5, blank=True, default='')
    failure_reason = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    orchard_response = models.JSONField(default=dict, blank=True)
    paystack_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['player', 'status']),
        ]

    def __str__(self):
        return f'Deposit {self.amount} {self.currency_code} - {self.status}'


class Withdrawal(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency_code = models.CharField(max_length=5, default='GHS')
    mobile_number = models.CharField(max_length=20)
    network = models.CharField(max_length=5)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True)
    payout_reference = models.CharField(max_length=100, blank=True, default='', db_index=True)
    payout_ext_trid = models.CharField(max_length=100, blank=True, default='')
    failure_reason = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    orchard_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Withdrawal {self.amount} {self.currency_code} to {self.mobile_number} - {self.status}'
