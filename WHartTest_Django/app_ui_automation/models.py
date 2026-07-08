# -*- coding: utf-8 -*-
"""APPUI 自动化数据模型"""

import os

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
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
        help_text=_('上传 .air 目录打包的 zip 文件'))
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
