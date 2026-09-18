"""飞书 OAuth 登录服务层。

负责构建授权页地址、签发/校验 state、与飞书开放平台交换令牌、获取用户信息。
官方端点（2026-09 核实）：
- 授权页: https://accounts.feishu.cn/open-apis/authen/v1/authorize （response_type=code 必填）
- token(v3): https://accounts.feishu.cn/oauth/v3/token （扁平响应，成功依据 code == 0）
- 登录用户信息: https://open.feishu.cn/open-apis/authen/v1/user_info
  （Bearer user_access_token；提供 open_id 与基础资料，email/enterprise_email
  依赖「获取用户邮箱信息 contact:user.email:readonly」权限）
- 单个用户信息(v3 通讯录): https://open.feishu.cn/open-apis/contact/v3/users/{open_id}
  （Bearer user_access_token；调用该接口本身需要接口权限「通过 API 获取基础用户信息
  contact:contact.base:readonly」，否则报 99991679；enterprise_email 字段依赖
  「获取用户受雇信息 contact:user.employee:readonly」，缺失时该字段不出现在响应中）
"""

import hashlib
import hmac
import logging
import secrets
import time
from urllib.parse import quote, urlencode

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

FEISHU_AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
FEISHU_TOKEN_URL = "https://accounts.feishu.cn/oauth/v3/token"
FEISHU_USER_INFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"
FEISHU_CONTACT_USER_URL = "https://open.feishu.cn/open-apis/contact/v3/users/{open_id}"

# 飞书登录所需授权范围（须与飞书开放平台已开通的「用户身份」权限一致）。
# 不传 scope 时飞书仅授予基础登录信息，user_access_token 无法调用通讯录接口获取企业邮箱。
# 权限分两类、缺一不可：
# - 接口权限：contact:contact.base:readonly 是调用通讯录 v3 接口本身的前提（缺了报 99991679）；
# - 字段权限：contact:user.base:readonly 控制 name、contact:user.employee:readonly 控制
#   enterprise_email（企业邮箱，官方字段权限说明见「用户资源介绍」，2026-04 核实）。
# 注意：「企业邮箱」字段属于受雇信息，contact:user.email:readonly（个人邮箱）与
# directory:employee.base.enterprise_email:read（企业目录 API）对其均无效。
FEISHU_LOGIN_SCOPES = [
    "contact:contact.base:readonly",
    "contact:user.base:readonly",
    "contact:user.employee:readonly",
]

# state 有效期（秒）：覆盖“跳转授权页 → 用户操作 → 回调”完整流程。
STATE_TTL_SECONDS = 600
HTTP_TIMEOUT_SECONDS = 10


class FeishuAuthError(Exception):
    """飞书认证失败（配置缺失 / token 交换失败 / 用户信息获取失败）。"""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def sign_state(payload: str) -> str:
    """对 state 载荷（随机串+时间戳）做 HMAC-SHA256 签名（密钥为 Django SECRET_KEY）。"""
    secret = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def build_state() -> str:
    """生成防伪造/防重放的 state：`随机串.时间戳.HMAC签名(随机串+时间戳)`。"""
    nonce = secrets.token_urlsafe(16)
    timestamp = str(int(time.time()))
    return f"{nonce}.{timestamp}.{sign_state(f'{nonce}{timestamp}')}"


def verify_state(state: str) -> bool:
    """校验 state 的结构、签名与有效期（TTL 以时间戳为准）。"""
    if not state or state.count(".") != 2:
        return False
    nonce, timestamp, signature = state.split(".", 2)
    if not nonce or not timestamp.isdigit():
        return False
    if not hmac.compare_digest(signature, sign_state(f"{nonce}{timestamp}")):
        return False
    return time.time() - int(timestamp) <= STATE_TTL_SECONDS


