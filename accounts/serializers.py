"""
Accounts Serializers
"""

from rest_framework import serializers
from accounts.models import Player, PlayerProfile


class RequestOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    channel = serializers.ChoiceField(choices=['sms', 'whatsapp'], default='sms')


class PhoneOnlySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6, min_length=6)


class EmailSignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6)
    display_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    ref_code = serializers.CharField(max_length=20, required=False, allow_blank=True)


class EmailLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class PlayerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerProfile
        fields = [
            'total_games', 'total_won', 'total_lost', 'highest_cashout',
            'best_streak', 'current_level', 'total_deposited', 'total_withdrawn',
            'lifetime_flips',
        ]
        read_only_fields = fields


class PlayerSerializer(serializers.ModelSerializer):
    profile = PlayerProfileSerializer(read_only=True)

    class Meta:
        model = Player
        fields = [
            'id', 'phone', 'email', 'display_name', 'avatar', 'country',
            'is_verified', 'auth_provider', 'date_joined', 'profile',
        ]
        read_only_fields = ['id', 'is_verified', 'auth_provider', 'date_joined']


class PlayerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ['display_name', 'avatar', 'country']
