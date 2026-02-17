"""
Accounts API Views - OTP Auth, Profile, Token Refresh
"""

import logging
import random

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from accounts.authentication import generate_access_token, generate_refresh_token, verify_refresh_token
from accounts.models import Player, PlayerProfile, AuthConfig
from accounts.otp_service import send_otp, verify_otp, normalize_phone
from accounts.serializers import (
    RequestOTPSerializer, VerifyOTPSerializer, RefreshTokenSerializer,
    PlayerSerializer, PlayerUpdateSerializer,
)

logger = logging.getLogger(__name__)

_ADJECTIVES = [
    'Lucky', 'Swift', 'Bold', 'Mighty', 'Clever', 'Brave', 'Fierce', 'Sharp',
    'Cool', 'Slick', 'Quick', 'Bright', 'Grand', 'Epic', 'Noble', 'Wise',
    'Flash', 'Turbo', 'Rapid', 'Gold', 'Silver', 'Iron', 'Steel', 'Storm',
    'Blaze', 'Frost', 'Thunder', 'Shadow', 'Cosmic', 'Royal', 'Ultra', 'Mega',
]
_NOUNS = [
    'Flipper', 'Stacker', 'Roller', 'Winner', 'Player', 'Ace', 'Star', 'King',
    'Queen', 'Champ', 'Boss', 'Chief', 'Legend', 'Hero', 'Ninja', 'Tiger',
    'Eagle', 'Hawk', 'Lion', 'Wolf', 'Fox', 'Bear', 'Shark', 'Cobra',
    'Phoenix', 'Dragon', 'Falcon', 'Panther', 'Viper', 'Jaguar', 'Titan', 'Bolt',
]

def _generate_username():
    """Generate a fun unique username like 'LuckyFlipper42'."""
    for _ in range(10):
        name = random.choice(_ADJECTIVES) + random.choice(_NOUNS) + str(random.randint(10, 99))
        if not Player.objects.filter(display_name=name).exists():
            return name
    return f'Player{random.randint(1000, 9999)}'


class OTPThrottle(AnonRateThrottle):
    rate = '3/minute'


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([OTPThrottle])
def request_otp(request):
    """Send OTP to phone number (generic — channel via request body)."""
    serializer = RequestOTPSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    phone = serializer.validated_data['phone']
    channel = serializer.validated_data['channel']
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))

    # Enforce auth config toggle
    auth_cfg = AuthConfig.get_config()
    if channel == 'sms' and not auth_cfg.sms_otp_enabled:
        msg = auth_cfg.maintenance_message or 'SMS login is currently disabled.'
        return Response({'error': msg}, status=status.HTTP_403_FORBIDDEN)
    if channel == 'whatsapp' and not auth_cfg.whatsapp_otp_enabled:
        msg = auth_cfg.maintenance_message or 'WhatsApp login is currently disabled.'
        return Response({'error': msg}, status=status.HTTP_403_FORBIDDEN)

    result = send_otp(phone, channel=channel, ip_address=ip)
    
    if result['success']:
        return Response({'message': result['message'], 'channel': channel}, status=status.HTTP_200_OK)
    return Response({'error': result['message']}, status=status.HTTP_429_TOO_MANY_REQUESTS)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([OTPThrottle])
def request_sms_otp(request):
    """
    Request OTP via SMS.
    Dedicated endpoint for the SMS login button.
    Body: {"phone": "0241234567"}
    """
    # Enforce auth config toggle
    auth_cfg = AuthConfig.get_config()
    if not auth_cfg.sms_otp_enabled:
        msg = auth_cfg.maintenance_message or 'SMS login is currently disabled.'
        return Response({'error': msg}, status=status.HTTP_403_FORBIDDEN)

    from accounts.serializers import PhoneOnlySerializer
    serializer = PhoneOnlySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    phone = serializer.validated_data['phone']
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))

    result = send_otp(phone, channel='sms', ip_address=ip)

    if result['success']:
        return Response({'message': result['message'], 'channel': 'sms'}, status=status.HTTP_200_OK)
    return Response({'error': result['message']}, status=status.HTTP_429_TOO_MANY_REQUESTS)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([OTPThrottle])
