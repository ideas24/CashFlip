import uuid
import random
import string

from django.conf import settings
from django.db import models


class ReferralConfig(models.Model):
    BONUS_TYPES = [
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage of First Deposit'),
    ]

    is_active = models.BooleanField(default=True)
    is_paused = models.BooleanField(default=False)
    referrer_bonus = models.DecimalField(max_digits=10, decimal_places=2, default=1.00,
                                          help_text='Bonus for the referrer')
    referee_bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0.50,
                                         help_text='Bonus for the new player')
    min_deposit_to_qualify = models.DecimalField(max_digits=10, decimal_places=2, default=1.00,
                                                  help_text='Min deposit for referral to qualify')
    max_referrals_per_user = models.PositiveIntegerField(default=100)
    bonus_type = models.CharField(max_length=15, choices=BONUS_TYPES, default='fixed')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Referral Configuration'
        verbose_name_plural = 'Referral Configuration'

    def __str__(self):
        status = 'paused' if self.is_paused else ('active' if self.is_active else 'disabled')
        return f'Referral Config ({status})'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def is_enabled(self):
        return self.is_active and not self.is_paused


class ReferralCode(models.Model):
    player = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referral_code')
    code = models.CharField(max_length=10, unique=True, db_index=True)
    total_referrals = models.PositiveIntegerField(default=0)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.player} - {self.code}'

    @property
    def share_url(self):
        from django.conf import settings
        return f'{settings.SITE_URL}/?ref={self.code}'

    @classmethod
    def generate_unique_code(cls):
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not cls.objects.filter(code=code).exists():
                return code


class Referral(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('qualified', 'Qualified'),
        ('paid', 'Paid'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referrals_made')
    referee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referred_by_record')
    referral_code = models.CharField(max_length=10)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True)
    referrer_bonus_paid = models.BooleanField(default=False)
    referee_bonus_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    qualified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['referrer', 'referee']

    def __str__(self):
        return f'{self.referrer} → {self.referee} ({self.status})'
