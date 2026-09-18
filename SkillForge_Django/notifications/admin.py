from django.contrib import admin
from .models import WebhookAddress, MessageTemplate


@admin.register(WebhookAddress)
class WebhookAddressAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform_type', 'url', 'is_active', 'creator', 'created_at']
    list_filter = ['is_active', 'platform_type']
    search_fields = ['name', 'url']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform_type', 'is_system', 'creator', 'created_at', 'updated_at']
    list_filter = ['is_system', 'platform_type']
    search_fields = ['name', 'content']
    readonly_fields = ['created_at', 'updated_at']
