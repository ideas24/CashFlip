from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from accounts.models import Player, PlayerProfile, OTPToken, AdminRole, StaffMember, AuditLog


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
