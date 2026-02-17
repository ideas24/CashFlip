from django.contrib import admin
from analytics.models import DailyStats


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    list_display = ['date', 'active_players', 'total_sessions', 'total_deposits', 'total_withdrawals', 'house_revenue', 'actual_house_edge']
    list_filter = ['date']
    readonly_fields = ['created_at', 'updated_at']