def request_whatsapp_otp(request):
    """
    Request OTP via WhatsApp Authentication template (copy-code button).
    Dedicated endpoint for the WhatsApp login button.
    Body: {"phone": "0241234567"}
    """
    # Enforce auth config toggle
    auth_cfg = AuthConfig.get_config()
    if not auth_cfg.whatsapp_otp_enabled:
        msg = auth_cfg.maintenance_message or 'WhatsApp login is currently disabled.'
        return Response({'error': msg}, status=status.HTTP_403_FORBIDDEN)

    from accounts.serializers import PhoneOnlySerializer
    serializer = PhoneOnlySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    phone = serializer.validated_data['phone']
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))

    result = send_otp(phone, channel='whatsapp', ip_address=ip)

    if result['success']:
        return Response({'message': result['message'], 'channel': 'whatsapp'}, status=status.HTTP_200_OK)
    return Response({'error': result['message']}, status=status.HTTP_429_TOO_MANY_REQUESTS)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp_view(request):
    """Verify OTP and return JWT tokens. Auto-creates player on first login."""
    serializer = VerifyOTPSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    phone = serializer.validated_data['phone']
    code = serializer.validated_data['code']

    # Normalize phone to canonical +233... format
    phone = normalize_phone(phone)

    result = verify_otp(phone, code)
    
    if not result['success']:
        return Response({'error': result['message']}, status=status.HTTP_400_BAD_REQUEST)

    # Get or create player
    player, created = Player.objects.get_or_create(
        phone=phone,
        defaults={'is_verified': True, 'auth_provider': 'phone'}
    )

    if not player.is_verified:
        player.is_verified = True
        player.save(update_fields=['is_verified'])

    # Auto-generate display name for new players
    if created and not player.display_name:
        player.display_name = _generate_username()
        player.save(update_fields=['display_name'])

    # Ensure profile exists
    PlayerProfile.objects.get_or_create(player=player)

    # Ensure referral code exists
    from referrals.models import ReferralCode
    if not hasattr(player, 'referral_code'):
        ReferralCode.objects.create(
            player=player,
            code=ReferralCode.generate_unique_code()
        )

    # Ensure wallet exists
    from wallet.models import Wallet
    from game.models import Currency
    if not hasattr(player, 'wallet'):
        default_currency = Currency.objects.filter(is_default=True).first()
        if default_currency:
            Wallet.objects.create(player=player, currency=default_currency)

    # Handle referral if provided
    ref_code = request.data.get('ref_code')
    if created and ref_code:
        _process_referral(player, ref_code)

    # Generate tokens
    access_token = generate_access_token(player)
    refresh_token = generate_refresh_token(player)

    return Response({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'is_new': created,
        'player': PlayerSerializer(player).data,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_view(request):
    """Refresh JWT access token."""
    serializer = RefreshTokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    payload = verify_refresh_token(serializer.validated_data['refresh_token'])
    
    try:
        player = Player.objects.get(id=payload['user_id'], is_active=True)
    except Player.DoesNotExist:
        return Response({'error': 'Player not found'}, status=status.HTTP_404_NOT_FOUND)

    access_token = generate_access_token(player)
    return Response({'access_token': access_token})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def player_profile(request):
    """Get current player profile."""
    PlayerProfile.objects.get_or_create(player=request.user)
    return Response(PlayerSerializer(request.user).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update player profile."""
    serializer = PlayerUpdateSerializer(request.user, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(PlayerSerializer(request.user).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def auth_methods(request):
    """Public endpoint — frontend fetches this to know which login buttons to show."""
    cfg = AuthConfig.get_config()
    return Response({
        'sms_otp': cfg.sms_otp_enabled,
        'whatsapp_otp': cfg.whatsapp_otp_enabled,
        'google': cfg.google_enabled,
        'facebook': cfg.facebook_enabled,
    })


def _process_referral(new_player, ref_code):
    """Process referral for new player."""
    try:
        from referrals.models import ReferralConfig, ReferralCode, Referral
        config = ReferralConfig.get_config()
        if not config.is_enabled:
            return
        
        ref = ReferralCode.objects.filter(code=ref_code, is_active=True).first()
        if not ref or ref.player == new_player:
            return
        
        if ref.total_referrals >= config.max_referrals_per_user:
            return
        
        Referral.objects.create(
            referrer=ref.player,
            referee=new_player,
            referral_code=ref_code,
            status='pending',
        )
        logger.info(f'Referral created: {ref.player} referred {new_player}')
    except Exception as e:
        logger.error(f'Error processing referral: {e}')
