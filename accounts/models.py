import uuid
import random
import string

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class PlayerManager(BaseUserManager):
    def create_user(self, phone=None, email=None, password=None, **extra_fields):
        if not phone and not email:
            raise ValueError('Player must have a phone number or email')
        if email:
            email = self.normalize_email(email)
        user = self.model(phone=phone, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        return self.create_user(phone=phone, email=email, password=password, **extra_fields)


class Player(AbstractBaseUser, PermissionsMixin):
    AUTH_PROVIDERS = [
        ('phone', 'Phone OTP'),
        ('google', 'Google'),
        ('facebook', 'Facebook'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    display_name = models.CharField(max_length=50, blank=True, default='')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    country = models.CharField(max_length=3, default='GH')
    default_currency = models.ForeignKey(
        'game.Currency', on_delete=models.SET_NULL, null=True, blank=True, related_name='players'
    )
    is_verified = models.BooleanField(default=False)
    auth_provider = models.CharField(max_length=20, choices=AUTH_PROVIDERS, default='phone')
    social_id = models.CharField(max_length=255, blank=True, default='')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = PlayerManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'Player'
        verbose_name_plural = 'Players'

    def __str__(self):
        return self.display_name or self.phone or self.email or str(self.id)[:8]

    def get_display_name(self):
        if self.display_name:
            return self.display_name
        if self.phone:
            return f'Player-{self.phone[-4:]}'
        return f'Player-{str(self.id)[:6]}'


class OTPToken(models.Model):
    CHANNELS = [
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE, null=True, blank=True, related_name='otps')
    phone = models.CharField(max_length=20, db_index=True)
    code = models.CharField(max_length=6)
    channel = models.CharField(max_length=10, choices=CHANNELS, default='sms')
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone', 'code', 'is_used']),
        ]

    def __str__(self):
        return f'OTP for {self.phone} via {self.channel}'

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired

    @classmethod
    def generate_code(cls):
        return ''.join(random.choices(string.digits, k=6))


class PlayerProfile(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name='profile')
    total_games = models.PositiveIntegerField(default=0)
    total_won = models.PositiveIntegerField(default=0)
    total_lost = models.PositiveIntegerField(default=0)
    highest_cashout = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    best_streak = models.PositiveIntegerField(default=0)
    current_level = models.PositiveIntegerField(default=1)
    total_deposited = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    lifetime_flips = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Profile: {self.player}'


class AdminRole(models.Model):
    PERMISSION_CHOICES = [
        ('view_analytics', 'View Analytics'),
        ('view_financials', 'View Financials'),
        ('manage_players', 'Manage Players'),
        ('manage_game_config', 'Manage Game Config'),
        ('manage_ads', 'Manage Ads'),
        ('manage_referrals', 'Manage Referrals'),
        ('manage_currencies', 'Manage Currencies'),
        ('manage_staff', 'Manage Staff'),
        ('super_admin', 'Super Admin'),
    ]

    name = models.CharField(max_length=50, unique=True)
    codename = models.CharField(max_length=50, unique=True)
    permissions = models.JSONField(default=list, help_text='List of permission codenames')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def has_permission(self, perm):
        if 'super_admin' in self.permissions:
            return True
        return perm in self.permissions


class StaffMember(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name='staff_profile')
    role = models.ForeignKey(AdminRole, on_delete=models.PROTECT, related_name='members')
    created_by = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, related_name='created_staff'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.player} - {self.role.name}'

    def has_permission(self, perm):
        if not self.is_active:
            return False
        return self.role.has_permission(perm)


class AuditLog(models.Model):
    staff = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100, blank=True, default='')
    object_id = models.CharField(max_length=100, blank=True, default='')
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.staff} - {self.action} at {self.created_at}'
