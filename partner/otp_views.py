"""
OTPaaS API Views — WhatsApp/SMS OTP as a Service.

All endpoints use OTPClientAuthentication (HMAC).
request.user = OTPClient instance, request.auth = OTPClientAPIKey instance.
"""

import hashlib
import logging
import random
import string
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, inline_serializer
from rest_framework import serializers as drf_serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from partner.otp_auth import OTPClientAuthentication
from partner.models import (
    OTPClient, OTPClientAPIKey, OTPSenderID, OTPRequest,
    OTPClientUsage, OTPPricingTier,
)

logger = logging.getLogger(__name__)

OTP_AUTH = [OTPClientAuthentication]
OTP_PERMS = [AllowAny]  # Auth handled by HMAC


def _get_client(request):
    if not isinstance(request.user, OTPClient):
        return None
    return request.user


def _normalize_phone(phone):
    """Normalize phone to E.164 format."""
    cleaned = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if cleaned.startswith('+'):
        return cleaned
    if cleaned.startswith('0') and len(cleaned) == 10:
        return '+233' + cleaned[1:]
    if cleaned.startswith('233'):
        return '+' + cleaned
    return '+' + cleaned


def _generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))


def _get_otp_cost(client, channel):
    """Get per-OTP cost based on client's pricing tier."""
    tier = client.pricing_tier
    if channel == 'whatsapp':
        return tier.price_per_otp_whatsapp
    return tier.price_per_otp_sms


def _check_phone_rate_limit(client, phone):
    """Check per-phone rate limit."""
    rate_key = f'otp_phone_rate:{client.id}:{phone}'
    current = cache.get(rate_key, 0)
    if current >= client.rate_limit_per_phone_per_hour:
        return False
    cache.set(rate_key, current + 1, timeout=3600)
    return True


def _check_daily_limit(client):
    """Check daily OTP limit."""
    if client.daily_limit == 0:
        return True  # unlimited
    today = timezone.now().date()
    count = OTPRequest.objects.filter(
        client=client,
        created_at__date=today,
    ).count()
    return count < client.daily_limit


