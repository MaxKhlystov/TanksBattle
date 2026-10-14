import time

from rest_framework import permissions

SECOND_FACTOR_SESSION_KEY = '2fa_at'
SECOND_FACTOR_TTL = 30 * 60  # 30 минут простоя


def has_2fa(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return False
    verified_at = request.session.get(SECOND_FACTOR_SESSION_KEY)
    if not verified_at:
        return False
    now = time.time()
    age = now - verified_at
    if age >= SECOND_FACTOR_TTL:
        return False
    if age > SECOND_FACTOR_TTL / 2:
        # скользящее окно: продлеваем, пока пользователь активен
        request.session[SECOND_FACTOR_SESSION_KEY] = now
    return True


def set_2fa(request):
    request.session[SECOND_FACTOR_SESSION_KEY] = time.time()


def clear_2fa(request):
    request.session.pop(SECOND_FACTOR_SESSION_KEY, None)


def is_staff_with_2fa(request):
    """Сотрудник (is_staff) с подтверждённой 2FA: видит и меняет данные всех игроков."""
    return request.user.is_staff and has_2fa(request)


class IsStaffAnd2FAVerified(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_staff_with_2fa(request)


class IsStaffAnd2FAOrReadOnly(IsStaffAnd2FAVerified):
    """Чтение — всем, изменение — только сотрудникам с подтверждённой 2FA."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return super().has_permission(request, view)
