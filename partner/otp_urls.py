"""
OTPaaS API v1 URL configuration.
All endpoints prefixed with /api/otp/v1/ in the root urlconf.
"""

from django.urls import path
from partner import otp_views

app_name = 'otpaas'

urlpatterns = [
    # Core OTP operations
    path('send', otp_views.otp_send, name='otp-send'),
    path('verify', otp_views.otp_verify, name='otp-verify'),
    path('status/<uuid:otp_id>', otp_views.otp_status, name='otp-status'),

    # Account & billing
    path('balance', otp_views.otp_balance, name='otp-balance'),
    path('usage', otp_views.otp_usage, name='otp-usage'),

    # Public
    path('pricing', otp_views.otp_pricing, name='otp-pricing'),
]
