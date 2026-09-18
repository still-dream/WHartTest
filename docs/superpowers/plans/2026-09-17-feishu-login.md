# 飞书登录功能实施计划

> **执行本计划前必须先加载** `subagent-driven-development` skill（Subagent-Driven 方式）或 `executing-plans` skill（Inline 方式）。

## Goal

在现有账号密码登录体系旁新增「飞书登录」：登录页新增与「账号登录」相同大小的飞书登录入口，点击后跳转飞书 OAuth 授权页，回调后按邮箱匹配已有账号登录；若无匹配账号，则用飞书名称作为用户名（邮箱前缀，冲突追加数字后缀）自动创建账号（默认密码 `Jt123456`）。

## Architecture

- **后端**：在现有 `accounts` app 内新增服务层 `accounts/feishu.py`（OAuth URL 构建 / state 签名 / token 交换 / 用户信息获取）+ 两个 `APIView` 视图（`FeishuAuthorizeUrlView`、`FeishuLoginView`）+ 两条路由。不新增 app、不新增数据模型。
- **认证交互**：标准 OAuth 2.0 授权码整页跳转。前端点击飞书登录 → GET 拿授权 URL → `window.location.href` 跳转 → 飞书回调 `/login/feishu/callback`（带 `code`+`state` 或 `error=access_denied`）→ 回调页调 POST `/accounts/feishu/login/` → 成功后写入 localStorage 登录态并进入 Dashboard。
- **账号匹配**：`email__iexact` + `is_active=True`；未匹配则创建新账号；`username` 用邮箱前缀，`iexact` 冲突时追加数字后缀。
- **state 防 CSRF**：`时间戳.HMAC-SHA256(SECRET_KEY, 时间戳)`，10 分钟有效期。
- **前端**：`authService.ts` 新增两个 API 函数；`authStore.ts` 新增 `loginWithFeishu` action（复用 `login` 的 localStorage 写入模式）；`LoginView.vue` 新增飞书 launcher；新建 `FeishuCallbackView.vue` + 路由。

## Tech Stack

- 后端：Django 5.2.1 / DRF / SimpleJWT / httpx==0.28.1（已在 requirements.txt）
- 前端：Vue 3 + `<script setup lang="ts">` / Pinia / Vue Router / Arco Design（Message）/ Vite（type-check：`npx vue-tsc -b`）
- 飞书开放平台（已核实官方文档）：
  - 授权页：`https://accounts.feishu.cn/open-apis/authen/v1/authorize?client_id=&redirect_uri=&response_type=code&state=`（`response_type=code` 为必填）
  - token 端点（v3 最新）：`POST https://accounts.feishu.cn/oauth/v3/token`，请求体 `grant_type=authorization_code` / `client_id` / `client_secret` / `code` / `redirect_uri`；**响应为扁平结构** `{code, access_token, refresh_token, ...}`，成功判断依据 `code === 0`
  - 用户信息：`GET https://open.feishu.cn/open-apis/authen/v1/user_info`，Header `Authorization: Bearer {user_access_token}`，响应 `{code: 0, data: {name, email, ...}}`
  - 拒绝授权回调携带 `error=access_denied`

## Global Constraints

1. **测试命令**：后端 `python manage.py test accounts -v 2`（cwd：`c:\app\WHartTest\WHartTest_Django`）；前端 `npx vue-tsc -b`（cwd：`c:\app\WHartTest\WHartTest_Vue`）。
2. **后端失败状态码约定**（与设计文档的差异说明）：飞书认证类失败（state 无效 / token 交换失败 / 无邮箱）一律返回 **400** 而非 401。原因：前端 `request.ts` 拦截器对所有非 `/token/` URL 的 401 触发 token 刷新流程，登录前的 401 会引发无意义的刷新与重定向，吞掉错误提示；400 不触发刷新，回调页能正常展示错误。数据库未就绪仍返回 503。
3. **响应格式**：`FeishuLoginView` 成功返回 `{access, refresh, user}`，命中 `renderers.py` 67-71 行的 token 专门分支（统一响应 message=「Token 获取成功」）。
4. **views.py 需新增 import**（已核实现有导入不含这些）：`from django.conf import settings`、`from rest_framework_simplejwt.tokens import RefreshToken`、`from .feishu import ...`。
5. **飞书图标**：使用内联 SVG（多次尝试外部 CDN 获取飞书 logo 均失败），与现有 launcher 的渐变圆图标风格一致。
6. **不修改** `UserInfo`/`ApiTokenResponseData` 的既有定义方式；`FeishuCallbackView` 只消费 `AuthServiceLoginResponse`（已导出），无需导出内部接口。
7. **每个任务完成后 commit**，格式沿用仓库惯例：`feat: 中文描述`。
8. **代码注释、错误消息一律中文**，与现有代码风格一致。

