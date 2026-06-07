from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'profile') and request.user.profile.role == 'admin'


class IsOperator(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'profile') and request.user.profile.role == 'operator'


class IsAuditor(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'profile') and request.user.profile.role == 'auditor'


class IsAdminOrOperator(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'profile'):
            return request.user.profile.role in ['admin', 'operator']
        return False


class IsAdminOrAuditor(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'profile'):
            return request.user.profile.role in ['admin', 'auditor']
        return False
