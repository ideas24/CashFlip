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

# Defaults — overridden by AuthConfig from DB when available
_DEFAULT_OTP_EXPIRY_MINUTES = 5
_DEFAULT_MAX_OTP_PER_HOUR = 6


def _get_auth_config():
    """Load AuthConfig from DB. Returns (otp_expiry_minutes, max_otp_per_hour)."""
    try:
        from accounts.models import AuthConfig
        cfg = AuthConfig.get_config()
        return cfg.otp_expiry_minutes, cfg.max_otp_per_hour
    except Exception:
        return _DEFAULT_OTP_EXPIRY_MINUTES, _DEFAULT_MAX_OTP_PER_HOUR


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
    otp_expiry, max_per_hour = _get_auth_config()
    logger.info(f'send_otp: phone={phone[:6]}***, channel={channel}, expiry={otp_expiry}m, max/hr={max_per_hour}')

    # Rate limiting
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_count = OTPToken.objects.filter(
        phone=phone,
        created_at__gte=one_hour_ago
    ).count()
    
    if recent_count >= max_per_hour:
        logger.warning(f'OTP rate limit hit: {phone[:6]}*** sent {recent_count} in last hour (max={max_per_hour})')
        return {'success': False, 'message': 'Too many OTP requests. Please try again later.'}
    
    # Invalidate previous unused OTPs
    OTPToken.objects.filter(phone=phone, is_used=False).update(is_used=True)
    
    # Generate new OTP
    code = OTPToken.generate_code()
    otp = OTPToken.objects.create(
        phone=phone,
        code=code,
        channel=channel,
        expires_at=timezone.now() + timedelta(minutes=otp_expiry),
        ip_address=ip_address,
    )
    
    # Send via appropriate channel
    if channel == 'whatsapp':
        success = _send_whatsapp_otp(phone, code)
    else:
        success = _send_sms_otp(phone, code)
    
    if success:
        logger.info(f'OTP sent successfully: {phone[:6]}*** via {channel}')
        return {'success': True, 'message': f'OTP sent via {channel}'}
    else:
        logger.error(f'OTP send FAILED: {phone[:6]}*** via {channel}')
        # Friendly message suggesting the other channel
        alt = 'WhatsApp' if channel == 'sms' else 'SMS'
        return {
            'success': False,
            'message': f'Could not deliver OTP via {channel.upper()}. Please try {alt} instead.',
            'suggest_channel': 'whatsapp' if channel == 'sms' else 'sms',
        }


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
    Send OTP via WhatsApp using Meta Authentication template.
    
    For Ghana (+233) numbers: tries WHATSAPP_PHONE_NUMBER_ID_GH first,
    falls back to WHATSAPP_PHONE_NUMBER_ID if GH number fails.
    
    Template must be pre-registered on Meta Business Manager:
      Name: cashflip_auth_otp (or WHATSAPP_AUTH_TEMPLATE_NAME env)
      Body: {{1}} is your verification code.
      Button: Copy code (copy_code type)
    """
    access_token = settings.WHATSAPP_ACCESS_TOKEN
    phone_number_id_default = settings.WHATSAPP_PHONE_NUMBER_ID
    phone_number_id_gh = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID_GH', '')
    template_name = getattr(settings, 'WHATSAPP_AUTH_TEMPLATE_NAME', 'cashflip_auth_otp')
    
    if not access_token or not phone_number_id_default:
        logger.error('WhatsApp credentials not configured: token=%s, phone_id=%s', bool(access_token), bool(phone_number_id_default))
        return False
    
    # Normalize phone to international format without +
    normalized = phone.replace('+', '').replace(' ', '')
    if normalized.startswith('0'):
        normalized = '233' + normalized[1:]
    
    # Build ordered list of phone IDs: default first, GH as fallback for Ghana numbers
    is_ghana = normalized.startswith('233')
    phone_ids = [phone_number_id_default]
    if is_ghana and phone_number_id_gh and phone_number_id_gh != phone_number_id_default:
        phone_ids.append(phone_number_id_gh)
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    
    # Authentication template: body has {{1}} = code, URL button has otp{{1}} suffix
    template_payload = {
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
    
    # Plain text fallback (works without approved template)
    text_payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': normalized,
        'type': 'text',
        'text': {
            'body': f'Your Cashflip verification code is: {code}\n\nThis code expires in 5 minutes. Do not share it with anyone.'
        }
    }
    
    for pid in phone_ids:
        url = f"https://graph.facebook.com/v23.0/{pid}/messages"
        
        # Try template message first
        logger.info(f'WhatsApp OTP: sending template to {normalized}, template={template_name}, phone_id={pid}')
        try:
            response = requests.post(url, json=template_payload, headers=headers, timeout=30)
            logger.info(f'WhatsApp template response (phone_id={pid}): status={response.status_code}, body={response.text[:500]}')
            if response.status_code in [200, 201]:
                logger.info(f'WhatsApp template OTP sent to {normalized} via phone_id={pid}')
                return True
        except Exception as e:
            logger.warning(f'WhatsApp template error (phone_id={pid}): {e}')
        
        # Template failed — try plain text message
        logger.info(f'WhatsApp OTP: trying plain text to {normalized}, phone_id={pid}')
        try:
            response = requests.post(url, json=text_payload, headers=headers, timeout=30)
            logger.info(f'WhatsApp text response (phone_id={pid}): status={response.status_code}, body={response.text[:500]}')
            if response.status_code in [200, 201]:
                logger.info(f'WhatsApp text OTP sent to {normalized} via phone_id={pid}')
                return True
            else:
                logger.warning(f'WhatsApp text failed (phone_id={pid}): {response.status_code} {response.text[:300]}')
        except Exception as e:
            logger.warning(f'WhatsApp text error (phone_id={pid}): {e}')
        
        logger.info(f'Phone ID {pid} exhausted, trying next...')
    
    logger.error(f'All WhatsApp methods exhausted for {normalized}')
    return False


def _send_sms_otp(phone, code):
    """
    Send OTP via SMS using multi-provider fallback chain.
    
    1. Query SMSProvider model for active providers (ordered by priority desc)
    2. Try each provider until one succeeds
    3. Fall back to Twilio env vars if no DB providers configured
    """
    # Normalize phone to E.164 format
    normalized = phone.replace(' ', '')
    if normalized.startswith('0'):
        normalized = '+233' + normalized[1:]
    elif not normalized.startswith('+'):
        normalized = '+' + normalized

    otp_expiry, _ = _get_auth_config()
    body = f'Cashflip - Your verification code is: {code}. Expires in {otp_expiry} minutes.'

    # Try DB-configured providers first
    try:
        from accounts.models import SMSProvider
        providers = list(SMSProvider.objects.filter(is_active=True).order_by('-priority'))
    except Exception:
        providers = []

    if providers:
        for provider in providers:
            logger.info(f'SMS OTP: trying {provider.name} ({provider.provider_type}) to {normalized[:6]}***')
            try:
                success = _send_via_provider(provider, normalized, body)
                if success:
                    logger.info(f'SMS OTP sent via {provider.name} to {normalized[:6]}***')
                    return True
                logger.warning(f'SMS OTP failed via {provider.name}, trying next...')
            except Exception as e:
                logger.warning(f'SMS OTP error via {provider.name}: {e}')
        logger.error(f'All DB SMS providers exhausted for {normalized[:6]}***')
        return False

    # Fallback: use Twilio from env vars (legacy path)
    return _send_via_twilio_env(normalized, body)


def _send_via_provider(provider, phone, body):
    """Dispatch to the correct provider-specific sender."""
    dispatch = {
        'twilio': _send_via_twilio,
        'arkesel': _send_via_arkesel,
        'hubtel': _send_via_hubtel,
        'mnotify': _send_via_mnotify,
    }
    handler = dispatch.get(provider.provider_type)
    if not handler:
        logger.warning(f'Unknown SMS provider type: {provider.provider_type}')
        return False
    return handler(provider, phone, body)


def _send_via_twilio(provider, phone, body):
    """Send SMS via Twilio using DB-configured provider."""
    try:
        from twilio.rest import Client
        client = Client(provider.api_key, provider.api_secret)
    except Exception as e:
        logger.error(f'Twilio client init error: {e}')
        return False

    # Build sender list: fallback number first for Ghana
    is_ghana = phone.startswith('+233')
    fallback = provider.extra_config.get('fallback_number', '')
    sender_id = provider.sender_id

    if is_ghana and fallback:
        senders = [fallback]
        if sender_id != fallback:
            senders.append(sender_id)
    else:
        senders = [sender_id]
        if fallback and fallback != sender_id:
            senders.append(fallback)

    for sender in senders:
        try:
            msg = client.messages.create(body=body, from_=sender, to=phone)
            logger.info(f'Twilio SMS sent: SID={msg.sid}, status={msg.status}, from={sender}')
            return True
        except Exception as e:
            logger.warning(f'Twilio sender {sender} failed: {e}')
    return False


def _send_via_arkesel(provider, phone, body):
    """Send SMS via Arkesel API."""
    api_key = provider.api_key
    sender_id = provider.sender_id or 'CASHFLIP'
    url = provider.base_url or 'https://sms.arkesel.com/api/v2/sms/send'

    try:
        resp = requests.post(url, json={
            'sender': sender_id,
            'message': body,
            'recipients': [phone],
        }, headers={'api-key': api_key}, timeout=30)
        logger.info(f'Arkesel response: {resp.status_code} {resp.text[:300]}')
        return resp.status_code in [200, 201]
    except Exception as e:
        logger.warning(f'Arkesel error: {e}')
        return False


def _send_via_hubtel(provider, phone, body):
    """Send SMS via Hubtel API."""
    client_id = provider.api_key
    client_secret = provider.api_secret
    sender_id = provider.sender_id or 'CASHFLIP'
    url = provider.base_url or 'https://smsc.hubtel.com/v1/messages/send'

    try:
        resp = requests.get(url, params={
            'clientid': client_id,
            'clientsecret': client_secret,
            'from': sender_id,
            'to': phone,
            'content': body,
        }, timeout=30)
        logger.info(f'Hubtel response: {resp.status_code} {resp.text[:300]}')
        return resp.status_code in [200, 201]
    except Exception as e:
        logger.warning(f'Hubtel error: {e}')
        return False


def _send_via_mnotify(provider, phone, body):
    """Send SMS via mNotify API."""
    api_key = provider.api_key
    sender_id = provider.sender_id or 'CASHFLIP'
    url = provider.base_url or 'https://apps.mnotify.net/smsapi'

    try:
        resp = requests.get(url, params={
            'key': api_key,
            'to': phone,
            'msg': body,
            'sender_id': sender_id,
        }, timeout=30)
        logger.info(f'mNotify response: {resp.status_code} {resp.text[:300]}')
        data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
        return resp.status_code == 200 and data.get('status') != 'error'
    except Exception as e:
        logger.warning(f'mNotify error: {e}')
        return False


def _send_via_twilio_env(phone, body):
    """Legacy: Send SMS via Twilio using env vars (fallback when no DB providers)."""
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_PHONE_NUMBER
    fallback_number = getattr(settings, 'TWILIO_FALLBACK_NUMBER', '')

    if not account_sid or not auth_token or not from_number:
        logger.error('Twilio credentials not configured: sid=%s, token=%s, from=%s', bool(account_sid), bool(auth_token), bool(from_number))
        return False

    is_ghana = phone.startswith('+233')
    if is_ghana and fallback_number:
        senders = [fallback_number]
        if from_number != fallback_number:
            senders.append(from_number)
    else:
        senders = [from_number]
        if fallback_number and fallback_number != from_number:
            senders.append(fallback_number)

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
    except Exception as e:
        logger.error(f'Twilio client init error: {e}', exc_info=True)
        return False

    for sender in senders:
        try:
            logger.info(f'Twilio SMS (env): sending to {phone}, from={sender}')
            message = client.messages.create(body=body, from_=sender, to=phone)
            logger.info(f'SMS OTP sent to {phone}, SID: {message.sid}, status: {message.status}, from={sender}')
            return True
        except Exception as e:
            logger.warning(f'Twilio SMS failed with sender {sender} to {phone}: {e}')
            if sender == senders[-1]:
                logger.error(f'All Twilio senders exhausted for {phone}', exc_info=True)
                return False
            logger.info(f'Retrying with fallback sender...')

    return False
