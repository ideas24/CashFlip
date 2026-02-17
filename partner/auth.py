"""
HMAC-SHA256 authentication for Partner API.

Operators sign requests with:
  - X-API-Key: <api_key>
  - X-Signature: HMAC-SHA256(request_body, api_secret)
  - X-Timestamp: Unix timestamp (optional, for replay protection)

DRF authentication class extracts operator context from the request.
"""

import hashlib
import hmac
import time
import logging

from django.utils import timezone
from rest_framework import authentication, exceptions

from partner.models import OperatorAPIKey

logger = logging.getLogger(__name__)

# Allow 5 minutes of clock skew for timestamp validation
MAX_TIMESTAMP_SKEW = 300


class PartnerHMACAuthentication(authentication.BaseAuthentication):
    """
    DRF authentication backend for partner API requests.
    Returns (operator_api_key.operator, operator_api_key) as the auth tuple.
    The 'user' in request.user will be the Operator instance.
    The api_key object is available via request.auth.
    """

    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY', '').strip()
        signature = request.META.get('HTTP_X_SIGNATURE', '').strip()

        if not api_key:
            return None  # Not a partner request — let other auth backends handle

        if not signature:
            raise exceptions.AuthenticationFailed('X-Signature header is required')

        # Look up the key
        try:
            key_obj = OperatorAPIKey.objects.select_related('operator').get(
                api_key=api_key,
                is_active=True,
                revoked_at__isnull=True,
            )
        except OperatorAPIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid or revoked API key')

        # Check operator status
        if key_obj.operator.status != 'active':
            raise exceptions.AuthenticationFailed(
                f'Operator is {key_obj.operator.get_status_display()}'
            )

        # IP whitelist check
        if key_obj.ip_whitelist:
            client_ip = self._get_client_ip(request)
            if client_ip not in key_obj.ip_whitelist:
                logger.warning(
                    f'Partner API: IP {client_ip} not in whitelist for {key_obj.operator.name}'
                )
                raise exceptions.AuthenticationFailed('IP address not whitelisted')

        # Optional timestamp replay protection
        timestamp_str = request.META.get('HTTP_X_TIMESTAMP', '').strip()
        if timestamp_str:
            try:
                ts = int(timestamp_str)
                now = int(time.time())
                if abs(now - ts) > MAX_TIMESTAMP_SKEW:
                    raise exceptions.AuthenticationFailed('Request timestamp too old or too far in future')
            except ValueError:
                raise exceptions.AuthenticationFailed('Invalid X-Timestamp value')

        # Verify HMAC signature
        body = request.body or b''
        expected = hmac.new(
            key_obj.api_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise exceptions.AuthenticationFailed('Invalid signature')

        # Update last_used_at (non-blocking, best effort)
        OperatorAPIKey.objects.filter(pk=key_obj.pk).update(last_used_at=timezone.now())

        return (key_obj.operator, key_obj)

    def authenticate_header(self, request):
        return 'HMAC'

    @staticmethod
    def _get_client_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
