from django.db import models
from django.contrib.auth.models import User


class WebhookAddress(models.Model):
    """飞书 Webhook 推送地址（全局，仅管理员管理）"""

    PLATFORM_CHOICES = [('feishu', '飞书')]

    name = models.CharField('地址名称', max_length=100)
    url = models.URLField('Webhook URL')
    platform_type = models.CharField(
        '平台类型', max_length=20, choices=PLATFORM_CHOICES, default='feishu'
    )
    description = models.TextField('描述', blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='创建人', related_name='created_webhook_addresses'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '推送地址'
        verbose_name_plural = '推送地址'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class MessageTemplate(models.Model):
    """消息模板库（所有用户可维护）"""

    PLATFORM_CHOICES = [('feishu', '飞书')]

    name = models.CharField('模板名称', max_length=100)
    content = models.TextField(
        '模板内容', help_text='Markdown格式，支持{{变量}}占位符'
    )
    platform_type = models.CharField(
        '平台类型', max_length=20, choices=PLATFORM_CHOICES, default='feishu'
    )
    description = models.TextField('描述', blank=True, default='')
    is_system = models.BooleanField('系统内置', default=False)
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE,
        verbose_name='创建人', related_name='created_message_templates'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '消息模板'
        verbose_name_plural = '消息模板'
        ordering = ['-is_system', '-created_at']

    def __str__(self):
        return self.name
