"""
Game Serializers
"""

from rest_framework import serializers
from game.models import Currency, CurrencyDenomination, GameSession, FlipResult, GameConfig, StakeTier


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'symbol', 'is_default', 'is_active']


class DenominationSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    front_image_url = serializers.SerializerMethodField()
    back_image_url = serializers.SerializerMethodField()
    face_image_path = serializers.SerializerMethodField()
    flip_gif_path = serializers.SerializerMethodField()

    class Meta:
        model = CurrencyDenomination
        fields = ['id', 'value', 'payout_multiplier', 'image_url', 'front_image_url', 'back_image_url',
                  'face_image_path', 'flip_sequence_prefix', 'flip_sequence_frames', 'flip_gif_path',
                  'flip_video_path', 'display_order', 'is_zero', 'weight']

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

    def get_face_image_path(self, obj):
        """Uploaded file takes priority; fall back to static path."""
        if obj.face_image_upload:
            return obj.face_image_upload.url
        return obj.face_image_path or ''

    def get_flip_gif_path(self, obj):
        """Uploaded GIF takes priority; fall back to static path."""
        if obj.flip_gif_upload:
            return obj.flip_gif_upload.url
        return obj.flip_gif_path or ''


class StakeTierSerializer(serializers.ModelSerializer):
    denomination_ids = serializers.SerializerMethodField()

    class Meta:
        model = StakeTier
        fields = ['id', 'name', 'min_stake', 'max_stake', 'denomination_ids', 'display_order', 'is_active']

    def get_denomination_ids(self, obj):
        return list(obj.denominations.values_list('id', flat=True))


class GameConfigPublicSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)

    class Meta:
        model = GameConfig
        fields = ['currency', 'min_deposit', 'max_cashout', 'min_stake', 'pause_cost_percent',
                  'min_flips_before_cashout', 'instant_cashout_enabled', 'instant_cashout_min_amount',
                  'auto_flip_seconds', 'flip_animation_mode', 'flip_sprite_url', 'flip_sprite_frames',
                  'flip_sprite_fps', 'flip_display_mode',
                  'flip_animation_speed_ms', 'flip_sound_enabled', 'flip_sound_url',
                  'win_sound_url', 'cashout_sound_url',
                  'start_flip_image_url', 'simulated_feed_enabled',
                  'payout_mode', 'decay_factor', 'max_flips_per_session',
                  'holiday_mode_enabled']


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
            'id', 'currency', 'stake_amount', 'cashout_balance',
            'payout_budget', 'remaining_budget', 'payout_pct_used',
            'is_holiday_boosted', 'status',
            'flip_count', 'server_seed_hash', 'created_at', 'ended_at', 'flips',
        ]


class GameSessionListSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)

    class Meta:
        model = GameSession
        fields = [
            'id', 'currency', 'stake_amount', 'cashout_balance',
            'payout_budget', 'remaining_budget', 'is_holiday_boosted',
            'status', 'flip_count', 'created_at', 'ended_at',
        ]


class PauseSerializer(serializers.Serializer):
    confirm = serializers.BooleanField(default=False)
