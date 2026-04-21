from rest_framework import permissions
from django.core.cache import cache

class IsStaffAnd2FAVerified(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not request.user.is_staff:
            return False
        return cache.get(f'2fa_{request.user.id}', False)