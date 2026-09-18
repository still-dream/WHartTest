"""
操作日志筛选器：支持用户名/用户ID/功能点精确匹配 + 创建时间范围筛选。
"""
import django_filters
from .models import OperationLog


class OperationLogFilter(django_filters.FilterSet):
    """
    操作日志筛选器

    支持的 query 参数：
    - username: 精确匹配（不区分大小写）
    - user: 用户 ID
    - feature: 精确匹配
    - created_at__gte: 大于等于（ISO / YYYY-MM-DD HH:mm:ss）
    - created_at__lte: 小于等于
    """
    # 忽略大小写
    username = django_filters.CharFilter(field_name='username', lookup_expr='iexact')
    # 显式声明 created_at 范围 lookup
    created_at__gte = django_filters.IsoDateTimeFilter(
        field_name='created_at', lookup_expr='gte'
    )
    created_at__lte = django_filters.IsoDateTimeFilter(
        field_name='created_at', lookup_expr='lte'
    )

    class Meta:
        model = OperationLog
        fields = ['user', 'feature']
