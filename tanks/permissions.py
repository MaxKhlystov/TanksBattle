import time

from rest_framework import permissions


def has_2fa(request):
    verified_at = request.session.get('2fa_at')
    if not verified_at:
        return False
    return time.time() - verified_at < 30 * 60


def is_admin(request):
    return request.user.is_staff and has_2fa(request)


class IsAdminWith2FA(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_admin(request)


class IsAdminWith2FAOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_admin(request)