---

## Task 1: 后端配置 FEISHU_REDIRECT_URI

**Files:**

- Modify: `WHartTest_Django\wharttest_django\settings.py`（752-756 行现有 FEISHU 区块）
- Modify: `WHartTest_Django\.env.example`（文件末尾，Qdrant 区块之后）
- Modify: `WHartTest_Django\.env`（若存在；本地运行配置，不在 git 内）

**Step 1: 修改 settings.py**

在现有 FEISHU 区块（`FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')` 之后）追加：

```python
# 飞书 OAuth 登录回调地址（前端回调页路由），需与飞书开放平台「重定向 URL」一致
FEISHU_REDIRECT_URI = os.environ.get(
    'FEISHU_REDIRECT_URI', 'http://localhost:5173/login/feishu/callback'
)
```

**Step 2: 修改 .env.example**

在文件末尾（`QDRANT_URL=http://127.0.0.1:8918` 之后）追加：

```ini

# ============================== 飞书 OAuth 登录 ==============================
# 飞书开放平台应用凭证（OAuth 登录用；与上方通知功能共用同名变量，配置一个应用即可）
# FEISHU_APP_ID=cli_xxx
# FEISHU_APP_SECRET=xxx
# OAuth 回调地址，必须与飞书开放平台「安全设置-重定向 URL」中登记的地址完全一致
FEISHU_REDIRECT_URI=http://localhost:5173/login/feishu/callback
```

**Step 3: 更新本地 .env（若存在）**

确认 `.env` 中 `FEISHU_APP_ID=cli_aa21520c0bb89cde`、`FEISHU_APP_SECRET=xxx`（若已有通知用途的同名值则保持一致即可），并新增 `FEISHU_REDIRECT_URI=http://localhost:5173/login/feishu/callback`。

**Step 4: 验证配置生效**

运行（cwd：`WHartTest_Django`）：

```
python manage.py shell -c "from django.conf import settings; print(settings.FEISHU_REDIRECT_URI)"
```

预期输出 `http://localhost:5173/login/feishu/callback`。

**Step 5: Commit**

```
git add WHartTest_Django/wharttest_django/settings.py WHartTest_Django/.env.example
git commit -m "feat: 新增飞书 OAuth 登录回调地址配置"
```

---

## Task 2: 后端服务层 accounts/feishu.py（TDD）

**Files:**

- Modify: `WHartTest_Django\accounts\tests.py`（顶部 import 区 + 文件末尾追加测试类）
- Create: `WHartTest_Django\accounts\feishu.py`

**Interfaces:**

- Produces（供 Task 3 视图与测试消费）：
  - `class FeishuAuthError(Exception)`，属性 `code: int | None`
  - `def build_state() -> str` → `"时间戳.HMAC签名"`
  - `def verify_state(state: str) -> bool`
  - `def build_authorize_url(state: str) -> str` → 完整授权页 URL
  - `def exchange_code_for_token(code: str) -> dict` → 飞书扁平 token 响应
  - `def get_feishu_user(access_token: str) -> dict` → `data` 字段（name/email 等）
- Consumes：`settings.FEISHU_APP_ID` / `settings.FEISHU_APP_SECRET` / `settings.FEISHU_REDIRECT_URI`（Task 1 已配置）/ `settings.SECRET_KEY`

**Step 1: 写失败测试**

修改 `accounts\tests.py` 顶部导入（第 1-9 行区域）：

```python
import time
from unittest.mock import patch
from types import SimpleNamespace

from django.db.utils import OperationalError
from django.test import SimpleTestCase, override_settings
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
from accounts.views import MyTokenObtainPairView
```

> 注意：原第 5 行 `from django.test import SimpleTestCase` 改为 `from django.test import SimpleTestCase, override_settings`；新增 `import time`、feishu 导入块。`sign_state` 虽不在最终实现公开名单中，测试过期 state 需要它——若实现中不单独导出该函数，可将签名逻辑内联为模块级 `_sign_timestamp` 并在本测试文件直接 `from accounts.feishu import _sign_timestamp` 使用（二选一，保持一致即可）。

在文件末尾追加测试类：

