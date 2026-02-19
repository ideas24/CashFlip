from django.urls import path
from referrals import views

app_name = 'referrals'

urlpatterns = [
    path('stats/', views.referral_stats, name='referral_stats'),
]
