# 飞书登录功能设计文档

日期：2026-09-17

## 1. 需求概述

在现有登录认证体系（Django SimpleJWT + Vue3 Pinia）下新增一套飞书认证登录：

- 登录页「账号登录」入口右侧有一个相同大小的「飞书登录」入口
- 点击后整页跳转飞书授权页（OAuth 2.0 授权码模式），授权后回跳系统自动登录
- 已有账号：按飞书账号邮箱（不区分大小写）匹配系统账号，命中直接登录
- 新账号：根据飞书邮箱自动创建账号，默认密码 `Jt123456`
- 飞书应用凭证：
  - App ID: `cli_aa21520c0bb89cde`
  - App Secret: 通过 `.env` 环境变量配置

## 2. 关键决策

| 决策点 | 结论 |
|---|---|
| 认证交互方式 | 跳转飞书授权页（官方标准 OAuth 流程，授权后回跳自动登录） |
| 账号匹配规则 | 按邮箱匹配（不区分大小写），仅匹配活跃用户 |
| 后端实现位置 | 方案 A：在现有 `accounts` app 内实现，不新建 app、不新增数据模型 |
| 新账号 username | 飞书邮箱前缀（如 `zhangsan@x.com` → `zhangsan`），冲突时追加数字后缀 |
| App Secret 存放 | 后端 `.env` 环境变量，前端不接触任何凭证 |

## 3. 整体流程

```
点击「飞书登录」
→ GET /api/accounts/feishu/authorize-url/ 获取授权链接（含 HMAC 签名 state）
→ 整页跳转飞书授权页
→ 用户授权 → 飞书重定向回 /login/feishu/callback?code=xxx&state=xxx
→ 前端回调页 POST /api/accounts/feishu/login/ {code, state}
→ 后端：校验 state → code 换 user_access_token → 拉取飞书用户信息
→ 按邮箱匹配/创建账号 → 签发系统 JWT（access/refresh/user）
→ 前端写入 authStore / localStorage → 跳转系统首页
```

## 4. 后端设计

### 4.1 配置（settings.py + .env）

```
FEISHU_APP_ID=cli_aa21520c0bb89cde
FEISHU_APP_SECRET=xxx
FEISHU_REDIRECT_URI=http://localhost:5173/login/feishu/callback
```

settings.py 中以 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_REDIRECT_URI` 读取，`.env` 提供默认值。

### 4.2 服务层 `accounts/feishu.py`（新增）

- `build_authorize_url(state) -> str`：拼接授权页 URL
  `https://accounts.feishu.cn/open-apis/authen/v1/authorize?client_id=...&redirect_uri=...&state=...&scope=`
- `sign_state() -> str`：生成 `payload.signature` 形式的 state（payload 含随机串+时间戳，用 `SECRET_KEY` HMAC-SHA256 签名，有效期 10 分钟）
- `verify_state(state) -> bool`：校验签名与有效期
- `exchange_code_for_token(code) -> str`：POST `https://accounts.feishu.cn/oauth/v3/token`
  （`grant_type=authorization_code`, `client_id`, `client_secret`, `code`, `redirect_uri`），返回 `user_access_token`
- `get_feishu_user(user_access_token) -> dict`：GET `https://open.feishu.cn/open-apis/authen/v1/user_info`，返回飞书用户信息（`name`、`email` 等）

使用项目已有依赖 `httpx`。

### 4.3 视图 `accounts/views.py`

- `FeishuAuthorizeUrlView(APIView)`：GET，返回 `{ "authorize_url": ... }`
- `FeishuLoginView(APIView)`：POST `{code, state}`
  1. 校验 `state`（失败返回 400「登录状态校验失败，请重新登录」）
  2. code 换 token（失败返回 400「飞书授权码无效或已过期」）
  3. 拉取飞书用户信息；无邮箱返回 400「飞书账号未绑定邮箱，无法登录」
  4. `User.objects.filter(email__iexact=email, is_active=True)` 命中 → 直接登录
  5. 未命中 → 创建用户：`username` = 邮箱前缀（冲突追加数字后缀保证唯一）、`email`、`set_password("Jt123456")`、姓名存飞书名称
  6. 复用 `MyTokenObtainPairSerializer` 的返回结构签发 JWT：`{access, refresh, user}`

### 4.4 路由 `accounts/urls.py`

- `path("feishu/authorize-url/", FeishuAuthorizeUrlView.as_view())`
- `path("feishu/login/", FeishuLoginView.as_view())`

### 4.5 错误处理

| 场景 | 处理 |
|---|---|
| state 校验失败 | 400，提示重新登录 |
| 授权码无效/过期（5 分钟一次性） | 400，提示重新发起登录 |
| 飞书用户无邮箱 | 400，明确提示 |
| 飞书接口网络异常 | 502，提示飞书服务异常 |
| 用户拒绝授权 | 飞书回调带 `error=access_denied`，前端提示「已取消授权」 |

## 5. 前端设计

### 5.1 `LoginView.vue`

- 现有「账号登录」launcher（`.login-launcher`）右侧新增相同尺寸的「飞书登录」launcher
- 点击 → 调 `getFeishuAuthorizeUrl()` → `window.location.href = authorize_url` 整页跳转

### 5.2 `FeishuCallbackView.vue`（新增）

- 路由 `/login/feishu/callback`，加入 `router/index.ts` 的 `publicRoutes` 白名单
- 读取 URL 参数：
  - `error`（如 `access_denied`）→ 显示「已取消授权」等提示 + 返回登录页按钮
  - `code` + `state` → 调 `authStore.loginWithFeishu(code, state)` → 成功跳转系统首页，失败显示错误 + 返回登录按钮
- 处理中显示加载状态

### 5.3 `authService.ts`

- `getFeishuAuthorizeUrl(): Promise<{ authorize_url: string }>`
- `feishuLogin(code: string, state: string): Promise<AuthServiceLoginResponse>`（与现有 `login()` 返回结构一致）

### 5.4 `authStore.ts`

- 新增 `loginWithFeishu(code, state)` action：调 `feishuLogin`，复用现有登录成功后的 localStorage 写入（`auth-isAuthenticated` / `auth-user` / `auth-accessToken` / `auth-refreshToken`）与 `loadUserPermissions()` 逻辑

## 6. 飞书开放平台配置（需手动完成）

1. 应用「安全设置」→ 添加重定向 URL：`http://localhost:5173/login/feishu/callback`（生产环境追加生产域名）
2. 开通「获取用户基本信息」权限（`contact:user.base:readonly` 等）并发布应用版本

## 7. 测试要点

- 后端：state 签名/过期校验；已有邮箱命中登录；新邮箱自动建号（含 username 冲突后缀）；无邮箱报错；飞书接口异常降级
- 前端：飞书登录按钮跳转；回调页正常登录跳首页；取消授权/失败提示与返回登录