```python
@override_settings(
    FEISHU_APP_ID='cli_test',
    FEISHU_APP_SECRET='secret_test',
    FEISHU_REDIRECT_URI='http://testserver/login/feishu/callback',
)
class FeishuServiceTests(SimpleTestCase):
    def test_build_authorize_url_contains_required_params(self):
        url = build_authorize_url('my-state')

        self.assertTrue(url.startswith('https://accounts.feishu.cn/open-apis/authen/v1/authorize?'))
        self.assertIn('response_type=code', url)
        self.assertIn('client_id=cli_test', url)
        self.assertIn('state=my-state', url)
        self.assertIn(
            'redirect_uri=http%3A%2F%2Ftestserver%2Flogin%2Ffeishu%2Fcallback', url
        )

    def test_state_roundtrip_verification(self):
        self.assertTrue(verify_state(build_state()))

    def test_verify_state_rejects_tampered_signature(self):
        timestamp = str(int(time.time()))
        self.assertFalse(verify_state(f'{timestamp}.deadbeef'))

    def test_verify_state_rejects_expired_timestamp(self):
        expired_timestamp = str(int(time.time()) - 601)
        expired_state = f'{expired_timestamp}.{sign_state(expired_timestamp)}'
        self.assertFalse(verify_state(expired_state))

    def test_verify_state_rejects_malformed_state(self):
        self.assertFalse(verify_state('not-a-signed-state'))

    @patch('accounts.feishu.httpx.post')
    def test_exchange_code_for_token_returns_flat_payload(self, mock_post):
        mock_post.return_value.json.return_value = {
            'code': 0,
            'access_token': 'u-access',
            'refresh_token': 'u-refresh',
            'token_type': 'Bearer',
            'expires_in': 6900,
        }

        token_data = exchange_code_for_token('auth-code')

        self.assertEqual(token_data['access_token'], 'u-access')
        self.assertEqual(mock_post.call_args.kwargs['json']['grant_type'], 'authorization_code')
        self.assertEqual(mock_post.call_args.kwargs['json']['client_id'], 'cli_test')
        self.assertEqual(mock_post.call_args.kwargs['json']['code'], 'auth-code')
        self.assertEqual(
            mock_post.call_args.args[0], 'https://accounts.feishu.cn/oauth/v3/token'
        )

    @patch('accounts.feishu.httpx.post')
    def test_exchange_code_for_token_raises_on_error_code(self, mock_post):
        mock_post.return_value.json.return_value = {
            'code': 20004, 'error': 'invalid_code', 'error_description': 'code 已过期',
        }

        with self.assertRaises(FeishuAuthError):
            exchange_code_for_token('expired-code')

    @patch('accounts.feishu.httpx.get')
    def test_get_feishu_user_returns_data_payload(self, mock_get):
        mock_get.return_value.json.return_value = {
            'code': 0,
            'data': {'name': '张三', 'email': 'zhangsan@example.com'},
        }

        feishu_user = get_feishu_user('u-access')

        self.assertEqual(feishu_user['email'], 'zhangsan@example.com')
        self.assertEqual(
            mock_get.call_args.kwargs['headers']['Authorization'], 'Bearer u-access'
        )
        self.assertEqual(
            mock_get.call_args.args[0],
            'https://open.feishu.cn/open-apis/authen/v1/user_info',
        )

    @patch('accounts.feishu.httpx.get')
    def test_get_feishu_user_raises_on_error_code(self, mock_get):
        mock_get.return_value.json.return_value = {'code': 99991668, 'msg': 'token 无效'}

        with self.assertRaises(FeishuAuthError):
            get_feishu_user('bad-token')
```

**Step 2: 跑测试确认失败**

```
python manage.py test accounts.tests.FeishuServiceTests -v 2
```

预期：`ModuleNotFoundError: No module named 'accounts.feishu'`（导入失败）。

**Step 3: 实现 accounts/feishu.py**

新建 `WHartTest_Django\accounts\feishu.py`：

