from rest_framework.permissions import BasePermission


class IsStaffAdmin(BasePermission):
    """Allow access only to active staff members or superusers."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'staff_profile') and request.user.staff_profile.is_active


class HasDashboardPermission(BasePermission):
    """Check specific permission from the staff member's role."""
    permission_required = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        perm = getattr(view, 'permission_required', None) or self.permission_required
        if not perm:
            return True
        if hasattr(request.user, 'staff_profile'):
            return request.user.staff_profile.has_permission(perm)
        return False
