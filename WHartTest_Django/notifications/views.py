import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .models import WebhookAddress, MessageTemplate
from .serializers import (
    WebhookAddressSerializer,
    WebhookAddressLimitedSerializer,
    MessageTemplateSerializer,
)
from .services import build_feishu_card
from wharttest_django.pagination import StandardPagination
import requests as http_requests

logger = logging.getLogger(__name__)


class IsAdminOrReadOnlyName(permissions.BasePermission):
    """管理员可完整CRUD；普通用户仅可GET列表（精简字段）"""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff or request.user.is_superuser


class IsCreatorOrAdmin(permissions.BasePermission):
    """创建者或管理员可编辑/删除；所有认证用户可读和创建"""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_superuser or request.user.is_staff:
            return True
        return obj.creator_id == request.user.id


class WebhookAddressViewSet(viewsets.ModelViewSet):
    """推送地址视图集"""

    queryset = WebhookAddress.objects.all()
    permission_classes = [IsAdminOrReadOnlyName]
    pagination_class = StandardPagination

    def get_serializer_class(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return WebhookAddressSerializer
        return WebhookAddressLimitedSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(detail=True, methods=['post'], url_path='test')
    def test_send(self, request, pk=None):
        """发送测试消息到该 webhook 地址"""
        addr = self.get_object()
        test_content = '## 推送测试\n这是一条测试消息，用于验证 Webhook 配置是否正确。'
        card = build_feishu_card(test_content, 'success', '', '')
        try:
            resp = http_requests.post(addr.url, json=card, timeout=10)
            if resp.status_code == 200:
                return Response({'message': '测试消息发送成功'}, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'message': f'发送失败，状态码: {resp.status_code}'},
                    status=status.HTTP_200_OK,
                )
        except Exception as e:
            return Response(
                {'message': f'发送失败: {str(e)}'},
                status=status.HTTP_200_OK,
            )


class MessageTemplateViewSet(viewsets.ModelViewSet):
    """消息模板视图集"""

    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsCreatorOrAdmin]
    pagination_class = StandardPagination

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def perform_destroy(self, instance):
        if instance.is_system:
            raise ValidationError('系统内置模板不可删除')
        instance.delete()