```python
"""飞书 OAuth 登录服务层。

负责构建授权页地址、签发/校验 state、与飞书开放平台交换令牌、获取用户信息。
官方端点（2026-09 核实）：
- 授权页: https://accounts.feishu.cn/open-apis/authen/v1/authorize （response_type=code 必填）
- token(v3): https://accounts.feishu.cn/oauth/v3/token （扁平响应，成功依据 code == 0）
- 用户信息: https://open.feishu.cn/open-apis/authen/v1/user_info （Bearer user_access_token）
"""

import hashlib
import hmac
import logging
import time
from urllib.parse import urlencode

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

FEISHU_AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
FEISHU_TOKEN_URL = "https://accounts.feishu.cn/oauth/v3/token"
FEISHU_USER_INFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"

# state 有效期（秒）：覆盖“跳转授权页 → 用户操作 → 回调”完整流程。
STATE_TTL_SECONDS = 600
HTTP_TIMEOUT_SECONDS = 10


class FeishuAuthError(Exception):
    """飞书认证失败（配置缺失 / token 交换失败 / 用户信息获取失败）。"""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def sign_state(timestamp: str) -> str:
    """对时间戳做 HMAC-SHA256 签名（密钥为 Django SECRET_KEY）。"""
    secret = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(secret, timestamp.encode("utf-8"), hashlib.sha256).hexdigest()


def build_state() -> str:
    """生成防伪造/防重放的 state：`时间戳.HMAC签名`。"""
    timestamp = str(int(time.time()))
    return f"{timestamp}.{sign_state(timestamp)}"


def verify_state(state: str) -> bool:
    """校验 state 的签名与有效期。"""
    if not state or state.count(".") != 1:
        return False
    timestamp, signature = state.split(".", 1)
    if not timestamp.isdigit():
        return False
    if not hmac.compare_digest(signature, sign_state(timestamp)):
        return False
    return time.time() - int(timestamp) <= STATE_TTL_SECONDS


def build_authorize_url(state: str) -> str:
    """构建飞书 OAuth 授权页地址。"""
    params = {
        "client_id": settings.FEISHU_APP_ID,
        "redirect_uri": settings.FEISHU_REDIRECT_URI,
        "response_type": "code",
        "state": state,
    }
    return f"{FEISHU_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
    """用授权码换取 user_access_token，返回飞书扁平结构响应。"""
    app_id = getattr(settings, "FEISHU_APP_ID", "")
    app_secret = getattr(settings, "FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise FeishuAuthError("飞书登录未配置（FEISHU_APP_ID / FEISHU_APP_SECRET 缺失）")

    payload = {
        "grant_type": "authorization_code",
        "client_id": app_id,
        "client_secret": app_secret,
        "code": code,
        "redirect_uri": settings.FEISHU_REDIRECT_URI,
    }
    try:
        response = httpx.post(FEISHU_TOKEN_URL, json=payload, timeout=HTTP_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise FeishuAuthError(f"请求飞书令牌接口失败：{exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise FeishuAuthError("飞书令牌接口返回了非 JSON 响应。") from exc

    if data.get("code") != 0 or not data.get("access_token"):
        logger.warning("飞书授权码换取令牌失败：%s", data)
        description = data.get("error_description") or data.get("error") or data
        raise FeishuAuthError(f"飞书授权失败：{description}", code=data.get("code"))
    return data


def get_feishu_user(access_token: str) -> dict:
    """用 user_access_token 获取飞书用户信息（返回 data 字段：name/email 等）。"""
    try:
        response = httpx.get(
            FEISHU_USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise FeishuAuthError(f"请求飞书用户信息失败：{exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise FeishuAuthError("飞书用户信息接口返回了非 JSON 响应。") from exc

    if data.get("code") != 0:
        logger.warning("获取飞书用户信息失败：%s", data)
        raise FeishuAuthError(
            f"获取飞书用户信息失败：{data.get('msg') or data}", code=data.get("code")
        )
    return data.get("data") or {}
```

**Step 4: 跑测试确认通过**

```
python manage.py test accounts.tests.FeishuServiceTests -v 2
```

预期：9 个测试全部 `ok`。

**Step 5: Commit**

```
git add WHartTest_Django/accounts/feishu.py WHartTest_Django/accounts/tests.py
git commit -m "feat: 新增飞书 OAuth 服务层（授权地址/state 签名/令牌交换/用户信息）"
```

---

## Task 3: 后端视图与路由（TDD）

**Files:**

- Modify: `WHartTest_Django\accounts\views.py`（新增 import + 文件末尾追加视图）
- Modify: `WHartTest_Django\accounts\urls.py`（`me/` 路由之后插两条）
- Modify: `WHartTest_Django\accounts\tests.py`（末尾追加视图测试类）

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

在 `accounts\views.py` 导入区新增（第 12 行 `from wharttest_django.permissions import ...` 之后、现有 `rest_framework_simplejwt.views` 导入块附近）：

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
git add WHartTest_Django/accounts/views.py WHartTest_Django/accounts/urls.py WHartTest_Django/accounts/tests.py
git commit -m "feat: 新增飞书登录视图与路由（邮箱匹配登录/自动建号）"
```

---

## Task 4: 前端 authService 飞书 API

**Files:**

- Modify: `WHartTest_Vue\src\services\authService.ts`（末尾追加两个函数 + 接口定义）

**Interfaces:**

- Consumes：`request<T>`（`@/utils/request`，已导入）、`axios`（已导入）
- Produces（供 Task 5/6/7 消费）：
  - `export const getFeishuAuthorizeUrl = async (): Promise<FeishuAuthorizeUrlResponse>`
  - `export const feishuLogin = async (code: string, state: string): Promise<AuthServiceLoginResponse>`（成功 data 为既有 `ApiTokenResponseData`，与账号登录同构）

**Step 1: 实现（前端无单测设施，直接实现后以 vue-tsc 验证）**

在 `authService.ts` 末尾追加：

```typescript
// 飞书授权地址接口响应的数据结构
export interface FeishuAuthorizeUrlResponseData {
  authorize_url: string;
  state: string;
}

