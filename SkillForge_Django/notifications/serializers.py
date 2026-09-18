from rest_framework import serializers
from .models import WebhookAddress, MessageTemplate


class WebhookAddressSerializer(serializers.ModelSerializer):
    """管理员看全部字段，普通用户仅 id/name/is_active"""

    class Meta:
        model = WebhookAddress
        fields = [
            'id', 'name', 'url', 'platform_type', 'description',
            'is_active', 'creator', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'creator', 'created_at', 'updated_at']


class WebhookAddressLimitedSerializer(serializers.ModelSerializer):
    """普通用户使用的精简序列化器（隐藏 url）"""

    class Meta:
        model = WebhookAddress
        fields = ['id', 'name', 'is_active']
        read_only_fields = fields


class MessageTemplateSerializer(serializers.ModelSerializer):
    """消息模板序列化器，is_system 只读"""

    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'name', 'content', 'platform_type', 'description',
            'is_system', 'creator', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'is_system', 'creator', 'created_at', 'updated_at']
