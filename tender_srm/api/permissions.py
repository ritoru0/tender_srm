from rest_framework.permissions import BasePermission

class IsManager(BasePermission):
    """Разрешение только для пользователей из группы 'Managers'."""
    
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Manager').exists()


class IsClient(BasePermission):
    """Разрешение только для пользователей из группы 'Client'."""
    
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Firm').exists()