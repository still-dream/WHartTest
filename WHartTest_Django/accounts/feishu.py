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
