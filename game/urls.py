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
]
