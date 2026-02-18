"""
Game Serializers
"""

from rest_framework import serializers
from game.models import Currency, CurrencyDenomination, GameSession, FlipResult, GameConfig


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'symbol', 'is_default', 'is_active']


class DenominationSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    front_image_url = serializers.SerializerMethodField()
    back_image_url = serializers.SerializerMethodField()

    class Meta:
        model = CurrencyDenomination
        fields = ['id', 'value', 'image_url', 'front_image_url', 'back_image_url', 'display_order', 'is_zero']

    def get_image_url(self, obj):
        if obj.front_image:
            return obj.front_image.url
        return None

    def get_front_image_url(self, obj):
        if obj.front_image:
            return obj.front_image.url
        return None

    def get_back_image_url(self, obj):
        if obj.back_image:
            return obj.back_image.url
        return None


class GameConfigPublicSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)

    class Meta:
        model = GameConfig
        fields = ['currency', 'min_deposit', 'max_cashout', 'min_stake', 'pause_cost_percent',
                  'auto_flip_seconds', 'simulated_feed_enabled']


class StartGameSerializer(serializers.Serializer):
    stake_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency_code = serializers.CharField(max_length=5, default='GHS')
    client_seed = serializers.CharField(max_length=64, required=False, default='')


class FlipResultSerializer(serializers.ModelSerializer):
    denomination = DenominationSerializer(read_only=True)

    class Meta:
        model = FlipResult
        fields = ['flip_number', 'value', 'is_zero', 'cumulative_balance', 'result_hash', 'denomination', 'timestamp']


class GameSessionSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)
    flips = FlipResultSerializer(many=True, read_only=True)

    class Meta:
        model = GameSession
        fields = [
            'id', 'currency', 'stake_amount', 'cashout_balance', 'status',
            'flip_count', 'server_seed_hash', 'created_at', 'ended_at', 'flips',
        ]


class GameSessionListSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)

    class Meta:
        model = GameSession
        fields = [
            'id', 'currency', 'stake_amount', 'cashout_balance', 'status',
            'flip_count', 'created_at', 'ended_at',
        ]


class PauseSerializer(serializers.Serializer):
    confirm = serializers.BooleanField(default=False)
