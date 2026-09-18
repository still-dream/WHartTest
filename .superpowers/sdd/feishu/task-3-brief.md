## Task 3: 后端视图与路由（TDD）

**Files:**

- Modify: `SkillForge_Django\accounts\views.py`（新增 import + 文件末尾追加视图）
- Modify: `SkillForge_Django\accounts\urls.py`（`me/` 路由之后插两条）
- Modify: `SkillForge_Django\accounts\tests.py`（末尾追加视图测试类）

**Interfaces:**

- Consumes（来自 Task 2）：`FeishuAuthError` / `build_authorize_url` / `build_state` / `exchange_code_for_token` / `get_feishu_user` / `verify_state`
- Consumes（已存在）：`UserDetailSerializer`（`views.py` 第 19 行已导入）、`User`（第 1 行已导入）、`OperationalError`（第 4 行已导入）、`AllowAny`（第 9 行已导入）
- Produces：
  - `GET /api/accounts/feishu/authorize-url/` → 200 `{authorize_url: str, state: str}`；未配置应用 → 503
  - `POST /api/accounts/feishu/login/` 请求体 `{code: str, state: str}` → 200 `{access, refresh, user}`（命中统一渲染 token 分支）；失败 400 `{detail}`；数据库未就绪 503
- Produces（供 Task 4 前端）：上述两个 URL

**Step 1: 写失败测试**

在 `accounts\tests.py` 顶部导入区补齐（与 Task 2 修改合并后的最终形态）：

```python
import time
from unittest.mock import patch
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory

from accounts.feishu import (
    FeishuAuthError,
    build_authorize_url,
    build_state,
    exchange_code_for_token,
    get_feishu_user,
    sign_state,
    verify_state,
)
from accounts.serializers import ContentTypeSerializer
from accounts.views import (
    FeishuLoginView,
    MyTokenObtainPairView,
)
```

在文件末尾追加（Task 2 测试类之后）：

