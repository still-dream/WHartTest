# -*- coding: utf-8 -*-
"""APPUI 自动化数据模型"""

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
