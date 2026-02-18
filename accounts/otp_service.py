"""
OTP Service - sends OTP via WhatsApp (reachmint bot) or Twilio SMS
"""

import logging
import requests
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from accounts.models import OTPToken

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = 5
MAX_OTP_PER_PHONE_PER_HOUR = 6


def normalize_phone(phone):
    """
    Normalize phone to canonical format: +233XXXXXXXXX
    Accepts: 0241234567, 233241234567, +233241234567, +233 24 123 4567
    """
    cleaned = phone.replace(' ', '').replace('-', '')
    if cleaned.startswith('+'):
        return cleaned
    if cleaned.startswith('0') and len(cleaned) == 10:
        return '+233' + cleaned[1:]
    if cleaned.startswith('233'):
        return '+' + cleaned
    return '+' + cleaned


def send_otp(phone, channel='sms', ip_address=None):
    """
    Generate and send OTP to phone number.
    
    Args:
        phone: Phone number (e.g., '0241234567' or '+233241234567')
        channel: 'sms' or 'whatsapp'
        ip_address: Request IP for rate limiting
    
    Returns:
        dict: {'success': bool, 'message': str}
    """
    phone = normalize_phone(phone)

    # Rate limiting
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_count = OTPToken.objects.filter(
        phone=phone,
        created_at__gte=one_hour_ago
    ).count()
    
    if recent_count >= MAX_OTP_PER_PHONE_PER_HOUR:
        return {'success': False, 'message': 'Too many OTP requests. Please try again later.'}
    
    # Invalidate previous unused OTPs
    OTPToken.objects.filter(phone=phone, is_used=False).update(is_used=True)
    
    # Generate new OTP
    code = OTPToken.generate_code()
    otp = OTPToken.objects.create(
        phone=phone,
        code=code,
        channel=channel,
        expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES),
        ip_address=ip_address,
    )
    
    # Send via appropriate channel
    if channel == 'whatsapp':
        success = _send_whatsapp_otp(phone, code)
    else:
        success = _send_sms_otp(phone, code)
    
    if success:
        return {'success': True, 'message': f'OTP sent via {channel}'}
    else:
        return {'success': False, 'message': f'Failed to send OTP via {channel}. Please try again.'}


def verify_otp(phone, code):
    """
    Verify OTP code.
    
    Returns:
        dict: {'success': bool, 'message': str}
    """
    phone = normalize_phone(phone)
    otp = OTPToken.objects.filter(
        phone=phone,
        code=code,
        is_used=False,
        expires_at__gt=timezone.now()
    ).order_by('-created_at').first()
    
    if not otp:
        return {'success': False, 'message': 'Invalid or expired OTP'}
    
    otp.is_used = True
    otp.save(update_fields=['is_used'])
    
    return {'success': True, 'message': 'OTP verified'}


def _send_whatsapp_otp(phone, code):
    """
    Send OTP via WhatsApp using Meta Authentication template with copy-code button.
    
    Authentication template guidelines (Meta):
    - Category: AUTHENTICATION
    - No URLs, media, or emojis in content or parameters
    - Parameters restricted to 15 characters (6-digit code = OK)
    - Uses copy-code button so user can tap to copy the OTP
    
    Template must be pre-registered on Meta Business Manager:
      Name: cashflip_auth_otp (or WHATSAPP_AUTH_TEMPLATE_NAME env)
      Body: {{1}} is your verification code.
      Button: Copy code
    """
    access_token = settings.WHATSAPP_ACCESS_TOKEN
    phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
    template_name = getattr(settings, 'WHATSAPP_AUTH_TEMPLATE_NAME', 'cashflip_auth_otp')
    
    if not access_token or not phone_number_id:
        logger.error('WhatsApp credentials not configured for OTP')
        return False
    
    # Normalize phone to international format without +
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
                    'parameters': [
                        {'type': 'text', 'text': code}
                    ]
                },
                {
                    'type': 'button',
                    'sub_type': 'url',
                    'index': '0',
                    'parameters': [
                        {'type': 'text', 'text': code}
                    ]
                }
            ]
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code in [200, 201]:
            logger.info(f'WhatsApp auth template OTP sent to {normalized}')
            return True
        else:
            logger.error(f'WhatsApp auth template OTP failed: {response.status_code} {response.text}')
            return False
    except Exception as e:
        logger.error(f'WhatsApp OTP error: {e}')
        return False


def _send_sms_otp(phone, code):
    """Send OTP via Twilio SMS."""
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_PHONE_NUMBER
    
    if not account_sid or not auth_token or not from_number:
        logger.error('Twilio credentials not configured for OTP')
        return False
    
    # Normalize phone to E.164 format
    normalized = phone.replace(' ', '')
    if normalized.startswith('0'):
        normalized = '+233' + normalized[1:]
    elif not normalized.startswith('+'):
        normalized = '+' + normalized
    
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body=f'Cashflip - Your verification code is: {code}. Expires in {OTP_EXPIRY_MINUTES} minutes.',
            from_=from_number,
            to=normalized
        )
        
        logger.info(f'SMS OTP sent to {normalized}, SID: {message.sid}')
        return True
    except Exception as e:
        logger.error(f'Twilio SMS OTP error: {e}')
        return False
