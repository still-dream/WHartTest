# -*- coding: utf-8 -*-
"""APPUI 自动化数据模型"""

import os

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from projects.models import Project


class AppUiModule(models.Model):
    """APPUI 自动化模块，支持5级子模块"""
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='app_ui_modules', verbose_name=_('所属项目')
    )
    name = models.CharField(_('模块名称'), max_length=100)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children', verbose_name=_('父模块')
    )
    level = models.PositiveSmallIntegerField(_('模块级别'), default=1)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_app_ui_modules', verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('APPUI 模块')
        verbose_name_plural = _('APPUI 模块')
        ordering = ['project', 'level', 'name']
        unique_together = ('project', 'parent', 'name')
        db_table = 'app_ui_module'

    def __str__(self):
        return f"{self.parent} > {self.name}" if self.parent else self.name

    def clean(self):
        if self.level > 5:
            raise ValidationError(_('模块级别不能超过5级'))
        if self.parent and self.parent.project_id != self.project_id:
            raise ValidationError(_('父模块必须属于同一个项目'))
        self.level = (self.parent.level + 1) if self.parent else 1

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


def app_ui_script_path(instance, filename):
    """脚本文件存储路径: app_ui_scripts/{project_id}/{script_id}/"""
    return f"app_ui_scripts/{instance.project.id}/{instance.id}/{filename}"


class AppUiScript(models.Model):
    """APPUI Airtest 脚本"""
    PLATFORM_CHOICES = [('android', _('Android')), ('ios', _('iOS'))]
    STATUS_CHOICES = [
        ('idle', _('空闲')), ('running', _('执行中')),
        ('success', _('成功')), ('failed', _('失败')),
    ]
    LEVEL_CHOICES = [('P0', 'P0'), ('P1', 'P1'), ('P2', 'P2'), ('P3', 'P3')]

    project = models.ForeignKey(Project, on_delete=models.CASCADE,
        related_name='app_ui_scripts', verbose_name=_('所属项目'))
    module = models.ForeignKey(AppUiModule, on_delete=models.PROTECT,
        related_name='scripts', verbose_name=_('所属模块'))
    name = models.CharField(_('脚本名称'), max_length=255)
    description = models.TextField(_('脚本描述'), blank=True, null=True)
    platform = models.CharField(_('目标平台'), max_length=10,
        choices=PLATFORM_CHOICES, default='android')
    script_file = models.FileField(_('Airtest脚本包'), upload_to=app_ui_script_path,
        help_text=_('上传 .zip、.air 或 .py 脚本文件'))
    script_dir = models.CharField(_('脚本目录路径'), max_length=500, blank=True, default='')
    script_entry = models.CharField(_('脚本入口文件'), max_length=255, blank=True, default='')
    level = models.CharField(_('用例等级'), max_length=2, choices=LEVEL_CHOICES, default='P2')
    status = models.CharField(_('最近状态'), max_length=10, choices=STATUS_CHOICES, default='idle')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
        related_name='created_app_ui_scripts', verbose_name=_('创建人'))
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('APPUI 脚本')
        verbose_name_plural = _('APPUI 脚本')
        ordering = ['-created_at']
        db_table = 'app_ui_script'

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    def delete(self, *args, **kwargs):
        if self.script_file:
            path = self.script_file.path
            if os.path.isfile(path):
                os.remove(path)
        if self.script_dir:
            import shutil
            full_dir = os.path.join(settings.MEDIA_ROOT, self.script_dir)
            if os.path.isdir(full_dir):
                shutil.rmtree(full_dir, ignore_errors=True)
        super().delete(*args, **kwargs)


