from django.urls import path
from game import views

app_name = 'game'

urlpatterns = [
    path('currencies/', views.currencies, name='currencies'),
    path('config/', views.game_config, name='game_config'),
    path('start/', views.start_game, name='start_game'),
    path('flip/', views.flip, name='flip'),
    path('cashout/', views.cashout, name='cashout'),
    path('pause/', views.pause_game, name='pause_game'),
    path('resume/', views.resume_game, name='resume_game'),
    path('state/', views.game_state, name='game_state'),
    path('history/', views.game_history, name='game_history'),
    path('verify/<uuid:session_id>/', views.verify_session, name='verify_session'),
    path('live-feed/', views.live_feed, name='live_feed'),
    path('features/', views.feature_config, name='feature_config'),
    path('badges/', views.player_badges, name='player_badges'),
    path('wheel/status/', views.daily_wheel_status, name='daily_wheel_status'),
    path('wheel/spin/', views.daily_wheel_spin, name='daily_wheel_spin'),
    path('legal/', views.legal_api, name='legal_api'),
]