```python
@override_settings(
    FEISHU_APP_ID='cli_test',
    FEISHU_APP_SECRET='secret_test',
    FEISHU_REDIRECT_URI='http://testserver/login/feishu/callback',
)
class FeishuLoginViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.feishu_token_payload = {
            'code': 0, 'access_token': 'u-access', 'refresh_token': 'u-refresh',
        }
        self.feishu_user_payload = {
            'code': 0, 'data': {'name': '张三', 'email': 'zhangsan@example.com'},
        }

    def _mock_feishu_apis(self, mock_post, mock_get):
        mock_post.return_value.json.return_value = dict(self.feishu_token_payload)
        mock_get.return_value.json.return_value = dict(self.feishu_user_payload)

    def _post_feishu_login(self, code='auth-code', state=None):
        request = self.factory.post(
            '/api/accounts/feishu/login/',
            {'code': code, 'state': state if state is not None else build_state()},
            format='json',
        )
        return FeishuLoginView.as_view()(request)

    @patch('accounts.feishu.httpx.get')
    @patch('accounts.feishu.httpx.post')
    def test_existing_user_login_by_email(self, mock_post, mock_get):
        self._mock_feishu_apis(mock_post, mock_get)
        User.objects.create_user(
            username='zhangsan', email='zhangsan@example.com', password='old-secret'
        )

        response = self._post_feishu_login()

        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'zhangsan')
        user = User.objects.get(email__iexact='zhangsan@example.com')
        self.assertEqual(user.username, 'zhangsan')

    @patch('accounts.feishu.httpx.get')
    @patch('accounts.feishu.httpx.post')
    def test_new_user_created_with_default_password(self, mock_post, mock_get):
        self._mock_feishu_apis(mock_post, mock_get)

        response = self._post_feishu_login()

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email__iexact='zhangsan@example.com')
        self.assertEqual(user.username, 'zhangsan')
        self.assertEqual(user.first_name, '张三')
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password('Jt123456'))

    @patch('accounts.feishu.httpx.get')
    @patch('accounts.feishu.httpx.post')
    def test_new_user_username_conflict_appends_suffix(self, mock_post, mock_get):
        self._mock_feishu_apis(mock_post, mock_get)
        User.objects.create_user(
            username='zhangsan', email='other@example.com', password='old-secret'
        )

        response = self._post_feishu_login()

        self.assertEqual(response.status_code, 200)
        new_user = User.objects.get(email__iexact='zhangsan@example.com')
        self.assertEqual(new_user.username, 'zhangsan1')

    @patch('accounts.feishu.httpx.get')
    @patch('accounts.feishu.httpx.post')
    def test_inactive_user_treated_as_absent_creates_new_account(self, mock_post, mock_get):
        self._mock_feishu_apis(mock_post, mock_get)
        User.objects.create_user(
            username='zhangsan', email='zhangsan@example.com',
            password='old-secret', is_active=False,
        )

        response = self._post_feishu_login()

        self.assertEqual(response.status_code, 200)
        new_user = User.objects.filter(
            email__iexact='zhangsan@example.com', is_active=True
        ).first()
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user.username, 'zhangsan1')

    @patch('accounts.feishu.httpx.get')
    @patch('accounts.feishu.httpx.post')
    def test_missing_email_rejected(self, mock_post, mock_get):
        mock_post.return_value.json.return_value = dict(self.feishu_token_payload)
        mock_get.return_value.json.return_value = {
            'code': 0, 'data': {'name': '张三'},
        }

        response = self._post_feishu_login()

        self.assertEqual(response.status_code, 400)
        self.assertIn('邮箱', response.data['detail'])

    def test_invalid_state_rejected(self):
        response = self._post_feishu_login(state='123.deadbeef')

        self.assertEqual(response.status_code, 400)
        self.assertIn('state', response.data['detail'])

    def test_missing_code_or_state_rejected(self):
        request = self.factory.post(
            '/api/accounts/feishu/login/', {'code': 'auth-code'}, format='json'
        )

        response = FeishuLoginView.as_view()(request)

        self.assertEqual(response.status_code, 400)

    @patch('accounts.feishu.httpx.get')
    @patch('accounts.feishu.httpx.post')
    def test_feishu_token_error_returns_400(self, mock_post, mock_get):
        mock_post.return_value.json.return_value = {
            'code': 20004, 'error': 'invalid_code', 'error_description': 'code 已过期',
        }
        mock_get.return_value.json.return_value = dict(self.feishu_user_payload)

        response = self._post_feishu_login()

        self.assertEqual(response.status_code, 400)
        self.assertIn('飞书授权失败', response.data['detail'])


class FeishuAuthorizeUrlViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @override_settings(FEISHU_APP_ID='cli_test', FEISHU_APP_SECRET='secret_test')
    def test_returns_authorize_url_and_state(self):
        from accounts.views import FeishuAuthorizeUrlView

        request = self.factory.get('/api/accounts/feishu/authorize-url/')

        response = FeishuAuthorizeUrlView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('state', response.data)
        self.assertIn('response_type=code', response.data['authorize_url'])

    @override_settings(FEISHU_APP_ID='', FEISHU_APP_SECRET='')
    def test_returns_503_when_feishu_not_configured(self):
        from accounts.views import FeishuAuthorizeUrlView

        request = self.factory.get('/api/accounts/feishu/authorize-url/')

        response = FeishuAuthorizeUrlView.as_view()(request)

        self.assertEqual(response.status_code, 503)
        self.assertIn('未配置', response.data['detail'])
```

> 注意装饰器顺序：`@patch` 必须放在 `@override_settings` 之上（参数从下往上注入）。上面的写法里 `override_settings` 在类上，方法上只有 `@patch`，无冲突。

**Step 2: 跑测试确认失败**

```
python manage.py test accounts.tests.FeishuLoginViewTests accounts.tests.FeishuAuthorizeUrlViewTests -v 2
```

