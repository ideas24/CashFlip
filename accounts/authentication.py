"""
JWT Authentication for Cashflip
"""

import jwt
import logging
from datetime import datetime, timedelta, timezone

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)


class JWTAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return 'Bearer'

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header[7:]
        
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token')
        
        from accounts.models import Player
        try:
            player = Player.objects.get(id=payload['user_id'], is_active=True)
        except Player.DoesNotExist:
            raise AuthenticationFailed('Player not found')
        
        return (player, token)


def generate_access_token(player):
    payload = {
        'user_id': str(player.id),
        'exp': datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES),
        'iat': datetime.now(timezone.utc),
        'type': 'access',
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm='HS256')


def generate_refresh_token(player):
    payload = {
        'user_id': str(player.id),
        'exp': datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS),
        'iat': datetime.now(timezone.utc),
        'type': 'refresh',
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm='HS256')


def verify_refresh_token(token):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=['HS256'])
        if payload.get('type') != 'refresh':
            raise AuthenticationFailed('Invalid token type')
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed('Refresh token has expired')
    except jwt.InvalidTokenError:
        raise AuthenticationFailed('Invalid refresh token')
