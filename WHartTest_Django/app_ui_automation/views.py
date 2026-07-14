# -*- coding: utf-8 -*-
"""APPUI 自动化视图"""

import os
import zipfile
from datetime import datetime

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.mixins import DestroyModelMixin
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework_simplejwt.authentication import JWTAuthentication
from api_keys.authentication import APIKeyAuthentication
from django.db.models.deletion import ProtectedError
from django.conf import settings
from django.http import FileResponse

from .models import (
    AppUiModule, AppUiScript, AppUiDevice,
    AppUiExecutionRecord, AppUiBatchExecutionRecord,
    AppUiExecutionConfig
)
from .serializers import (
    AppUiModuleSerializer, AppUiScriptSerializer, AppUiDeviceSerializer,
    AppUiExecutionRecordSerializer, AppUiBatchExecutionRecordSerializer,
    AppUiExecutionConfigSerializer
)
from .tasks import execute_app_ui_script


class QueryParamJWTAuthentication(JWTAuthentication):
    """扩展 JWT 认证，支持通过 URL query parameter ?token=xxx 传递 token。
    用于 window.open() 等无法设置 Authorization header 的场景。"""

    def authenticate(self, request):
        # 先尝试标准 header 认证
        auth = super().authenticate(request)
        if auth is not None:
            return auth
        # header 认证失败，尝试 query parameter
        token = request.query_params.get('token')
        if token:
            try:
                raw_token = token.encode() if isinstance(token, str) else token
                validated_token = self.get_validated_token(raw_token)
                return (self.get_user(validated_token), validated_token)
            except Exception:
                return None
        return None


