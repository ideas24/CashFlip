import secrets
import string
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_voucher_code(length=10):
    """Generate a unique alphanumeric voucher code like CF-XXXX-XXXX."""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(secrets.choice(chars) for _ in range(4))
    part2 = ''.join(secrets.choice(chars) for _ in range(4))
    return f'CF-{part1}-{part2}'


class VoucherBatch(models.Model):
    """A batch of vouchers created at once with the same denomination."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text='Batch label, e.g. "Launch Promo 5 GHS"')
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='Credit amount per voucher')
    currency_code = models.CharField(max_length=5, default='GHS')
    quantity = models.PositiveIntegerField(help_text='Number of vouchers in batch')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_voucher_batches'
    )
    expires_at = models.DateTimeField(null=True, blank=True, help_text='Optional expiry for all vouchers in batch')
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'voucher batches'

    def __str__(self):
        return f'{self.name} ({self.quantity}× {self.currency_code}{self.amount})'

    @property
    def redeemed_count(self):
        return self.vouchers.filter(status='redeemed').count()

    @property
    def active_count(self):
        return self.vouchers.filter(status='active').count()


class Voucher(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('redeemed', 'Redeemed'),
        ('expired', 'Expired'),
        ('disabled', 'Disabled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='Credit amount when redeemed')
    currency_code = models.CharField(max_length=5, default='GHS')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', db_index=True)
    batch = models.ForeignKey(VoucherBatch, on_delete=models.CASCADE, null=True, blank=True, related_name='vouchers')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_vouchers'
    )
    redeemed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='redeemed_vouchers'
    )
    redeemed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'code']),
        ]

    def __str__(self):
        return f'{self.code} - {self.currency_code}{self.amount} ({self.status})'

    @property
    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    @property
    def is_redeemable(self):
        if self.status != 'active':
            return False
        if self.is_expired:
            return False
        return True

    def save(self, *args, **kwargs):
        if not self.code:
            # Generate unique code
            for _ in range(10):
                code = generate_voucher_code()
                if not Voucher.objects.filter(code=code).exists():
                    self.code = code
                    break
        super().save(*args, **kwargs)
