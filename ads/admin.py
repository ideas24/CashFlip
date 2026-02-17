from django.contrib import admin
from ads.models import AdConfig, AdCampaign, AdCreative, AdImpression


@admin.register(AdConfig)
class AdConfigAdmin(admin.ModelAdmin):
    list_display = ['ads_enabled', 'show_every_n_flips', 'max_ads_per_session', 'skip_after_seconds', 'non_blocking']

    def has_add_permission(self, request):
        return not AdConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class CreativeInline(admin.TabularInline):
    model = AdCreative
    extra = 1


@admin.register(AdCampaign)
class AdCampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'advertiser', 'start_date', 'end_date', 'budget', 'spent', 'is_active', 'priority']
    list_filter = ['is_active']
    inlines = [CreativeInline]


@admin.register(AdCreative)
class AdCreativeAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'media_type', 'display_position', 'duration_seconds', 'is_active']
    list_filter = ['media_type', 'display_position', 'is_active']


@admin.register(AdImpression)
class AdImpressionAdmin(admin.ModelAdmin):
    list_display = ['creative', 'player', 'shown_at', 'clicked']
    list_filter = ['clicked']
    readonly_fields = ['shown_at', 'clicked_at']