class AppUiModuleViewSet(viewsets.ModelViewSet):
    """模块管理视图"""
    queryset = AppUiModule.objects.select_related('project', 'parent', 'creator')
    serializer_class = AppUiModuleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'parent', 'level']
    search_fields = ['name']
    ordering_fields = ['name', 'level', 'created_at']
    ordering = ['level', 'name']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {'error': '存在关联脚本，无法删除。请先解除关联'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取模块树形结构"""
        project_id = request.query_params.get('project')
        if not project_id:
            return Response({'error': 'project 参数必填'}, status=status.HTTP_400_BAD_REQUEST)
        modules = AppUiModule.objects.filter(project_id=project_id, parent__isnull=True)
        serializer = self.get_serializer(modules, many=True)
        return Response(serializer.data)


class AppUiScriptViewSet(viewsets.ModelViewSet):
    """脚本管理视图"""
    queryset = AppUiScript.objects.select_related('project', 'module', 'creator')
    serializer_class = AppUiScriptSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'module', 'platform', 'status']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        instance = serializer.save(creator=self.request.user)
        self._extract_and_parse(instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        if 'script_file' in serializer.validated_data:
            self._extract_and_parse(instance)

    def _extract_and_parse(self, instance):
        """解析脚本文件并识别 .py 入口文件，支持 .zip/.air/.py 格式"""
        if not instance.script_file:
            return
        file_path = instance.script_file.path
        file_ext = os.path.splitext(file_path)[1].lower()
        script_base_dir = f'app_ui_scripts/{instance.project.id}/{instance.id}'
        extract_dir = os.path.join(settings.MEDIA_ROOT, script_base_dir)
        os.makedirs(extract_dir, exist_ok=True)

        if file_ext == '.py':
            # 单个 .py 脚本，直接作为入口文件
            instance.script_dir = script_base_dir
            instance.script_entry = os.path.basename(file_path)
            instance.save()
            return

        # .zip 或 .air 文件，按 zip 解压
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                zf.extractall(extract_dir)
        except zipfile.BadZipFile:
            instance.status = 'failed'
            instance.save()
            return

        # 查找 .air 目录
        air_dirs = [d for d in os.listdir(extract_dir)
                    if d.endswith('.air') and os.path.isdir(os.path.join(extract_dir, d))]
        if air_dirs:
            air_dir = air_dirs[0]
            instance.script_dir = f'{script_base_dir}/{air_dir}'
            py_name = air_dir.replace('.air', '.py')
            py_path = os.path.join(extract_dir, air_dir, py_name)
            if os.path.isfile(py_path):
                instance.script_entry = py_name
            else:
                for f in os.listdir(os.path.join(extract_dir, air_dir)):
                    if f.endswith('.py'):
                        instance.script_entry = f
                        break
            instance.save()
            return

        # 没有 .air 目录，查找解压目录下的 .py 文件
        py_files = [f for f in os.listdir(extract_dir)
                    if f.endswith('.py') and os.path.isfile(os.path.join(extract_dir, f))]
        if py_files:
            instance.script_dir = script_base_dir
            instance.script_entry = py_files[0]
            instance.save()
        else:
            instance.status = 'failed'
            instance.save()

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """预览脚本源码"""
        script = self.get_object()
        if not script.script_dir or not script.script_entry:
            return Response({'error': '脚本未正确解析'}, status=status.HTTP_400_BAD_REQUEST)
        py_path = os.path.join(settings.MEDIA_ROOT, script.script_dir, script.script_entry)
        if not os.path.isfile(py_path):
            return Response({'error': '脚本文件不存在'}, status=status.HTTP_404_NOT_FOUND)
        with open(py_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response({'content': content, 'entry': script.script_entry})

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """执行单个脚本（调试）"""
        script = self.get_object()
        device_id = request.data.get('device_id')
        trigger_type = request.data.get('trigger_type', 'debug')
        device = None
        if device_id:
            try:
                device = AppUiDevice.objects.get(id=device_id, project=script.project)
            except AppUiDevice.DoesNotExist:
                return Response({'error': '设备不存在'}, status=status.HTTP_404_NOT_FOUND)
        record = AppUiExecutionRecord.objects.create(
            script=script, device=device,
            trigger_type=trigger_type,
            executor=request.user,
            status=0,
        )
        task = execute_app_ui_script.delay(record.id)
        record.celery_task_id = task.id
        record.status = 1
        record.save()
        return Response({
            'id': record.id, 'status': record.status,
            'celery_task_id': task.id, 'message': '脚本已开始执行'
        })


class AppUiDeviceViewSet(viewsets.ModelViewSet):
    """设备管理视图"""
    queryset = AppUiDevice.objects.select_related('project', 'creator')
    serializer_class = AppUiDeviceSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'platform', 'connection_type', 'status']
    search_fields = ['name', 'device_serial', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['project', 'name']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(detail=True, methods=['post'])
    def check(self, request, pk=None):
        """检测设备连接状态"""
        device = self.get_object()
        try:
            from airtest.core.api import connect_device
            connect_device(device.device_uri)
            device.status = 'online'
            device.save()
            return Response({'status': 'online', 'message': '设备连接成功'})
        except Exception as e:
            device.status = 'offline'
            device.save()
            return Response({'status': 'offline', 'message': f'连接失败: {str(e)}'})


class AppUiExecutionRecordViewSet(DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    """执行记录视图"""
    authentication_classes = [QueryParamJWTAuthentication, APIKeyAuthentication]
    queryset = AppUiExecutionRecord.objects.select_related('script', 'device', 'executor')
    serializer_class = AppUiExecutionRecordSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['script', 'device', 'status', 'trigger_type']
    ordering_fields = ['created_at', 'duration']
    ordering = ['-created_at']

    @action(detail=True, methods=['get'])
    def report(self, request, pk=None):
        """在线查看报告"""
        record = self.get_object()
        if not record.report_path:
            return Response({'error': '报告尚未生成'}, status=status.HTTP_404_NOT_FOUND)
        html_path = os.path.join(settings.MEDIA_ROOT, record.report_path)
        if not os.path.isfile(html_path):
            return Response({'error': '报告文件不存在'}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(open(html_path, 'rb'), content_type='text/html')

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """下载报告"""
        record = self.get_object()
        if not record.report_path:
            return Response({'error': '报告尚未生成'}, status=status.HTTP_404_NOT_FOUND)
        html_path = os.path.join(settings.MEDIA_ROOT, record.report_path)
        if not os.path.isfile(html_path):
            return Response({'error': '报告文件不存在'}, status=status.HTTP_404_NOT_FOUND)
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{record.id}.html"
        response = FileResponse(open(html_path, 'rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消执行"""
        record = self.get_object()
        if record.status != 1:
            return Response({'error': '当前状态不可取消'}, status=status.HTTP_400_BAD_REQUEST)
        from celery import current_app
        current_app.control.revoke(record.celery_task_id, terminate=True)
        record.status = 4
        record.save()
        return Response({'status': 'cancelled', 'message': '任务已取消'})


class AppUiBatchExecutionRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """批量执行记录视图"""
    queryset = AppUiBatchExecutionRecord.objects.select_related('executor')
    serializer_class = AppUiBatchExecutionRecordSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'trigger_type']
    ordering_fields = ['created_at']
    ordering = ['-created_at']


class AppUiExecutionConfigViewSet(viewsets.ViewSet):
    """执行配置视图（全局单例）"""
    queryset = AppUiExecutionConfig.objects.all()
    def retrieve(self, request, pk=None):
        config = AppUiExecutionConfig.get_config()
        serializer = AppUiExecutionConfigSerializer(config)
        return Response(serializer.data)

    def update(self, request, pk=None):
        config = AppUiExecutionConfig.get_config()
        old_poco_timeout = config.poco_wait_timeout
        serializer = AppUiExecutionConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        # 检测 poco_wait_timeout 是否变更（需重连才生效）
        needs_reconnect = serializer.validated_data.get('poco_wait_timeout') is not None \
            and serializer.validated_data.get('poco_wait_timeout') != old_poco_timeout
        data = serializer.data
        data['needs_reconnect'] = needs_reconnect
        return Response(data)

    def partial_update(self, request, pk=None):
        return self.update(request, pk=pk)
