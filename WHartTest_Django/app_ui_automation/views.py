# -*- coding: utf-8 -*-
"""APPUI 自动化视图"""

import os
import zipfile
import hashlib
import logging
from datetime import datetime
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.mixins import DestroyModelMixin
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from api_keys.authentication import APIKeyAuthentication
from django.db.models.deletion import ProtectedError
from django.conf import settings
from django.core import signing
from django.http import FileResponse, HttpResponseForbidden, HttpResponseNotFound

from .models import (
    AppUiModule, AppUiScript, AppUiDevice,
    AppUiExecutionRecord, AppUiBatchExecutionRecord,
    AppUiExecutionConfig,
    AppPackage, AppPackageVersion,
)
from .serializers import (
    AppUiModuleSerializer, AppUiScriptSerializer, AppUiDeviceSerializer,
    AppUiExecutionRecordSerializer, AppUiBatchExecutionRecordSerializer,
    AppUiExecutionConfigSerializer,
    AppPackageSerializer, AppPackageVersionSerializer,
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


# ============================================================
# APP 应用分发管理 视图
# ============================================================

logger = logging.getLogger(__name__)


def _calc_file_hashes(file_obj):
    """计算上传文件的 MD5/SHA1"""
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    file_obj.seek(0)
    for chunk in iter(lambda: file_obj.read(8192), b''):
        md5.update(chunk)
        sha1.update(chunk)
    file_obj.seek(0)
    return md5.hexdigest(), sha1.hexdigest()


class AppPackageViewSet(viewsets.ModelViewSet):
    """APP 应用（按包名归一）"""
    queryset = AppPackage.objects.all()
    serializer_class = AppPackageSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['package_name', 'app_name', 'description']
    ordering_fields = ['updated_at', 'created_at']
    ordering = ['-updated_at']

    def get_queryset(self):
        qs = super().get_queryset().select_related('project', 'creator')
        project = self.request.query_params.get('project')
        if project:
            qs = qs.filter(project_id=project)
        platform = self.request.query_params.get('platform')
        if platform:
            qs = qs.filter(platform=platform)
        return qs

    @action(detail=True, methods=['get'], url_path='versions')
    def list_versions(self, request, pk=None):
        """列出指定 APP 下的所有版本（含受保护/清理状态）"""
        pkg = self.get_object()
        qs = pkg.versions.all().order_by('-version_code')
        serializer = AppPackageVersionSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class AppPackageVersionViewSet(viewsets.ModelViewSet):
    """APP 应用版本（APK 文件）"""
    queryset = AppPackageVersion.objects.all()
    serializer_class = AppPackageVersionSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = super().get_queryset().select_related('package', 'uploader')
        # 支持过滤: ?package=1&is_protected=true&expired=true
        package = self.request.query_params.get('package')
        if package:
            qs = qs.filter(package_id=package)
        is_protected = self.request.query_params.get('is_protected')
        if is_protected is not None:
            qs = qs.filter(is_protected=is_protected.lower() == 'true')
        if self.request.query_params.get('expired') == 'true':
            qs = qs.filter(expire_at__lte=timezone.now(), is_protected=False, cleaned_at__isnull=True)
        return qs

    def create(self, request, *args, **kwargs):
        """上传新版本 (multipart/form-data)"""
        package_id = request.data.get('package')
        if not package_id:
            return Response({'detail': '缺少 package 参数'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pkg = AppPackage.objects.get(id=package_id)
        except AppPackage.DoesNotExist:
            return Response({'detail': 'APP 不存在'}, status=status.HTTP_404_NOT_FOUND)

        apk_file = request.FILES.get('apk_file')
        if not apk_file:
            return Response({'detail': '请上传 APK 文件'}, status=status.HTTP_400_BAD_REQUEST)

        # 校验文件类型
        if not apk_file.name.lower().endswith('.apk'):
            return Response({'detail': '只支持 .apk 格式'}, status=status.HTTP_400_BAD_REQUEST)

        # 校验大小（500MB）
        if apk_file.size > 500 * 1024 * 1024:
            return Response({'detail': '文件超过 500MB 限制'}, status=status.HTTP_400_BAD_REQUEST)

        # 计算哈希
        md5, sha1 = _calc_file_hashes(apk_file)

        # 创建版本记录
        try:
            version_code = int(request.data.get('version_code', 0))
        except (TypeError, ValueError):
            version_code = 0

        if not version_code:
            return Response({'detail': '请提供有效的 version_code'}, status=status.HTTP_400_BAD_REQUEST)

        version = AppPackageVersion(
            package=pkg,
            version_name=request.data.get('version_name', ''),
            version_code=version_code,
            apk_file=apk_file,
            file_size=apk_file.size,
            file_md5=md5,
            file_sha1=sha1,
            changelog=request.data.get('changelog', ''),
            status=request.data.get('status', 'released'),
            is_protected=str(request.data.get('is_protected', 'false')).lower() == 'true',
            uploader=request.user if request.user.is_authenticated else None,
            parse_status='pending',
        )
        try:
            version.save()
        except Exception as e:
            logger.exception('保存 APK 版本失败: %s', e)
            return Response({'detail': f'保存失败: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = AppPackageVersionSerializer(version, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='protect')
    def toggle_protection(self, request, pk=None):
        """切换受保护状态"""
        version = self.get_object()
        is_protected = bool(request.data.get('is_protected', False))
        version.is_protected = is_protected
        # 如果重新受保护，重置清理时间
        if is_protected:
            version.cleaned_at = None
        version.save(update_fields=['is_protected', 'cleaned_at', 'updated_at'])
        serializer = AppPackageVersionSerializer(version, context={'request': request})
        return Response(serializer.data)


def _get_cleanup_status():
    """获取清理任务状态（下次运行时间、上次运行时间、累计统计）"""
    from django_celery_beat.models import PeriodicTask

    task_name = 'app_ui_automation.cleanup_apks_daily'
    last_run = None
    try:
        pt = PeriodicTask.objects.filter(name=task_name).first()
        if pt and pt.last_run_at:
            last_run = pt.last_run_at.isoformat()
    except Exception:
        pass

    # 统计当前可清理的数量
    now = timezone.now()
    pending = AppPackageVersion.objects.filter(
        is_protected=False,
        cleaned_at__isnull=True,
        expire_at__lte=now,
    ).count()

    return {
        'retention_days': AppPackageVersion.RETENTION_DAYS,
        'next_run_at': None,  # 下次运行时间由前端通过 crontab 描述展示
        'last_run_at': last_run,
        'total_cleaned': pending,  # 当前待清理
        'total_freed_bytes': 0,
    }


class AppCleanupViewSet(viewsets.ViewSet):
    """APK 自动清理相关接口"""

    @action(detail=False, methods=['get'], url_path='cleanup-config')
    def cleanup_config(self, request):
        """获取清理配置"""
        return Response(_get_cleanup_status())

    @action(detail=False, methods=['post'], url_path='cleanup')
    def run_cleanup(self, request):
        """手动触发清理任务

        Body: {"dry_run": true/false}
        """
        dry_run = bool(request.data.get('dry_run', False))

        from .tasks import cleanup_expired_apks
        if dry_run:
            # 同步执行 dry_run，立即返回结果
            result = cleanup_expired_apks.apply(args=[True]).get()
            return Response(result)

        # 异步执行，立即返回
        task = cleanup_expired_apks.delay(dry_run=False)
        return Response({
            'task_id': task.id,
            'status': 'started',
            'message': '清理任务已启动，请稍后查看结果',
        })


# 报告签名 token 有效期（30 天）
REPORT_TOKEN_MAX_AGE = 30 * 24 * 3600


def public_report_view(request):
    """公开访问测试报告（通过签名 token 认证，无需登录）。

    用于飞书消息中的报告链接，token 由 notifications.variables 生成。
    """
    token = request.GET.get('token')
    if not token:
        return HttpResponseForbidden('缺少访问令牌')

    try:
        data = signing.loads(token, max_age=REPORT_TOKEN_MAX_AGE)
    except signing.SignatureExpired:
        return HttpResponseForbidden('链接已过期')
    except signing.BadSignature:
        return HttpResponseForbidden('无效的访问链接')

    record_id = data.get('record_id')
    if not record_id:
        return HttpResponseForbidden('无效的访问链接')

    try:
        record = AppUiExecutionRecord.objects.get(id=record_id)
    except AppUiExecutionRecord.DoesNotExist:
        return HttpResponseNotFound('报告记录不存在')

    if not record.report_path:
        return HttpResponseNotFound('报告尚未生成')

    html_path = os.path.join(settings.MEDIA_ROOT, record.report_path)
    if not os.path.isfile(html_path):
        return HttpResponseNotFound('报告文件不存在')

    return FileResponse(open(html_path, 'rb'), content_type='text/html')
