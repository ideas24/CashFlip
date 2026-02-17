"""
Partner API v1 URL configuration.
All endpoints are prefixed with /api/partner/v1/ in the root urlconf.
"""

from django.urls import path
from partner import views

app_name = 'partner'

urlpatterns = [
    # Player management
    path('players/auth', views.player_auth, name='player-auth'),

    # Game config
    path('game/config', views.game_config, name='game-config'),

    # Game operations
    path('game/start', views.game_start, name='game-start'),
    path('game/flip', views.game_flip, name='game-flip'),
    path('game/cashout', views.game_cashout, name='game-cashout'),
    path('game/state/<uuid:session_id>', views.game_state, name='game-state'),
    path('game/history/<str:ext_player_id>', views.game_history, name='game-history'),
    path('game/verify/<uuid:session_id>', views.game_verify, name='game-verify'),

    # Reports
    path('reports/ggr', views.reports_ggr, name='reports-ggr'),
    path('reports/sessions', views.reports_sessions, name='reports-sessions'),

    # Settlements
    path('settlements/', views.settlements_list, name='settlements-list'),

    # Webhooks
    path('webhooks/configure', views.webhooks_configure, name='webhooks-configure'),
]
