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


class IsStaffAnd2FAVerified(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not request.user.is_staff:
            return False
        return has_2fa(request)