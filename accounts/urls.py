from django.urls import path
from accounts import views

app_name = 'accounts'

urlpatterns = [
    path('auth/request-otp/', views.request_otp, name='request_otp'),
    path('auth/verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('auth/refresh/', views.refresh_token_view, name='refresh_token'),
    path('profile/', views.player_profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
]
