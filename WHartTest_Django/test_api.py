import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'wharttest_django.settings'

import django
django.setup()

from rest_framework.test import APIRequestFactory, force_authenticate
from requirements.views import RequirementDocumentViewSet
from django.contrib.auth.models import User

user = User.objects.get(username='admin')
factory = APIRequestFactory()

# 创建请求
request = factory.get('/api/requirements/documents/1f1e59ed-0b35-4ba9-8b28-a769c5f935ad/export-report/', {'format': 'pdf'})
force_authenticate(request, user=user)

# 使用 as_view
view_func = RequirementDocumentViewSet.as_view({'get': 'export_report'})

# 检查 view_func 的属性
print('view_func:', view_func)
print('view_func actions:', view_func.actions if hasattr(view_func, 'actions') else 'No actions')

# 调用视图
response = view_func(request, pk='1f1e59ed-0b35-4ba9-8b28-a769c5f935ad')
print('Response status:', response.status_code)