class AppUiDevice(models.Model):
    """APPUI 测试设备管理"""
    CONNECTION_TYPE_CHOICES = [
        ('adb_tcp', _('ADB TCP 远程')),
        ('emulator', _('Android 模拟器')),
        ('cloud', _('云真机平台')),
        ('usb', _('USB 直连')),
    ]
    PLATFORM_CHOICES = [('android', _('Android')), ('ios', _('iOS'))]
    STATUS_CHOICES = [('online', _('在线')), ('offline', _('离线')), ('busy', _('忙碌'))]

    project = models.ForeignKey(Project, on_delete=models.CASCADE,
        related_name='app_ui_devices', verbose_name=_('所属项目'))
    name = models.CharField(_('设备名称'), max_length=100, help_text=_('如：测试机-小米12'))
    connection_type = models.CharField(_('连接类型'), max_length=20,
        choices=CONNECTION_TYPE_CHOICES, default='adb_tcp')
    platform = models.CharField(_('平台'), max_length=10,
        choices=PLATFORM_CHOICES, default='android')
    device_uri = models.CharField(_('设备连接URI'), max_length=500,
        help_text=_('Android: android://127.0.0.1:5037/序列号; iOS: ios:///127.0.0.1:8100'))
    device_serial = models.CharField(_('设备序列号'), max_length=255, blank=True, default='')
    status = models.CharField(_('设备状态'), max_length=10,
        choices=STATUS_CHOICES, default='offline')
    description = models.TextField(_('设备描述'), blank=True, null=True)
    is_default = models.BooleanField(_('是否默认'), default=False)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
        related_name='created_app_ui_devices', verbose_name=_('创建人'))
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('APPUI 设备')
        verbose_name_plural = _('APPUI 设备')
        ordering = ['project', 'name']
        unique_together = ('project', 'name')
        db_table = 'app_ui_device'

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class AppUiBatchExecutionRecord(models.Model):
    """APPUI 批量执行记录"""
    STATUS_CHOICES = [
        (0, _('待执行')), (1, _('执行中')),
        (2, _('全部成功')), (3, _('部分失败')), (4, _('全部失败')),
    ]
    TRIGGER_TYPE_CHOICES = [('manual', _('手动')), ('scheduled', _('定时')), ('api', _('API'))]

    name = models.CharField(_('批次名称'), max_length=255)
    total_scripts = models.IntegerField(_('脚本总数'), default=0)
    passed_scripts = models.IntegerField(_('成功数'), default=0)
    failed_scripts = models.IntegerField(_('失败数'), default=0)
    status = models.SmallIntegerField(_('状态'), choices=STATUS_CHOICES, default=0)
    trigger_type = models.CharField(_('触发类型'), max_length=20,
        choices=TRIGGER_TYPE_CHOICES, default='manual')
    executor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
        related_name='app_ui_batch_executions', verbose_name=_('执行人'))
    start_time = models.DateTimeField(_('开始时间'), null=True, blank=True)
    end_time = models.DateTimeField(_('结束时间'), null=True, blank=True)
    duration = models.FloatField(_('总时长（秒）'), null=True, blank=True)
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('APPUI 批量执行记录')
        verbose_name_plural = _('APPUI 批量执行记录')
        ordering = ['-created_at']
        db_table = 'app_ui_batch_execution_record'

    def __str__(self):
        return f"{self.name} ({self.passed_scripts}/{self.total_scripts})"

    def update_statistics(self):
        records = self.execution_records.all()
        self.passed_scripts = records.filter(status=2).count()
        self.failed_scripts = records.filter(status=3).count()
        completed = self.passed_scripts + self.failed_scripts
        if completed >= self.total_scripts:
            if self.failed_scripts == 0:
                self.status = 2
            elif self.passed_scripts == 0:
                self.status = 4
            else:
                self.status = 3
            from django.utils import timezone
            self.end_time = timezone.now()
            if self.start_time:
                self.duration = (self.end_time - self.start_time).total_seconds()
        self.save()


