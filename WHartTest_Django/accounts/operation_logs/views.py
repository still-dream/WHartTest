from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta
from .models import OperationLog
from .serializers import OperationLogSerializer


class OperationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    操作日志视图集
    
    提供操作日志的查询、筛选功能
    """
    queryset = OperationLog.objects.all()
    serializer_class = OperationLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['user', 'username', 'feature', 'created_at']
    search_fields = ['username', 'feature', 'path']
    ordering_fields = ['created_at', 'username', 'feature']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        user = self.request.user
        
        if user.is_superuser:
            return queryset
        else:
            return queryset.filter(user=user)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        获取操作日志统计信息
        
        返回：
        - 总访问次数
        - 今日访问次数
        - 本周访问次数
        - 本月访问次数
        - 活跃用户数
        """
        queryset = self.get_queryset()
        
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)
        
        total_count = queryset.count()
        today_count = queryset.filter(created_at__gte=today_start).count()
        week_count = queryset.filter(created_at__gte=week_start).count()
        month_count = queryset.filter(created_at__gte=month_start).count()
        
        active_users = queryset.values('user').distinct().count()
        
        return Response({
            'total_count': total_count,
            'today_count': today_count,
            'week_count': week_count,
            'month_count': month_count,
            'active_users': active_users
        })
    
    @action(detail=False, methods=['delete'])
    def clear_old_logs(self, request):
        """
        清理旧日志
        
        参数：
        - days: 保留最近多少天的日志（默认30天）
        """
        if not request.user.is_superuser:
            return Response(
                {'error': '只有管理员可以清理日志'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        days = int(request.query_params.get('days', 30))
        cutoff_date = timezone.now() - timedelta(days=days)
        
        deleted_count, _ = OperationLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        return Response({
            'message': f'已清理 {deleted_count} 条 {days} 天前的日志记录',
            'deleted_count': deleted_count
        })
