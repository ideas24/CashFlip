from rest_framework import serializers
from accounts.models import Player, AdminRole, StaffMember, AuthConfig


class AdminLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField()


class AdminUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    phone = serializers.CharField()
    display_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    def get_display_name(self, obj):
        return obj.get_display_name()

    def get_role(self, obj):
        if obj.is_superuser:
            return 'super_admin'
        if hasattr(obj, 'staff_profile'):
            return obj.staff_profile.role.codename
        return 'unknown'

    def get_permissions(self, obj):
        if obj.is_superuser:
            return [c[0] for c in AdminRole.PERMISSION_CHOICES]
        if hasattr(obj, 'staff_profile'):
            return obj.staff_profile.role.permissions
        return []


class PlayerListSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    total_sessions = serializers.SerializerMethodField()
    total_wagered = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = ['id', 'phone', 'display_name', 'balance', 'total_sessions',
                  'total_wagered', 'is_active', 'date_joined', 'last_login']

    def get_balance(self, obj):
        wallet = getattr(obj, 'wallet', None)
        return str(wallet.balance) if wallet else '0.00'

    def get_total_sessions(self, obj):
        return obj.game_sessions.count() if hasattr(obj, 'game_sessions') else 0

    def get_total_wagered(self, obj):
        from django.db.models import Sum
        total = obj.game_sessions.aggregate(s=Sum('stake_amount'))['s']
        return str(total or 0)


class AuthSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthConfig
        fields = ['sms_otp_enabled', 'whatsapp_otp_enabled', 'email_password_enabled',
                  'google_enabled', 'facebook_enabled', 'otp_expiry_minutes', 'max_otp_per_hour']


class RoleSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='name')
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = AdminRole
        fields = ['id', 'name', 'display_name', 'codename', 'permissions', 'user_count']

    def get_user_count(self, obj):
        return obj.members.filter(is_active=True).count()


class StaffSerializer(serializers.Serializer):
    id = serializers.UUIDField(source='player.id')
    phone = serializers.CharField(source='player.phone')
    display_name = serializers.SerializerMethodField()
    role = serializers.CharField(source='role.codename')
    role_display = serializers.CharField(source='role.name')
    is_active = serializers.BooleanField()
    last_login = serializers.DateTimeField(source='player.last_login')

    def get_display_name(self, obj):
        return obj.player.get_display_name()
