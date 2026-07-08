# -*- coding: utf-8 -*-
"""APPUI 自动化视图"""

import os
import zipfile

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models.deletion import ProtectedError
from django.conf import settings
from django.http import FileResponse

from .models import (
    AppUiModule, AppUiScript, AppUiDevice,
    AppUiExecutionRecord, AppUiBatchExecutionRecord
)
from .serializers import (
    AppUiModuleSerializer, AppUiScriptSerializer, AppUiDeviceSerializer,
    AppUiExecutionRecordSerializer, AppUiBatchExecutionRecordSerializer
)
from .tasks import execute_app_ui_script


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
        """解压 zip 包并识别 .py 入口文件"""
        if not instance.script_file:
            return
        zip_path = instance.script_file.path
        extract_dir = os.path.join(
            settings.MEDIA_ROOT,
            f'app_ui_scripts/{instance.project.id}/{instance.id}'
        )
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        # 查找 .air 目录
        air_dirs = [d for d in os.listdir(extract_dir) if d.endswith('.air')]
        if air_dirs:
            air_dir = air_dirs[0]
            instance.script_dir = f'app_ui_scripts/{instance.project.id}/{instance.id}/{air_dir}'
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


class AppUiExecutionRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """执行记录视图"""
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
        filename = f"{record.script.name}_{record.created_at.strftime('%Y%m%d_%H%M%S')}.html"
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
