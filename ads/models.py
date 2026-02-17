import uuid

from django.conf import settings
from django.db import models


class AdConfig(models.Model):
    ads_enabled = models.BooleanField(default=False)
    show_every_n_flips = models.PositiveIntegerField(default=5,
                                                      help_text='Show ad every N flips')
    max_ads_per_session = models.PositiveIntegerField(default=3)
    skip_after_seconds = models.PositiveIntegerField(default=5,
                                                      help_text='Allow skipping ad after this many seconds')
    non_blocking = models.BooleanField(default=True,
                                        help_text='If True, ads appear as overlay without pausing gameplay')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ad Configuration'
        verbose_name_plural = 'Ad Configuration'

    def __str__(self):
        return f'Ad Config ({"enabled" if self.ads_enabled else "disabled"})'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AdCampaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    advertiser = models.CharField(max_length=200, blank=True, default='')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=0, help_text='Higher = shown first')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-priority', '-created_at']

    def __str__(self):
        return self.name


class AdCreative(models.Model):
    MEDIA_TYPES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('html', 'HTML'),
    ]

    POSITIONS = [
        ('between_flips', 'Between Flips'),
        ('sidebar', 'Sidebar'),
        ('overlay', 'Overlay'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(AdCampaign, on_delete=models.CASCADE, related_name='creatives')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default='image')
    media_file = models.FileField(upload_to='ads/')
    click_url = models.URLField(blank=True, default='')
    duration_seconds = models.PositiveIntegerField(default=5)
    display_position = models.CharField(max_length=20, choices=POSITIONS, default='between_flips')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.campaign.name} - {self.media_type}'


class AdImpression(models.Model):
    creative = models.ForeignKey(AdCreative, on_delete=models.CASCADE, related_name='impressions')
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ad_impressions')
    session = models.ForeignKey('game.GameSession', on_delete=models.SET_NULL, null=True, blank=True)
    shown_at = models.DateTimeField(auto_now_add=True)
    clicked = models.BooleanField(default=False)
    clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-shown_at']

    def __str__(self):
        return f'Impression: {self.creative} - {"clicked" if self.clicked else "viewed"}'
