from rest_framework import permissions
from . import models, utils


class IsGetOrIsAuthenticated(permissions.BasePermission):
    """
        need tokenAuthentication for all methods except GET request
    """

    def has_permission(self, request, view):
        if request.method == 'GET':
            return True
        return request.user and request.user.is_authenticated
    
    
class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.type == "Admin"