// 飞书授权地址函数返回的结构
export interface FeishuAuthorizeUrlResponse {
  success: boolean;
  data?: FeishuAuthorizeUrlResponseData;
  error?: string;
  statusCode?: number;
}

/**
 * 获取飞书 OAuth 授权页地址
 * @returns 返回一个 Promise，解析为包含授权地址与 state 的对象
 */
export const getFeishuAuthorizeUrl = async (): Promise<FeishuAuthorizeUrlResponse> => {
  const API_URL = '/accounts/feishu/authorize-url/';

  try {
    const response = await request<FeishuAuthorizeUrlResponseData>({
      url: API_URL,
      method: 'GET',
      headers: {
        'accept': 'application/json',
      }
    });

    if (response.success && response.data) {
      return { success: true, data: response.data, statusCode: 200 };
    }

    return {
      success: false,
      error: response.error || '获取飞书授权地址失败：响应数据格式不正确。',
      statusCode: (response as any).status ?? 500,
    };
  } catch (error) {
    let errorMessage = '获取飞书授权地址失败，请稍后再试。';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;
        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        }
      } else if (error.request) {
        errorMessage = '认证服务暂未就绪，请稍后重试。';
      }
    }
    return { success: false, error: errorMessage, statusCode };
  }
};

/**
 * 使用飞书授权码登录（返回结构与账号登录一致）
 * @param code 飞书回调携带的授权码
 * @param state 飞书回调携带的防 CSRF 状态
 * @returns 返回一个 Promise，解析为包含认证结果的对象
 */
export const feishuLogin = async (code: string, state: string): Promise<AuthServiceLoginResponse> => {
  const API_URL = '/accounts/feishu/login/';
  const CSRF_TOKEN = 'kMNlyN2uN6c2QRr9r2rDQbfxBGsVzjPFY1h1as93VNMRTjo5kRpDbVq5ii8FFcKW';

  try {
    const response = await request<ApiTokenResponseData>({
      url: API_URL,
      method: 'POST',
      data: { code, state },
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFTOKEN': CSRF_TOKEN,
        'accept': 'application/json',
      }
    });

    if (response.success && response.data) {
      return { success: true, data: response.data, statusCode: 200 };
    }

    const responseStatus = (response as any).status as number | undefined;
    let errorMessage = response.error || '飞书登录失败：响应数据格式不正确。';
    if (responseStatus === 503) {
      errorMessage = response.error || '认证服务正在启动，请稍后重试。';
    } else if (errorMessage.includes('服务器无响应') || errorMessage.includes('Network Error')) {
      errorMessage = '认证服务暂未就绪，请稍后重试。';
    }
    return { success: false, error: errorMessage, statusCode: responseStatus ?? 500 };
  } catch (error) {
    let errorMessage = '飞书登录暂时不可用，请稍后再试。';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;
        if (statusCode === 503) {
          errorMessage = '认证服务正在启动，请稍后重试。';
        } else if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else {
          errorMessage = `飞书登录失败：服务器错误 (${statusCode})。`;
        }
      } else if (error.request) {
        errorMessage = '认证服务暂未就绪，请稍后重试。';
      }
    }
    return { success: false, error: errorMessage, statusCode };
  }
};
```

**Step 2: 验证**

```
npx vue-tsc -b
```

cwd：`WHartTest_Vue`。预期：无类型错误（exit 0）。本函数暂无调用方，type-check 通过即可。

**Step 3: Commit**

```
git add WHartTest_Vue/src/services/authService.ts
git commit -m "feat: authService 新增飞书授权地址与飞书登录接口"
```

---

## Task 5: 前端 authStore loginWithFeishu

**Files:**

- Modify: `WHartTest_Vue\src\store\authStore.ts`（导入区 + actions 内追加）

**Interfaces:**

- Consumes：`feishuLogin as feishuLoginService`（Task 4）、既有 `loadUserPermissions()` action
- Produces：`async loginWithFeishu(code: string, state: string): Promise<boolean>`（供 Task 7 回调页消费；成功后登录态写入与 `login()` 完全一致）

**Step 1: 修改导入**

`authStore.ts` 第 2-7 行的 authService 导入块改为：

```typescript
import {
  login as loginService,
  register as registerService,
  feishuLogin as feishuLoginService,
  type AuthServiceLoginResponse,
  type AuthServiceRegisterResponse,
} from '@/services/authService';
```

**Step 2: 追加 action**

在 `actions` 内 `login(...)` 方法之后、`logout()` 之前追加：

```typescript
    /**
     * 飞书登录 Action（邮箱匹配已有账号，否则后端自动创建）
     * @param code 飞书回调携带的授权码
     * @param state 飞书回调携带的防 CSRF 状态
     * @returns 返回一个 Promise，解析为登录是否成功 (boolean)
     */
    async loginWithFeishu(code: string, state: string): Promise<boolean> {
      this.isLoading = true;
      this.loginError = null;
      try {
        const response: AuthServiceLoginResponse = await feishuLoginService(code, state);
        if (response.success && response.data) {
          this.isAuthenticated = true;
          this.user = response.data.user;
          this.accessToken = response.data.access;
          this.refreshToken = response.data.refresh;

          localStorage.setItem('auth-isAuthenticated', 'true');
          localStorage.setItem('auth-user', JSON.stringify(this.user));
          localStorage.setItem('auth-accessToken', this.accessToken);
          localStorage.setItem('auth-refreshToken', this.refreshToken);

          // 异步获取用户权限（不阻塞登录流程）
          this.loadUserPermissions().catch(error => {
            console.error('获取用户权限失败:', error);
          });

          this.isLoading = false;
          return true;
        }

        this.isAuthenticated = false;
        this.user = null;
        this.accessToken = null;
        this.refreshToken = null;
        this.loginError = response.error || '飞书登录失败，请重试。';
        localStorage.removeItem('auth-isAuthenticated');
        localStorage.removeItem('auth-user');
        localStorage.removeItem('auth-accessToken');
        localStorage.removeItem('auth-refreshToken');
        this.isLoading = false;
        return false;
      } catch (error: any) {
        this.isAuthenticated = false;
        this.user = null;
        this.accessToken = null;
        this.refreshToken = null;
        this.loginError = error.message || '发生未知错误，请稍后再试。';
        localStorage.removeItem('auth-isAuthenticated');
        localStorage.removeItem('auth-user');
        localStorage.removeItem('auth-accessToken');
        localStorage.removeItem('auth-refreshToken');
        this.isLoading = false;
        return false;
      }
    },
