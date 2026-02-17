"""
Serializers for the Partner API v1.
"""

from rest_framework import serializers


class PlayerAuthSerializer(serializers.Serializer):
    ext_player_id = serializers.CharField(max_length=200)
    display_name = serializers.CharField(max_length=200, required=False, default='')


class GameLaunchSerializer(serializers.Serializer):
    ext_player_id = serializers.CharField(max_length=200)
    ext_session_ref = serializers.CharField(max_length=200, required=False, default='')


class GameStartSerializer(serializers.Serializer):
    ext_player_id = serializers.CharField(max_length=200)
    stake = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=5, default='GHS')
    client_seed = serializers.CharField(max_length=64, required=False, default='')
    ext_session_ref = serializers.CharField(max_length=200, required=False, default='')


class GameFlipSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()


class GameCashoutSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()


class GameStateSerializer(serializers.Serializer):
    """Read-only serializer for game session state."""
    session_id = serializers.UUIDField(source='game_session.id')
    status = serializers.CharField(source='game_session.status')
    stake_amount = serializers.DecimalField(
        source='game_session.stake_amount', max_digits=12, decimal_places=2
    )
    cashout_balance = serializers.DecimalField(
        source='game_session.cashout_balance', max_digits=12, decimal_places=2
    )
    flip_count = serializers.IntegerField(source='game_session.flip_count')
    created_at = serializers.DateTimeField(source='game_session.created_at')
    ended_at = serializers.DateTimeField(source='game_session.ended_at')
    ext_session_ref = serializers.CharField()
    ext_player_id = serializers.CharField(source='operator_player.ext_player_id')


class FlipResultSerializer(serializers.Serializer):
    flip_number = serializers.IntegerField()
    value = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_zero = serializers.BooleanField()
    cumulative_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    result_hash = serializers.CharField()
    timestamp = serializers.DateTimeField()


class GameHistorySerializer(serializers.Serializer):
    session_id = serializers.UUIDField(source='game_session.id')
    status = serializers.CharField(source='game_session.status')
    stake_amount = serializers.DecimalField(
        source='game_session.stake_amount', max_digits=12, decimal_places=2
    )
    cashout_balance = serializers.DecimalField(
        source='game_session.cashout_balance', max_digits=12, decimal_places=2
    )
    flip_count = serializers.IntegerField(source='game_session.flip_count')
    created_at = serializers.DateTimeField(source='game_session.created_at')
    ended_at = serializers.DateTimeField(source='game_session.ended_at')
    ext_session_ref = serializers.CharField()


class OperatorGameConfigSerializer(serializers.Serializer):
    currency_code = serializers.CharField(source='currency.code')
    currency_symbol = serializers.CharField(source='currency.symbol')
    house_edge_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    min_stake = serializers.DecimalField(max_digits=10, decimal_places=2)
    max_stake = serializers.DecimalField(max_digits=12, decimal_places=2)
    max_cashout = serializers.DecimalField(max_digits=12, decimal_places=2)
    pause_cost_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    max_session_duration_minutes = serializers.IntegerField()


class GGRReportSerializer(serializers.Serializer):
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    total_bets = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_wins = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_sessions = serializers.IntegerField()
    ggr = serializers.DecimalField(max_digits=14, decimal_places=2)
    commission_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    net_operator_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    status = serializers.CharField()


class WebhookConfigureSerializer(serializers.Serializer):
    webhook_url = serializers.URLField()
    subscribed_events = serializers.ListField(
        child=serializers.CharField(max_length=30),
        required=False,
        default=['game.started', 'game.won', 'game.lost']
    )
