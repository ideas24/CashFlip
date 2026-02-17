"""
OTPaaS HMAC Authentication.
Mirrors partner/auth.py but for OTP service clients.
Authenticates via X-OTP-Key + X-OTP-Signature headers.
"""

import hashlib
import hmac
import logging
import time

from django.core.cache import cache
from django.utils import timezone
from rest_framework import authentication, exceptions

from partner.models import OTPClient, OTPClientAPIKey

logger = logging.getLogger(__name__)

REPLAY_WINDOW = 300  # 5 minutes


class OTPClientAuthentication(authentication.BaseAuthentication):
    """
    HMAC-SHA256 authentication for OTPaaS clients.
    
    Required headers:
        X-OTP-Key: otp_live_xxxxxxxxxxxx
        X-OTP-Signature: HMAC-SHA256(body, api_secret)
    
    Optional headers:
        X-OTP-Timestamp: Unix timestamp (replay protection)
    """

    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_OTP_KEY', '').strip()
        signature = request.META.get('HTTP_X_OTP_SIGNATURE', '').strip()

        if not api_key:
            return None  # Not OTP auth — let other authenticators try

        if not signature:
            raise exceptions.AuthenticationFailed('X-OTP-Signature header required')

        # Lookup key
        try:
            key_obj = OTPClientAPIKey.objects.select_related('client', 'client__pricing_tier').get(
                api_key=api_key,
                is_active=True,
            )
        except OTPClientAPIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid or revoked API key')

        client = key_obj.client
        if client.status != 'active':
            raise exceptions.AuthenticationFailed(f'OTP client account is {client.status}')

        # IP whitelist
        if client.ip_whitelist:
            ip = self._get_client_ip(request)
            if ip and ip not in client.ip_whitelist:
                raise exceptions.AuthenticationFailed(f'IP {ip} not in whitelist')

        # Verify HMAC signature
        body = request.body or b''
        expected = hmac.new(
            key_obj.api_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise exceptions.AuthenticationFailed('Invalid signature')

        # Replay protection (optional)
        ts = request.META.get('HTTP_X_OTP_TIMESTAMP', '')
        if ts:
            try:
                ts_int = int(ts)
                if abs(time.time() - ts_int) > REPLAY_WINDOW:
                    raise exceptions.AuthenticationFailed('Request timestamp out of window')
            except ValueError:
                raise exceptions.AuthenticationFailed('Invalid timestamp format')

        # Rate limiting — per minute
        rate_key = f'otp_rate:{client.id}'
        current = cache.get(rate_key, 0)
        if current >= client.rate_limit_per_minute:
            raise exceptions.Throttled(detail='Rate limit exceeded. Try again shortly.')
        cache.set(rate_key, current + 1, timeout=60)

        # Update last used
        key_obj.last_used_at = timezone.now()
        key_obj.save(update_fields=['last_used_at'])

        # Return client as request.user, key as request.auth
        return (client, key_obj)

    def authenticate_header(self, request):
        return 'HMAC'

    @staticmethod
    def _get_client_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
