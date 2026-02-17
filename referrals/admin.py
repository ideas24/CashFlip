from django.contrib import admin
from referrals.models import ReferralConfig, ReferralCode, Referral


@admin.register(ReferralConfig)
class ReferralConfigAdmin(admin.ModelAdmin):
    list_display = ['is_active', 'is_paused', 'referrer_bonus', 'referee_bonus', 'bonus_type', 'max_referrals_per_user']

    def has_add_permission(self, request):
        return not ReferralConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    list_display = ['player', 'code', 'total_referrals', 'total_earned', 'is_active']
    search_fields = ['player__phone', 'code']


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ['referrer', 'referee', 'referral_code', 'status', 'referrer_bonus_paid', 'referee_bonus_paid', 'created_at']
    list_filter = ['status']
    search_fields = ['referrer__phone', 'referee__phone', 'referral_code']
