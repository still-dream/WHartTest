import logging
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from .models import OperationLog

User = get_user_model()
logger = logging.getLogger(__name__)


class OperationLogMiddleware(MiddlewareMixin):
    """
    操作日志中间件
    
    记录用户访问的功能点和时间
    """
    
    EXCLUDE_PATHS = [
        '/api/token/',
        '/api/token/refresh/',
        '/api/schema/',
        '/admin/',
        '/static/',
        '/media/',
        '/ws/',
    ]
    
    EXCLUDE_EXTENSIONS = [
        '.css',
        '.js',
        '.png',
        '.jpg',
        '.jpeg',
        '.gif',
        '.ico',
        '.svg',
        '.woff',
        '.woff2',
        '.ttf',
        '.eot',
    ]
    
    def process_request(self, request):
        request.operation_log_feature = None
        return None
    
    def process_response(self, request, response):
        try:
            if self._should_log(request, response):
                self._log_operation(request, response)
        except Exception as e:
            logger.error(f"记录操作日志失败: {e}", exc_info=True)
        
        return response
    
    def _should_log(self, request, response):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return False
        
        path = request.path
        
        for exclude_path in self.EXCLUDE_PATHS:
            if path.startswith(exclude_path):
                return False
        
        for ext in self.EXCLUDE_EXTENSIONS:
            if path.endswith(ext):
                return False
        
        if response.status_code >= 400:
            return False
        
        return True
    
    def _log_operation(self, request, response):
        feature = self._extract_feature(request)
        
        if not feature:
            return
        
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        try:
            OperationLog.objects.create(
                user=request.user,
                username=request.user.username,
                feature=feature,
                path=request.path,
                method=request.method,
                ip_address=ip_address,
                user_agent=user_agent
            )
        except Exception as e:
            logger.error(f"记录操作日志失败: {e}", exc_info=True)
    
    def _extract_feature(self, request):
        path = request.path
        
        if hasattr(request, 'operation_log_feature') and request.operation_log_feature:
            return request.operation_log_feature
        
        feature_mapping = {
            '/api/projects/': '项目管理',
            '/api/projects': '项目管理',
            '/api/requirements/': '需求管理',
            '/api/requirements': '需求管理',
            '/api/testcases/': '用例管理',
            '/api/testcase-modules/': '用例管理',
            '/api/test-suites/': '测试套件',
            '/api/test-executions/': '执行历史',
            '/api/automation-scripts/': 'UI脚本库',
            '/api/script-executions/': '脚本执行',
            '/api/knowledge/': '知识库管理',
            '/api/lg/': 'LLM对话',
            '/api/orchestrator/': '智能编排',
            '/api/prompts/': '提示词管理',
            '/api/accounts/users/': '用户管理',
            '/api/accounts/groups/': '组织管理',
            '/api/accounts/permissions/': '权限管理',
            '/api/llm-configs/': 'LLM配置',
            '/api/api-keys/': 'KEY管理',
            '/api/mcp_tools/': 'MCP配置',
            '/api/skills/': 'Skills管理',
            '/api/operation-logs/': '操作日志',
        }
        
        for pattern, feature_name in feature_mapping.items():
            if path.startswith(pattern):
                return feature_name
        
        if path.startswith('/api/'):
            return 'API访问'
        
        return None
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        return ip
