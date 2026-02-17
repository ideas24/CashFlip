from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from accounts.models import Player, PlayerProfile, OTPToken, AdminRole, AuthConfig, StaffMember, AuditLog


@admin.register(Player)
class PlayerAdmin(BaseUserAdmin):
    list_display = ['phone', 'email', 'display_name', 'country', 'is_verified', 'auth_provider', 'date_joined']
    list_filter = ['is_verified', 'auth_provider', 'country', 'is_active', 'is_staff']
    search_fields = ['phone', 'email', 'display_name']
    ordering = ['-date_joined']
    fieldsets = (
        (None, {'fields': ('phone', 'email', 'password')}),
        ('Profile', {'fields': ('display_name', 'avatar', 'country', 'default_currency')}),
        ('Auth', {'fields': ('is_verified', 'auth_provider', 'social_id')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('date_joined', 'last_login')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('phone', 'email', 'password1', 'password2')}),
    )


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ['player', 'total_games', 'total_won', 'total_lost', 'highest_cashout', 'current_level']
    search_fields = ['player__phone', 'player__display_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(OTPToken)
class OTPTokenAdmin(admin.ModelAdmin):
    list_display = ['phone', 'channel', 'is_used', 'expires_at', 'created_at']
    list_filter = ['channel', 'is_used']
    search_fields = ['phone']
    readonly_fields = ['created_at']


@admin.register(AuthConfig)
class AuthConfigAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'sms_otp_enabled', 'whatsapp_otp_enabled', 'google_enabled', 'facebook_enabled', 'updated_at']

    fieldsets = (
        ('Login Method Toggles', {
            'fields': ('sms_otp_enabled', 'whatsapp_otp_enabled', 'google_enabled', 'facebook_enabled'),
            'description': 'Enable or disable each login method. Changes take effect immediately.',
        }),
        ('OTP Settings', {
            'fields': ('otp_expiry_minutes', 'max_otp_per_hour'),
        }),
        ('Maintenance', {
            'fields': ('maintenance_message',),
            'description': 'Custom message shown to users when a login method is disabled. Leave blank for a generic message.',
        }),
    )

    def has_add_permission(self, request):
        # Singleton — only allow add if none exists
        return not AuthConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AdminRole)
class AdminRoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'codename', 'created_at']
    search_fields = ['name']


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ['player', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['staff', 'action', 'model_name', 'created_at']
    list_filter = ['action', 'model_name']
    readonly_fields = ['staff', 'action', 'model_name', 'object_id', 'changes', 'ip_address', 'created_at']
    search_fields = ['action', 'model_name']