def _send_whatsapp_otp(phone, code, sender_id=None):
    """Send OTP via WhatsApp. Uses client's sender ID if whitelabel, else Cashflip default."""
    from django.conf import settings as django_settings
    import requests

    if sender_id and sender_id.is_active and sender_id.whatsapp_phone_number_id:
        access_token = sender_id.whatsapp_access_token
        phone_number_id = sender_id.whatsapp_phone_number_id
        template_name = sender_id.whatsapp_template_name or 'cashflip_auth_otp'
    else:
        access_token = django_settings.WHATSAPP_ACCESS_TOKEN
        phone_number_id = django_settings.WHATSAPP_PHONE_NUMBER_ID
        template_name = getattr(django_settings, 'WHATSAPP_AUTH_TEMPLATE_NAME', 'cashflip_auth_otp')

    if not access_token or not phone_number_id:
        return False, 'WhatsApp credentials not configured', ''

    normalized = phone.replace('+', '').replace(' ', '')
    if normalized.startswith('0'):
        normalized = '233' + normalized[1:]

    url = f"https://graph.facebook.com/v23.0/{phone_number_id}/messages"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': normalized,
        'type': 'template',
        'template': {
            'name': template_name,
            'language': {'code': 'en'},
            'components': [
                {
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': code}]
                },
                {
                    'type': 'button',
                    'sub_type': 'copy_code',
                    'index': '0',
                    'parameters': [{'type': 'coupon_code', 'coupon_code': code}]
                }
            ]
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code in [200, 201]:
            data = response.json()
            msg_id = data.get('messages', [{}])[0].get('id', '')
            return True, '', msg_id
        else:
            return False, f'WhatsApp API error {response.status_code}: {response.text[:200]}', ''
    except Exception as e:
        return False, str(e), ''


def _send_sms_otp(phone, code, sender_id=None):
    """Send OTP via SMS. Uses client's sender config if whitelabel, else Cashflip default."""
    from django.conf import settings as django_settings

    if sender_id and sender_id.is_active and sender_id.sms_sender_id:
        provider = sender_id.sms_provider
        config = sender_id.sms_provider_config
    else:
        provider = 'twilio'
        config = {
            'account_sid': django_settings.TWILIO_ACCOUNT_SID,
            'auth_token': django_settings.TWILIO_AUTH_TOKEN,
            'from_number': django_settings.TWILIO_PHONE_NUMBER,
        }

    normalized = phone.replace(' ', '')
    if normalized.startswith('0'):
        normalized = '+233' + normalized[1:]
    elif not normalized.startswith('+'):
        normalized = '+' + normalized

    if provider == 'twilio':
        try:
            from twilio.rest import Client
            client = Client(config.get('account_sid', ''), config.get('auth_token', ''))
            message = client.messages.create(
                body=f'Your verification code is: {code}',
                from_=config.get('from_number', ''),
                to=normalized,
            )
            return True, '', message.sid
        except Exception as e:
            return False, str(e), ''
    elif provider == 'arkesel':
        import requests
        try:
            resp = requests.post('https://sms.arkesel.com/api/v2/sms/send', json={
                'sender': sender_id.sms_sender_id if sender_id else 'Cashflip',
                'message': f'Your verification code is: {code}',
                'recipients': [normalized],
            }, headers={'api-key': config.get('api_key', '')}, timeout=30)
            if resp.status_code in [200, 201]:
                return True, '', resp.json().get('data', {}).get('id', '')
            return False, f'Arkesel error: {resp.text[:200]}', ''
        except Exception as e:
            return False, str(e), ''
    elif provider == 'hubtel':
        import requests
        try:
            resp = requests.post(
                f"https://smsc.hubtel.com/v1/messages/send",
                json={
                    'From': sender_id.sms_sender_id if sender_id else 'Cashflip',
                    'To': normalized,
                    'Content': f'Your verification code is: {code}',
                },
                auth=(config.get('client_id', ''), config.get('client_secret', '')),
                timeout=30,
            )
            if resp.status_code in [200, 201]:
                return True, '', resp.json().get('MessageId', '')
            return False, f'Hubtel error: {resp.text[:200]}', ''
        except Exception as e:
            return False, str(e), ''

    return False, f'Unknown SMS provider: {provider}', ''


def _update_daily_usage(client, channel, delivered, cost):
    """Increment daily usage counters."""
    today = timezone.now().date()
    usage, _ = OTPClientUsage.objects.get_or_create(
        client=client, date=today,
    )
    if channel == 'whatsapp':
        usage.whatsapp_sent = F('whatsapp_sent') + 1
        if delivered:
            usage.whatsapp_delivered = F('whatsapp_delivered') + 1
        else:
            usage.whatsapp_failed = F('whatsapp_failed') + 1
        usage.whatsapp_cost = F('whatsapp_cost') + cost
    else:
        usage.sms_sent = F('sms_sent') + 1
        if delivered:
            usage.sms_delivered = F('sms_delivered') + 1
        else:
            usage.sms_failed = F('sms_failed') + 1
        usage.sms_cost = F('sms_cost') + cost
    usage.total_cost = F('total_cost') + cost
    usage.save()


# ==================== API ENDPOINTS ====================


@extend_schema(
    tags=['OTPaaS: Send & Verify'],
    summary='Send OTP',
    description=(
        'Send a one-time password to a phone number via WhatsApp or SMS.\n\n'
        '**Flow**: Generate code → deliver via channel → return OTP ID for verification.\n\n'
        '**Rate Limits**: Per-client per-minute limit + per-phone-per-hour limit apply.\n\n'
        '**Billing**: Cost deducted from prepaid balance on successful delivery (prepaid mode).'
    ),
    request=inline_serializer('OTPSendRequest', fields={
        'phone': drf_serializers.CharField(help_text='Phone number in E.164 format, e.g. +233241234567'),
        'channel': drf_serializers.ChoiceField(choices=['whatsapp', 'sms'], required=False, help_text='Delivery channel (defaults to client config)'),
        'client_ref': drf_serializers.CharField(required=False, help_text='Your reference ID for tracking'),
        'metadata': drf_serializers.DictField(required=False, help_text='Freeform JSON metadata'),
    }),
    responses={
        201: inline_serializer('OTPSendResponse', fields={
            'otp_id': drf_serializers.UUIDField(),
            'phone': drf_serializers.CharField(),
            'channel': drf_serializers.CharField(),
            'status': drf_serializers.CharField(),
            'expires_at': drf_serializers.DateTimeField(),
            'expires_in_seconds': drf_serializers.IntegerField(),
            'client_ref': drf_serializers.CharField(),
        }),
        400: OpenApiResponse(description='Missing or invalid parameters'),
        402: OpenApiResponse(description='Insufficient prepaid balance'),
        429: OpenApiResponse(description='Rate limit exceeded'),
        502: OpenApiResponse(description='OTP delivery failed'),
    },
    examples=[
        OpenApiExample('WhatsApp OTP', value={'phone': '+233241234567', 'channel': 'whatsapp', 'client_ref': 'login-sess-001'}, request_only=True),
        OpenApiExample('SMS OTP', value={'phone': '+233201234567', 'channel': 'sms'}, request_only=True),
        OpenApiExample('Success', value={'otp_id': 'a1b2c3d4-...', 'phone': '+233241234567', 'channel': 'whatsapp', 'status': 'sent', 'expires_at': '2026-02-18T00:05:00Z', 'expires_in_seconds': 300, 'client_ref': 'login-sess-001'}, response_only=True),
    ],
)
@api_view(['POST'])
@authentication_classes(OTP_AUTH)
@permission_classes(OTP_PERMS)
def otp_send(request):
    """Send an OTP to a phone number via WhatsApp or SMS."""
    client = _get_client(request)
    if not client:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    phone = request.data.get('phone', '').strip()
    if not phone:
        return Response({'error': 'phone is required'}, status=status.HTTP_400_BAD_REQUEST)

    phone = _normalize_phone(phone)
    channel = request.data.get('channel', client.default_channel)
    client_ref = request.data.get('client_ref', '')
    metadata = request.data.get('metadata', {})

    # Validate channel
    allowed = client.allowed_channels or ['whatsapp', 'sms']
    if channel not in allowed:
        return Response({
            'error': f'Channel "{channel}" not allowed. Allowed: {allowed}'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Per-phone rate limit
    if not _check_phone_rate_limit(client, phone):
        return Response({
            'error': 'Too many OTPs to this phone number. Try again later.',
            'retry_after_seconds': 3600,
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Daily limit
    if not _check_daily_limit(client):
        return Response({
            'error': 'Daily OTP limit reached for your account.',
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Billing check
    cost = _get_otp_cost(client, channel)
    if client.billing_mode == 'prepaid' and client.prepaid_balance < cost:
        if client.auto_suspend_on_zero:
            client.status = 'suspended'
            client.save(update_fields=['status'])
        return Response({
            'error': 'Insufficient prepaid balance. Please top up.',
            'balance': str(client.prepaid_balance),
            'cost': str(cost),
        }, status=status.HTTP_402_PAYMENT_REQUIRED)

    # Invalidate previous pending OTPs for this phone + client
    OTPRequest.objects.filter(
        client=client, phone=phone,
        status__in=('pending', 'sent', 'delivered'),
    ).update(status='expired')

    # Generate OTP
    code = _generate_code(client.otp_length)
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    expires_at = timezone.now() + timedelta(seconds=client.otp_expiry_seconds)

    # Check for whitelabel sender
    sender_id = OTPSenderID.objects.filter(
        client=client, channel=channel, is_active=True, status='verified'
    ).first()

    # Create OTP request record
    otp_req = OTPRequest.objects.create(
        client=client,
        api_key=request.auth if isinstance(request.auth, OTPClientAPIKey) else None,
        sender_id=sender_id,
        phone=phone,
        channel=channel,
        code=code,
        code_hash=code_hash,
        status='pending',
        expires_at=expires_at,
        cost=cost,
        client_ref=client_ref,
        ip_address=request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata=metadata,
        max_verify_attempts=3,
    )

    # Send OTP
    if channel == 'whatsapp':
        success, error, msg_id = _send_whatsapp_otp(phone, code, sender_id)
    else:
        success, error, msg_id = _send_sms_otp(phone, code, sender_id)

    if success:
        otp_req.status = 'sent'
        otp_req.provider_message_id = msg_id
        otp_req.delivery_attempts = 1
        otp_req.billed = True
        otp_req.save(update_fields=['status', 'provider_message_id', 'delivery_attempts', 'billed'])

        # Deduct prepaid balance
        if client.billing_mode == 'prepaid':
            OTPClient.objects.filter(pk=client.pk).update(
                prepaid_balance=F('prepaid_balance') - cost
            )

        _update_daily_usage(client, channel, True, cost)

        return Response({
            'otp_id': str(otp_req.id),
            'phone': phone,
            'channel': channel,
            'status': 'sent',
            'expires_at': otp_req.expires_at.isoformat(),
            'expires_in_seconds': client.otp_expiry_seconds,
            'client_ref': client_ref,
        }, status=status.HTTP_201_CREATED)
    else:
        otp_req.status = 'failed'
        otp_req.error_message = error
        otp_req.delivery_attempts = 1
        otp_req.save(update_fields=['status', 'error_message', 'delivery_attempts'])
        _update_daily_usage(client, channel, False, Decimal('0'))

        return Response({
            'otp_id': str(otp_req.id),
            'phone': phone,
            'channel': channel,
            'status': 'failed',
            'error': 'Failed to deliver OTP. Try another channel.',
        }, status=status.HTTP_502_BAD_GATEWAY)


@extend_schema(
    tags=['OTPaaS: Send & Verify'],
    summary='Verify OTP',
    description=(
        'Verify an OTP code submitted by the end user.\n\n'
        '**Max attempts**: 3 per OTP (configurable). After exceeding, the OTP is rejected.\n\n'
        '**Expiry**: OTPs expire after the configured TTL (default 5 minutes).'
    ),
    request=inline_serializer('OTPVerifyRequest', fields={
        'phone': drf_serializers.CharField(help_text='Phone number used when sending the OTP'),
        'code': drf_serializers.CharField(help_text='6-digit OTP code entered by user'),
        'otp_id': drf_serializers.UUIDField(required=False, help_text='Specific OTP ID for precision matching'),
    }),
    responses={
        200: inline_serializer('OTPVerifyResponse', fields={
            'verified': drf_serializers.BooleanField(),
            'otp_id': drf_serializers.UUIDField(),
            'phone': drf_serializers.CharField(),
            'client_ref': drf_serializers.CharField(),
        }),
        400: OpenApiResponse(description='Invalid OTP code'),
        404: OpenApiResponse(description='No valid OTP found (expired or not sent)'),
        429: OpenApiResponse(description='Max verification attempts exceeded'),
    },
    examples=[
        OpenApiExample('Verify', value={'phone': '+233241234567', 'code': '482916'}, request_only=True),
        OpenApiExample('Success', value={'verified': True, 'otp_id': 'a1b2c3d4-...', 'phone': '+233241234567', 'client_ref': 'login-sess-001'}, response_only=True),
        OpenApiExample('Failed', value={'verified': False, 'error': 'Invalid OTP code.', 'attempts_remaining': 2}, response_only=True, status_codes=['400']),
    ],
)
@api_view(['POST'])
@authentication_classes(OTP_AUTH)
@permission_classes(OTP_PERMS)
def otp_verify(request):
    """Verify an OTP code."""
    client = _get_client(request)
    if not client:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    phone = _normalize_phone(request.data.get('phone', '').strip())
    code = request.data.get('code', '').strip()
    otp_id = request.data.get('otp_id', '').strip()

    if not phone or not code:
        return Response({'error': 'phone and code are required'}, status=status.HTTP_400_BAD_REQUEST)

    # Find the OTP
    qs = OTPRequest.objects.filter(
        client=client,
        phone=phone,
        status__in=('sent', 'delivered'),
        expires_at__gt=timezone.now(),
    )
    if otp_id:
        qs = qs.filter(id=otp_id)

    otp_req = qs.order_by('-created_at').first()

    if not otp_req:
        return Response({
            'verified': False,
            'error': 'No valid OTP found for this phone number. It may have expired.',
        }, status=status.HTTP_404_NOT_FOUND)

    # Check max attempts
    if otp_req.verify_attempts >= otp_req.max_verify_attempts:
        otp_req.status = 'rejected'
        otp_req.save(update_fields=['status'])
        return Response({
            'verified': False,
            'error': 'Maximum verification attempts exceeded. Request a new OTP.',
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Verify code
    if otp_req.code == code:
        otp_req.status = 'verified'
        otp_req.verified_at = timezone.now()
        otp_req.save(update_fields=['status', 'verified_at'])

        # Update usage stats
        today = timezone.now().date()
        OTPClientUsage.objects.filter(client=client, date=today).update(
            total_verified=F('total_verified') + 1
        )

        return Response({
            'verified': True,
            'otp_id': str(otp_req.id),
            'phone': phone,
            'client_ref': otp_req.client_ref,
        })
    else:
        otp_req.verify_attempts = F('verify_attempts') + 1
        otp_req.save(update_fields=['verify_attempts'])
        otp_req.refresh_from_db()

        remaining = otp_req.max_verify_attempts - otp_req.verify_attempts
        return Response({
            'verified': False,
            'error': 'Invalid OTP code.',
            'attempts_remaining': remaining,
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['OTPaaS: Status'],
    summary='Get OTP Status',
    description='Retrieve the current delivery and verification status of a specific OTP request by its ID.',
    responses={
        200: inline_serializer('OTPStatusResponse', fields={
            'otp_id': drf_serializers.UUIDField(),
            'phone': drf_serializers.CharField(),
            'channel': drf_serializers.CharField(),
            'status': drf_serializers.ChoiceField(choices=['pending', 'sent', 'delivered', 'failed', 'expired', 'verified', 'rejected']),
            'created_at': drf_serializers.DateTimeField(),
            'expires_at': drf_serializers.DateTimeField(),
            'verified_at': drf_serializers.DateTimeField(allow_null=True),
            'verify_attempts': drf_serializers.IntegerField(),
            'client_ref': drf_serializers.CharField(),
            'cost': drf_serializers.DecimalField(max_digits=8, decimal_places=4),
        }),
        404: OpenApiResponse(description='OTP request not found'),
    },
)
@api_view(['GET'])
@authentication_classes(OTP_AUTH)
@permission_classes(OTP_PERMS)
def otp_status(request, otp_id):
    """Check the status of a specific OTP request."""
    client = _get_client(request)
    if not client:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        otp_req = OTPRequest.objects.get(id=otp_id, client=client)
    except OTPRequest.DoesNotExist:
        return Response({'error': 'OTP request not found'}, status=status.HTTP_404_NOT_FOUND)

    # Check expiry
    if otp_req.status in ('sent', 'delivered') and otp_req.is_expired:
        otp_req.status = 'expired'
        otp_req.save(update_fields=['status'])

    return Response({
        'otp_id': str(otp_req.id),
        'phone': otp_req.phone,
        'channel': otp_req.channel,
        'status': otp_req.status,
        'created_at': otp_req.created_at.isoformat(),
        'expires_at': otp_req.expires_at.isoformat(),
        'verified_at': otp_req.verified_at.isoformat() if otp_req.verified_at else None,
        'verify_attempts': otp_req.verify_attempts,
        'client_ref': otp_req.client_ref,
        'cost': str(otp_req.cost),
    })


@extend_schema(
    tags=['OTPaaS: Billing & Usage'],
    summary='Get Balance & Usage',
    description='Retrieve your current prepaid balance, pricing tier details, today\'s usage, and month-to-date totals.',
)
@api_view(['GET'])
@authentication_classes(OTP_AUTH)
@permission_classes(OTP_PERMS)
def otp_balance(request):
    """Get client's current balance and usage summary."""
    client = _get_client(request)
    if not client:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    today = timezone.now().date()
    usage_today = OTPClientUsage.objects.filter(client=client, date=today).first()

    # Month-to-date
    month_start = today.replace(day=1)
    from django.db.models import Sum
    mtd = OTPClientUsage.objects.filter(
        client=client, date__gte=month_start,
    ).aggregate(
        wa_sent=Sum('whatsapp_sent'),
        sms_sent=Sum('sms_sent'),
        wa_cost=Sum('whatsapp_cost'),
        sms_cost=Sum('sms_cost'),
        total=Sum('total_cost'),
        verified=Sum('total_verified'),
    )

    tier = client.pricing_tier
    return Response({
        'client': client.company_name,
        'billing_mode': client.billing_mode,
        'prepaid_balance': str(client.prepaid_balance),
        'pricing_tier': {
            'name': tier.name,
            'whatsapp_per_otp': str(tier.price_per_otp_whatsapp),
            'sms_per_otp': str(tier.price_per_otp_sms),
            'monthly_base_fee': str(tier.monthly_base_fee),
            'whitelabel_available': tier.whitelabel_available,
            'whitelabel_fee': str(tier.whitelabel_fee_monthly),
        },
        'today': {
            'whatsapp_sent': usage_today.whatsapp_sent if usage_today else 0,
            'sms_sent': usage_today.sms_sent if usage_today else 0,
            'total_cost': str(usage_today.total_cost) if usage_today else '0.00',
            'verified': usage_today.total_verified if usage_today else 0,
        },
        'month_to_date': {
            'whatsapp_sent': mtd['wa_sent'] or 0,
            'sms_sent': mtd['sms_sent'] or 0,
            'whatsapp_cost': str(mtd['wa_cost'] or 0),
            'sms_cost': str(mtd['sms_cost'] or 0),
            'total_cost': str(mtd['total'] or 0),
            'total_verified': mtd['verified'] or 0,
        },
        'limits': {
            'rate_per_minute': client.rate_limit_per_minute,
            'per_phone_per_hour': client.rate_limit_per_phone_per_hour,
            'daily_limit': client.daily_limit,
        },
    })


@extend_schema(
    tags=['OTPaaS: Billing & Usage'],
    summary='Get Usage History',
    description='Retrieve daily aggregated usage data for the last N days (max 90). Includes per-channel volumes, delivery rates, and costs.',
)
@api_view(['GET'])
@authentication_classes(OTP_AUTH)
@permission_classes(OTP_PERMS)
def otp_usage(request):
    """Get daily usage history."""
    client = _get_client(request)
    if not client:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    days = min(int(request.query_params.get('days', 30)), 90)
    start = timezone.now().date() - timedelta(days=days - 1)

    usage = OTPClientUsage.objects.filter(
        client=client, date__gte=start,
    ).order_by('date')

    data = []
    for u in usage:
        data.append({
            'date': u.date.isoformat(),
            'whatsapp_sent': u.whatsapp_sent,
            'whatsapp_delivered': u.whatsapp_delivered,
            'whatsapp_failed': u.whatsapp_failed,
            'sms_sent': u.sms_sent,
            'sms_delivered': u.sms_delivered,
            'sms_failed': u.sms_failed,
            'total_verified': u.total_verified,
            'total_expired': u.total_expired,
            'whatsapp_cost': str(u.whatsapp_cost),
            'sms_cost': str(u.sms_cost),
            'total_cost': str(u.total_cost),
        })

    return Response({'days': days, 'usage': data})


@extend_schema(
    tags=['OTPaaS: Billing & Usage'],
    summary='List Pricing Tiers',
    description='**Public endpoint** (no authentication required). Returns all available OTPaaS pricing tiers with per-OTP costs, whitelabel availability, and SLA details.',
    auth=[],
)
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def otp_pricing(request):
    """Public endpoint — list available pricing tiers."""
    tiers = OTPPricingTier.objects.filter(is_active=True).order_by('display_order')
    data = []
    for t in tiers:
        data.append({
            'name': t.name,
            'monthly_base_fee': str(t.monthly_base_fee),
            'whatsapp_per_otp': str(t.price_per_otp_whatsapp),
            'sms_per_otp': str(t.price_per_otp_sms),
            'min_monthly_volume': t.min_monthly_volume,
            'max_monthly_volume': t.max_monthly_volume or 'unlimited',
            'whitelabel_available': t.whitelabel_available,
            'whitelabel_fee': str(t.whitelabel_fee_monthly),
            'priority_support': t.priority_support,
            'sla_uptime': str(t.sla_uptime),
        })
    return Response({'tiers': data})
