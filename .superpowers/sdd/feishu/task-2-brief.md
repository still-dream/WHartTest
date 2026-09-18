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