预期：`ImportError: cannot import name 'FeishuLoginView'`。

**Step 3: 实现 views.py**

在 `accounts\views.py` 导入区新增（第 12 行 `from skillforge_django.permissions import ...` 之后、现有 `rest_framework_simplejwt.views` 导入块附近）：

```python
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
```

在现有 `.serializers` 导入块之后新增：

```python
from .feishu import (
    FeishuAuthError,
    build_authorize_url,
    build_state,
    exchange_code_for_token,
    get_feishu_user,
    verify_state,
)
```

在 `MyTokenObtainPairView` 类之后（或文件末尾）追加：

```python
class FeishuAuthorizeUrlView(APIView):
    """返回飞书 OAuth 授权页地址（供前端整页跳转）。"""

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        if not getattr(settings, "FEISHU_APP_ID", "") or not getattr(
            settings, "FEISHU_APP_SECRET", ""
        ):
            return Response(
                {"detail": "飞书登录未配置，请联系管理员。"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        state = build_state()
        return Response(
            {"authorize_url": build_authorize_url(state), "state": state},
            status=status.HTTP_200_OK,
        )


def _generate_feishu_username(email: str) -> str:
    """用邮箱前缀生成用户名，与现有用户名冲突（不区分大小写）时追加数字后缀。"""
    base = email.split("@", 1)[0] or "feishu_user"
    if not User.objects.filter(username__iexact=base).exists():
        return base
    index = 1
    while True:
        candidate = f"{base}{index}"
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate
        index += 1


class FeishuLoginView(APIView):
    """飞书授权码登录：按邮箱匹配活跃账号，未匹配则自动创建（默认密码 Jt123456）。"""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        code = request.data.get("code")
        state = request.data.get("state")
        if not code or not state:
            return Response(
                {"detail": "缺少 code 或 state 参数。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not verify_state(state):
            return Response(
                {"detail": "登录状态校验失败，请重新发起飞书登录。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token_data = exchange_code_for_token(code)
            feishu_user = get_feishu_user(token_data["access_token"])
            email = (feishu_user.get("email") or "").strip()
            feishu_name = (feishu_user.get("name") or "").strip()
            if not email:
                return Response(
                    {"detail": "飞书账号未绑定邮箱，无法登录，请使用账号密码登录。"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user is None:
                user = User.objects.create_user(
                    username=_generate_feishu_username(email),
                    email=email,
                    password="Jt123456",
                    first_name=feishu_name,
                    is_active=True,
                )
            elif feishu_name and user.first_name != feishu_name:
                user.first_name = feishu_name
                user.save(update_fields=["first_name"])
        except FeishuAuthError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        except OperationalError:
            return Response(
                {"detail": "认证服务正在启动，请稍后重试。"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserDetailSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
```

**Step 4: 修改 urls.py 注册路由**

`accounts\urls.py` 现有 urlpatterns（router + register/ + me/ + operation_logs include）。在 `path('me/', CurrentUserAPIView.as_view(), name='user-me'),` 之后插入：

```python
    path('feishu/authorize-url/', FeishuAuthorizeUrlView.as_view(), name='feishu-authorize-url'),
    path('feishu/login/', FeishuLoginView.as_view(), name='feishu-login'),
```

并在文件顶部现有 views 导入中追加 `FeishuAuthorizeUrlView, FeishuLoginView`（按该文件现有导入风格写全）。

**Step 5: 跑测试确认通过**

```
python manage.py test accounts -v 2
```

预期：全部通过（含 Task 1/2 的既有测试与 MyTokenObtainPairView 既有测试）。

**Step 6: Commit**

```
git add SkillForge_Django/accounts/views.py SkillForge_Django/accounts/urls.py SkillForge_Django/accounts/tests.py
git commit -m "feat: 新增飞书登录视图与路由（邮箱匹配登录/自动建号）"
```

---
