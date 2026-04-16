from rest_framework import permissions
from django.core.cache import cache

class IsStaffAnd2FAVerified(permissions.BasePermission):
    """
    Доступ только для staff, у которых пройдена двухфакторная аутентификация
    (флаг в кэше '2fa_<user_id>').
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not request.user.is_staff:
            return False
        # Суперюзер может обходить 2FA (по желанию)
        if request.user.is_superuser:
            return True
        return cache.get(f'2fa_{request.user.id}', False)