class AppUiExecutionRecord(models.Model):
    """APPUI 脚本执行记录"""
    STATUS_CHOICES = [(0, _('等待中')), (1, _('执行中')), (2, _('成功')), (3, _('失败')), (4, _('取消'))]
    TRIGGER_TYPE_CHOICES = [('manual', _('手动')), ('scheduled', _('定时')), ('api', _('API')), ('debug', _('调试'))]

    batch = models.ForeignKey(AppUiBatchExecutionRecord, on_delete=models.CASCADE,
        null=True, blank=True, related_name='execution_records', verbose_name=_('所属批次'))
    script = models.ForeignKey(AppUiScript, on_delete=models.CASCADE,
        related_name='execution_records', verbose_name=_('执行脚本'))
    device = models.ForeignKey(AppUiDevice, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='execution_records', verbose_name=_('执行设备'))
    status = models.SmallIntegerField(_('执行状态'), choices=STATUS_CHOICES, default=0)
    trigger_type = models.CharField(_('触发类型'), max_length=20,
        choices=TRIGGER_TYPE_CHOICES, default='manual')
    executor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
        related_name='app_ui_executions', verbose_name=_('执行人'))
    total_steps = models.IntegerField(_('总步骤数'), default=0)
    passed_steps = models.IntegerField(_('通过步骤数'), default=0)
    failed_steps = models.IntegerField(_('失败步骤数'), default=0)
    report_path = models.CharField(_('报告文件路径'), max_length=500, blank=True, default='')
    log_dir = models.CharField(_('日志目录路径'), max_length=500, blank=True, default='')
    execution_log = models.TextField(_('执行日志'), blank=True, null=True)
    error_message = models.TextField(_('错误信息'), null=True, blank=True)
    start_time = models.DateTimeField(_('开始时间'), null=True, blank=True)
    end_time = models.DateTimeField(_('结束时间'), null=True, blank=True)
    duration = models.FloatField(_('执行时长（秒）'), null=True, blank=True)
    celery_task_id = models.CharField(_('Celery任务ID'), max_length=255, blank=True, default='')
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('APPUI 执行记录')
        verbose_name_plural = _('APPUI 执行记录')
        ordering = ['-created_at']
        db_table = 'app_ui_execution_record'

    def __str__(self):
        return f"{self.script.name} - {self.get_status_display()}"


class AppUiExecutionConfig(models.Model):
    """APPUI 执行配置（全局单例）"""
    airtest_threshold = models.FloatField(_('图像匹配阈值'), default=0.6,
        help_text=_('0-1 之间，值越低匹配越宽松'))
    airtest_find_timeout = models.IntegerField(_('元素查找超时（秒）'), default=30)
    airtest_opdelay = models.FloatField(_('操作间隔延迟（秒）'), default=1.0)
    poco_wait_timeout = models.IntegerField(_('Poco元素等待超时（秒）'), default=20,
        help_text=_('修改后需重新连接设备才生效'))
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
        related_name='app_ui_config_updates', verbose_name=_('更新人'))
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('APPUI 执行配置')
        verbose_name_plural = _('APPUI 执行配置')
        db_table = 'app_ui_execution_config'

    def __str__(self):
        return f"APPUI执行配置 (阈值={self.airtest_threshold}, 超时={self.airtest_find_timeout}s)"

    @classmethod
    def get_config(cls):
        """获取全局配置（单例）"""
        config, _ = cls.objects.get_or_create(id=1)
        return config


# ============================================================
# APP 应用分发管理（APK 上传 + 自动清理）
# ============================================================

class AppPackage(models.Model):
    """APP 应用（按包名归一）"""
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='app_packages', verbose_name=_('所属项目')
    )
    platform = models.CharField(_('平台'), max_length=10, default='android')
    package_name = models.CharField(_('包名'), max_length=200, db_index=True,
        help_text=_('例如：com.example.app'))
    app_name = models.CharField(_('应用名称'), max_length=200, blank=True, default='')
    icon = models.ImageField(_('图标'), upload_to='app_icons/', null=True, blank=True)
    description = models.TextField(_('应用描述'), blank=True, default='')
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_app_packages', verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('APP 应用')
        verbose_name_plural = _('APP 应用')
        ordering = ['-updated_at']
        unique_together = ('project', 'package_name')
        db_table = 'app_package'

    def __str__(self):
        return f"{self.app_name or self.package_name} ({self.package_name})"

    @property
    def latest_version(self):
        return self.versions.order_by('-version_code').first()

    @property
    def total_versions(self):
        return self.versions.count()