```

**Step 3: 验证**

```
npx vue-tsc -b
```

预期：无类型错误。

**Step 4: Commit**

```
git add WHartTest_Vue/src/store/authStore.ts
git commit -m "feat: authStore 新增飞书登录 action"
```

---

## Task 6: LoginView 新增飞书登录入口

**Files:**

- Modify: `WHartTest_Vue\src\views\LoginView.vue`（模板 / script / style 三处）

**Interfaces:**

- Consumes：`getFeishuAuthorizeUrl`（Task 4）
- Produces：点击飞书 launcher → 整页跳转飞书授权页

**Step 1: 修改模板**

将现有单个 `.login-launcher` 按钮（第 15-39 行，含 `ref="launcherButtonRef"` 的整个 `<button>`）包进行容器，并在其后新增飞书按钮：

```html
      <div class="launcher-row">
        <button
          ref="launcherButtonRef"
          type="button"
          class="login-launcher"
          aria-label="打开登录弹窗"
          @click="openLoginDialog"
        >
          <span class="launcher-aura" />
          <span class="launcher-icon" aria-hidden="true">
            <img
              v-if="!fingerprintImageLoadFailed && currentFingerprintAsset"
              :src="currentFingerprintAsset"
              alt=""
              class="launcher-fingerprint-img"
              @error="handleFingerprintAssetError"
            />
            <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.8" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V7.875a4.5 4.5 0 00-9 0V10.5m9 0h.75A2.25 2.25 0 0119.5 12.75v5.625a2.25 2.25 0 01-2.25 2.25h-10.5a2.25 2.25 0 01-2.25-2.25V12.75A2.25 2.25 0 016.75 10.5h.75" />
            </svg>
          </span>
          <span class="launcher-copy">
            <strong>账号登录</strong>
            <span>点击展开登录框</span>
          </span>
        </button>

        <button
          type="button"
          class="login-launcher feishu-launcher"
          aria-label="使用飞书登录"
          :disabled="feishuLoading"
          @click="handleFeishuLogin"
        >
          <span class="launcher-aura feishu-aura" />
          <span class="launcher-icon feishu-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10.9 10.9H2A8.9 8.9 0 0 1 10.9 2v8.9Z" fill="#3370FF" />
              <path d="M13.1 13.1H22A8.9 8.9 0 0 1 13.1 22v-8.9Z" fill="#3370FF" />
              <path d="M13.1 2A8.9 8.9 0 0 1 22 10.9h-8.9V2Z" fill="#00D6B9" />
              <path d="M10.9 22A8.9 8.9 0 0 1 2 13.1h8.9V22Z" fill="#00D6B9" />
              <circle cx="12" cy="12" r="2.4" fill="#fff" />
            </svg>
          </span>
          <span class="launcher-copy">
            <strong>飞书登录</strong>
            <span>使用飞书账号快捷登录</span>
          </span>
        </button>
      </div>
