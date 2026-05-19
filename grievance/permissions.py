from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'ADMIN'
class IsFaculty(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'FACULTY'
class IsStudentOrStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['STUDENT', 'STAFF']