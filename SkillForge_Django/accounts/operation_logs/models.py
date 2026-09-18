from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class OperationLog(models.Model):
    """
    用户操作日志模型
    
    记录用户在系统中的操作访问记录
    """
    
    class Meta:
        db_table = 'operation_logs'
        verbose_name = '操作日志'
        verbose_name_plural = '操作日志'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='operation_logs',
        verbose_name='用户'
    )
    
    username = models.CharField(
        max_length=150,
        verbose_name='用户名',
        db_index=True
    )
    
    feature = models.CharField(
        max_length=200,
        verbose_name='功能点',
        db_index=True,
        help_text='用户访问的功能模块或页面'
    )
    
    path = models.CharField(
        max_length=500,
        verbose_name='访问路径',
        blank=True,
        null=True
    )
    
    method = models.CharField(
        max_length=10,
        verbose_name='请求方法',
        blank=True,
        null=True
    )
    
    ip_address = models.GenericIPAddressField(
        verbose_name='IP地址',
        blank=True,
        null=True
    )
    
    user_agent = models.TextField(
        verbose_name='用户代理',
        blank=True,
        null=True
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='访问时间',
        db_index=True
    )
    
    def __str__(self):
        return f"{self.username} - {self.feature} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