```

> 内联 SVG 为飞书品牌风格的多色风车标识（外部 CDN 获取 logo 不可用，采用自绘几何图形），尺寸继承现有 `.launcher-icon svg` 的 36px 样式，fill 写死在 path 上不受 `color` 影响。

**Step 2: 修改 script**

导入区（第 157 行 `useStarryBackground` 导入附近）新增：

```typescript
import { getFeishuAuthorizeUrl } from '@/services/authService'
```

在 `const featureTags = [...]` 之后新增响应式状态与方法（放在 `openLoginDialog` 定义之前）：

```typescript
const feishuLoading = ref(false)

const handleFeishuLogin = async () => {
  if (feishuLoading.value) {
    return
  }

  feishuLoading.value = true
  try {
    const response = await getFeishuAuthorizeUrl()
    if (response.success && response.data) {
      // 整页跳转到飞书授权页，授权完成后由回调页接管
      window.location.href = response.data.authorize_url
      return
    }
    Message.error(response.error || '无法获取飞书授权地址，请稍后重试。')
  } catch {
    Message.error('无法获取飞书授权地址，请稍后重试。')
  } finally {
    feishuLoading.value = false
  }
}
```

**Step 3: 修改样式**

在 `.login-launcher` 相关样式块之后（`.launcher-copy span` 规则之后）追加：

```css
.launcher-row {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 20px;
}

.feishu-launcher .launcher-icon {
  background: linear-gradient(135deg, rgba(0, 102, 255, 0.9), rgba(0, 214, 185, 0.9));
  box-shadow: 0 12px 28px rgba(51, 112, 255, 0.35);
}

.feishu-launcher .launcher-aura {
  background: radial-gradient(circle, rgba(0, 214, 185, 0.22), transparent 72%);
}

.feishu-launcher:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}
```

在文件末尾 640px 媒体查询内（`.launcher-icon { width: 50px; height: 50px; }` 规则之后）追加：

```css
  .launcher-row {
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }
```

**Step 4: 验证**

```
npx vue-tsc -b
```

预期：无类型错误。

**Step 5: Commit**

```
git add WHartTest_Vue/src/views/LoginView.vue
git commit -m "feat: 登录页新增飞书登录入口"
```

---

## Task 7: 飞书回调页与路由

**Files:**

- Create: `WHartTest_Vue\src\views\FeishuCallbackView.vue`
- Modify: `WHartTest_Vue\src\router\index.ts`（import + 路由定义 + publicRoutes）

**Interfaces:**

- Consumes：`useAuthStore().loginWithFeishu`（Task 5）、`useStarryBackground`（既有 composable）、`Message`（Arco）
- Produces：路由 `path: '/login/feishu/callback'`、`name: 'FeishuCallback'`（即后端 `FEISHU_REDIRECT_URI` 的默认值路径）；处理三分支：`code+state` 正常登录 / `error=access_denied` 取消授权 / 其他错误

**Step 1: 新建 FeishuCallbackView.vue**

```vue
<template>
  <div class="feishu-callback-page">
    <canvas ref="canvasRef" class="starry-canvas" />

    <div class="callback-card">
      <template v-if="status === 'loading'">
        <svg class="spinner" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" opacity="0.25" />
          <path fill="currentColor" opacity="0.75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <h2>飞书登录中</h2>
        <p>正在验证飞书授权信息，请稍候...</p>
      </template>

      <template v-else>
        <div class="callback-icon">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
        </div>
        <h2>{{ status === 'denied' ? '已取消授权' : '登录失败' }}</h2>
        <p>{{ errorMessage }}</p>
        <button type="button" class="back-button" @click="goLogin">返回登录</button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useRoute, useRouter } from 'vue-router'
import { useStarryBackground } from '@/composables/useStarryBackground'
import { useAuthStore } from '@/store/authStore'

type CallbackStatus = 'loading' | 'denied' | 'error'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const status = ref<CallbackStatus>('loading')
const errorMessage = ref('')

useStarryBackground(canvasRef)

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const goLogin = () => {
  router.replace({ name: 'Login' })
}

onMounted(async () => {
  // 分支一：飞书携带 error 回调（用户拒绝授权等）
  const queryError = typeof route.query.error === 'string' ? route.query.error : ''
  if (queryError) {
    status.value = queryError === 'access_denied' ? 'denied' : 'error'
    errorMessage.value = queryError === 'access_denied'
      ? '您取消了飞书授权，可返回使用其他方式登录。'
      : '飞书授权失败，请返回重试。'
    return
  }

  const code = typeof route.query.code === 'string' ? route.query.code : ''
  const state = typeof route.query.state === 'string' ? route.query.state : ''
  if (!code || !state) {
    status.value = 'error'
    errorMessage.value = '回调参数缺失，无法完成飞书登录。'
    return
  }

  // 分支二：正常回调，交给后端换取令牌并登录
  const success = await authStore.loginWithFeishu(code, state)
  if (success) {
    Message.success('登录成功！')
    await router.replace({ name: 'Dashboard' })
    return
  }

  // 分支三：登录失败，展示后端返回的错误信息
  status.value = 'error'
  errorMessage.value = authStore.getLoginError || '飞书登录失败，请返回重试。'
})
</script>

