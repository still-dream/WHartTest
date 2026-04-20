from django.contrib import admin
from .models import OperationLog


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'feature', 'path', 'method', 'ip_address', 'created_at']
    list_filter = ['feature', 'created_at']
    search_fields = ['username', 'feature', 'path']
    readonly_fields = ['id', 'username', 'feature', 'path', 'method', 'ip_address', 'user_agent', 'created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
