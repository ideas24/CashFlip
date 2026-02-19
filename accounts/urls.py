from django.urls import path
from accounts import views

app_name = 'accounts'

urlpatterns = [
    # Generic OTP (accepts channel in body)
    path('auth/request-otp/', views.request_otp, name='request_otp'),

    # Dedicated login buttons — separate WhatsApp and SMS flows
    path('auth/otp/sms/', views.request_sms_otp, name='request_sms_otp'),
    path('auth/otp/whatsapp/', views.request_whatsapp_otp, name='request_whatsapp_otp'),

    # Verify OTP (same for both channels)
    path('auth/verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('auth/refresh/', views.refresh_token_view, name='refresh_token'),

    # Email/password auth
    path('auth/email/signup/', views.email_signup, name='email_signup'),
    path('auth/email/login/', views.email_login, name='email_login'),

    # Public — which login buttons to show
    path('auth/methods/', views.auth_methods, name='auth_methods'),

    # Profile
    path('profile/', views.player_profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
]
