"""
drf-spectacular extensions for Partner API.

Registers PartnerHMACAuthentication so the OpenAPI schema
correctly documents the X-API-Key / X-Signature security scheme.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class PartnerHMACAuthExtension(OpenApiAuthenticationExtension):
    target_class = 'partner.auth.PartnerHMACAuthentication'
    name = 'PartnerHMAC'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-API-Key',
            'description': (
                'HMAC-SHA256 authenticated requests require two headers:\n'
                '- **X-API-Key**: Your operator API key\n'
                '- **X-Signature**: HMAC-SHA256(request_body, api_secret)\n'
                '- **X-Timestamp** (optional): Unix timestamp for replay protection'
            ),
        }
