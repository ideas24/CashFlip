from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from referrals.models import ReferralCode, Referral, ReferralConfig


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def referral_stats(request):
    """Return player's referral code, link, stats, and config bonuses."""
    try:
        ref_code_obj = request.user.referral_code
    except ReferralCode.DoesNotExist:
        ref_code_obj = ReferralCode.objects.create(
            player=request.user,
            code=ReferralCode.generate_unique_code(),
        )

    config = ReferralConfig.get_config()
    referrals = Referral.objects.filter(referrer=request.user)
    pending = referrals.filter(status='pending').count()
    qualified = referrals.filter(status__in=['qualified', 'paid']).count()

    return Response({
        'code': ref_code_obj.code,
        'total_referrals': ref_code_obj.total_referrals,
        'total_earned': str(ref_code_obj.total_earned),
        'pending_referrals': pending,
        'qualified_referrals': qualified,
        'referrer_bonus': str(config.referrer_bonus),
        'referee_bonus': str(config.referee_bonus),
        'is_enabled': config.is_enabled,
    })