def build_authorize_url(state: str) -> str:
    """构建飞书 OAuth 授权页地址（scope 决定 user_access_token 的权限范围）。"""
    params = {
        "client_id": settings.FEISHU_APP_ID,
        "redirect_uri": settings.FEISHU_REDIRECT_URI,
        "response_type": "code",
        "state": state,
        # scope 以空格分隔；quote_via=quote 将空格编码为 %20（quote_plus 的 + 会被部分服务端解析为加号）。
        "scope": " ".join(FEISHU_LOGIN_SCOPES),
    }
    return f"{FEISHU_AUTHORIZE_URL}?{urlencode(params, quote_via=quote)}"


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
    """用 user_access_token 获取登录用户信息（旧版接口）。

    返回 data 字段：open_id/name/email/enterprise_email 等。
    该响应是 open_id 的来源，也是通讯录 v3 详情获取失败时的回退数据源。
    """
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


def get_feishu_user_detail(access_token: str, open_id: str) -> dict:
    """用 user_access_token + open_id 调通讯录 v3 接口获取完整用户信息（data.user）。

    name 字段依赖「获取用户基本信息 contact:user.base:readonly」、enterprise_email
    字段依赖「获取用户受雇信息 contact:user.employee:readonly」权限（权限缺失时字段
    直接不出现在响应中，而非报错）；调用方需自行处理 FeishuAuthError
    （如降级使用旧版 get_feishu_user 的数据）。
    """
    url = FEISHU_CONTACT_USER_URL.format(open_id=open_id)
    try:
        response = httpx.get(
            url,
            params={"user_id_type": "open_id"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise FeishuAuthError(f"请求飞书通讯录用户信息失败：{exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise FeishuAuthError("飞书通讯录用户信息接口返回了非 JSON 响应。") from exc

    if data.get("code") != 0:
        logger.warning("获取飞书通讯录用户信息失败：%s", data)
        raise FeishuAuthError(
            f"获取飞书通讯录用户信息失败：{data.get('msg') or data}",
            code=data.get("code"),
        )
    return (data.get("data") or {}).get("user") or {}


FEISHU_BATCH_GET_ID_URL = "https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id"


def get_feishu_user_name_by_email(email: str) -> str | None:
    """用应用身份（tenant_access_token）按企业邮箱反查飞书用户中文名。

    供创建账号时自动填充「姓名」（last_name）使用；任何失败均返回 None
    （记录日志，不阻断调用方的创建流程）。需要应用已开通通讯录
    「通过手机号或邮箱获取用户 ID」与「获取用户基本信息」等应用身份权限。
    """
    normalized = (email or "").strip()
    if not normalized:
        return None

    # 延迟导入：复用推送服务的应用身份令牌获取逻辑，避免跨应用加载顺序问题。
    from notifications.services import _get_feishu_token

    token = _get_feishu_token()
    if not token:
        logger.warning("按邮箱反查飞书用户姓名失败：未配置 FEISHU_APP_ID / FEISHU_APP_SECRET。")
        return None

    headers = {"Authorization": f"Bearer {token}"}

    # 第一步：按企业邮箱反查 open_id（batch_get_id 仅匹配企业邮箱，与本系统账号邮箱口径一致）。
    try:
        response = httpx.post(
            FEISHU_BATCH_GET_ID_URL,
            params={"user_id_type": "open_id"},
            json={"emails": [normalized]},
            headers=headers,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("按邮箱反查飞书用户 ID 失败：%s", exc)
        return None

    if data.get("code") != 0:
        logger.warning("按邮箱反查飞书用户 ID 失败：%s", data)
        return None

    user_list = (data.get("data") or {}).get("user_list") or []
    open_id = ((user_list[0] or {}).get("user_id") or "").strip() if user_list else ""
    if not open_id:
        logger.info("邮箱 %s 未匹配到飞书用户。", normalized)
        return None

    # 第二步：用 open_id 取通讯录用户详情中的 name（中文名）。
    try:
        detail = get_feishu_user_detail(token, open_id)
    except FeishuAuthError as exc:
        logger.warning("获取飞书用户姓名失败：%s", exc)
        return None
    return ((detail.get("name") or "").strip()) or None