<style scoped>
.feishu-callback-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: radial-gradient(ellipse at 20% 50%, #0a1628 0%, #020810 100%);
}

.starry-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.callback-card {
  position: relative;
  z-index: 1;
  width: min(100%, 380px);
  padding: 36px 32px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 24px;
  background: rgba(9, 20, 38, 0.72);
  backdrop-filter: blur(18px);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
  color: #e8f0ff;
  text-align: center;
  animation: fade-in-up 0.6s ease-out;
}

.spinner {
  width: 44px;
  height: 44px;
  animation: spin 1s linear infinite;
}

.callback-card h2 {
  margin: 16px 0 8px;
  font-size: 20px;
  font-weight: 700;
}

.callback-card p {
  margin: 0;
  color: rgba(180, 210, 255, 0.75);
  font-size: 14px;
  line-height: 1.6;
}

.callback-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(245, 83, 61, 0.16);
  color: #f87171;
}

.callback-icon svg {
  width: 30px;
  height: 30px;
}

.back-button {
  margin-top: 20px;
  padding: 10px 28px;
  border: none;
  border-radius: 999px;
  background: linear-gradient(135deg, #2563eb, #38bdf8);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.back-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.35);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
```

**Step 2: 修改 router/index.ts**

1. 在 `LoginView` 的 import 语句之后新增：

```typescript
import FeishuCallbackView from '@/views/FeishuCallbackView.vue'; // 导入飞书登录回调页面组件。
```

2. 在 `Register` 路由对象（第 40-44 行）之后新增路由：

```typescript
  {
    path: '/login/feishu/callback', // 飞书 OAuth 回调地址，与后端 FEISHU_REDIRECT_URI 默认值一致。
    name: 'FeishuCallback', // 定义飞书回调路由名称。
    component: FeishuCallbackView // 指定回调页组件，负责用 code 完成登录。
  },
```

3. 第 269 行白名单改为：

```typescript
  const publicRoutes = ['Login', 'Register', 'FeishuCallback']; // 声明公开路由名称白名单。
```

**Step 3: 验证**

```
npx vue-tsc -b
```

预期：无类型错误。

**Step 4: Commit**

```
git add WHartTest_Vue/src/views/FeishuCallbackView.vue WHartTest_Vue/src/router/index.ts
git commit -m "feat: 新增飞书登录回调页与路由"
```

---

## Task 8: 全量验证与手动测试清单

**Files:**

- 无代码修改（验证任务）

**Step 1: 后端全量测试**

cwd `WHartTest_Django`：

```
python manage.py test accounts -v 2
```

预期：全部通过（含既有 MyTokenObtainPairView / ContentTypeSerializer 测试，无回归）。

**Step 2: 前端构建验证**

cwd `WHartTest_Vue`：

```
npm run build
```

预期：`vue-tsc -b` 类型检查 + vite build 全部成功。

**Step 3: Commit（如 Step 1/2 产生修复）**

若有修复则按修复内容提交；无修改则跳过。

**Step 4: 手动测试清单（需人工/浏览器执行）**

前置配置（飞书开放平台，应用 `cli_aa21520c0bb89cde`）：

1. 「安全设置」→「重定向 URL」添加 `http://localhost:5173/login/feishu/callback`（生产环境需另加对应域名地址，并同步设置 `FEISHU_REDIRECT_URI` 环境变量）。
2. 「权限管理」开通：`获取用户基本信息`（authen 相关，user_info 接口必需）、`获取用户邮箱` 相关权限；然后「版本管理与发布」创建版本并发布（权限变更需发布后生效）。

验证路径：

1. 打开 `/login`：两个 launcher（账号登录 / 飞书登录）并排展示、大小一致；640px 以下纵向堆叠。
2. 点击「飞书登录」→ 跳转飞书授权页，URL 含 `response_type=code` 与 state。
3. 授权 → 回调页短暂 loading → 提示「登录成功」→ 进入 Dashboard；`localStorage` 中 `auth-user` 的 `first_name` 为飞书名称。
4. 新邮箱用户：Django 后台确认用户已创建，username 为邮箱前缀，密码 `Jt123456` 可登录（可用账号密码方式复核）。
5. 已有同邮箱账号：登录后 username 不变，无新用户产生。
6. 授权页点「取消」→ 回调页显示「已取消授权」+「返回登录」按钮可用。
7. 篡改回调 URL 的 state → 回调页显示登录失败及后端 detail 信息。
8. 用户名冲突：预先创建 username 同邮箱前缀的其他用户 → 飞书登录后新账号 username 带数字后缀。