class AppPackageVersion(models.Model):
    """APP 应用版本（APK 文件）"""
    STATUS_CHOICES = [
        ('draft', _('草稿')),
        ('released', _('已发布')),
        ('deprecated', _('已废弃')),
        ('prerelease', _('预发布')),
    ]
    PARSE_STATUS_CHOICES = [
        ('pending', _('待解析')),
        ('parsing', _('解析中')),
        ('success', _('解析成功')),
        ('failed', _('解析失败')),
    ]
    RETENTION_DAYS = 30  # APK 文件保留天数（自动清理）

    package = models.ForeignKey(
        AppPackage, on_delete=models.CASCADE,
        related_name='versions', verbose_name=_('所属应用')
    )
    version_name = models.CharField(_('版本号'), max_length=50,
        help_text=_('如：1.2.3'))
    version_code = models.IntegerField(_('版本代码'),
        help_text=_('如：123'))
    apk_file = models.FileField(_('APK 文件'), upload_to='app_packages/')
    file_size = models.BigIntegerField(_('文件大小(字节)'), default=0)
    file_md5 = models.CharField(_('MD5'), max_length=32, blank=True, default='')
    file_sha1 = models.CharField(_('SHA1'), max_length=40, blank=True, default='')
    signature_sha1 = models.CharField(_('签名 SHA1'), max_length=100, blank=True, default='')
    signature_algorithm = models.CharField(_('签名算法'), max_length=50, blank=True, default='')
    target_sdk = models.IntegerField(_('目标 SDK'), null=True, blank=True)
    min_sdk = models.IntegerField(_('最低 SDK'), null=True, blank=True)
    permissions = models.JSONField(_('权限列表'), default=list)
    main_activity = models.CharField(_('启动 Activity'), max_length=300, blank=True, default='')
    abi_support = models.JSONField(_('支持 ABI'), default=list)
    changelog = models.TextField(_('版本说明'), blank=True, default='')
    status = models.CharField(_('状态'), max_length=20,
        choices=STATUS_CHOICES, default='released')
    is_latest = models.BooleanField(_('是否最新版本'), default=False)
    parse_status = models.CharField(_('解析状态'), max_length=20,
        choices=PARSE_STATUS_CHOICES, default='pending')
    parse_error = models.TextField(_('解析错误'), blank=True, default='')
    # 自动清理相关
    is_protected = models.BooleanField(_('受保护（不自动清理）'), default=False,
        help_text=_('勾选后即使超过保留期也不会被自动清理'))
    expire_at = models.DateTimeField(_('过期时间'), null=True, blank=True,
        help_text=_('达到该时间后将被自动清理，默认上传后 30 天'))
    cleaned_at = models.DateTimeField(_('清理时间'), null=True, blank=True,
        help_text=_('被自动清理的时间'))
    uploader = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='uploaded_app_versions', verbose_name=_('上传人')
    )
    created_at = models.DateTimeField(_('上传时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('APP 应用版本')
        verbose_name_plural = _('APP 应用版本')
        ordering = ['-version_code', '-created_at']
        unique_together = ('package', 'version_code')
        db_table = 'app_package_version'
        indexes = [
            models.Index(fields=['expire_at', 'is_protected']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.package.package_name} v{self.version_name} (code={self.version_code})"

    def save(self, *args, **kwargs):
        # 自动设置过期时间（首次保存时）
        if not self.expire_at:
            from datetime import timedelta
            self.expire_at = timezone.now() + timedelta(days=self.RETENTION_DAYS)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # 删除磁盘上的 APK 文件
        if self.apk_file:
            apk_path = self.apk_file.path if hasattr(self.apk_file, 'path') else None
            if apk_path and os.path.isfile(apk_path):
                try:
                    os.remove(apk_path)
                except OSError:
                    pass
        super().delete(*args, **kwargs)

    @property
    def file_size_human(self):
        """人类可读的文件大小"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    @property
    def is_expired(self):
        """是否已过期（达到自动清理时间）"""
        if self.is_protected or not self.expire_at:
            return False
        return timezone.now() >= self.expire_at

    @property
    def days_to_expire(self):
        """距离过期还剩多少天（负数表示已过期）"""
        if not self.expire_at:
            return None
        delta = self.expire_at - timezone.now()
        return delta.days
