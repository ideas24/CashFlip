from django.db import models


class DailyStats(models.Model):
    date = models.DateField(unique=True, db_index=True)
    total_players = models.PositiveIntegerField(default=0)
    new_players = models.PositiveIntegerField(default=0)
    active_players = models.PositiveIntegerField(default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    total_flips = models.PositiveIntegerField(default=0)
    total_deposits = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_withdrawals = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_stakes = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_payouts = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    house_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    actual_house_edge = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_referral_bonuses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ad_impressions = models.PositiveIntegerField(default=0)
    ad_clicks = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Daily Statistics'
        verbose_name_plural = 'Daily Statistics'
        ordering = ['-date']

    def __str__(self):
        return f'Stats: {self.date}'
