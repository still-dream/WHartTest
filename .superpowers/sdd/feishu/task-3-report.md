# Task 3 报告：后端视图与路由（TDD）

## 实现内容

在 `WHartTest_Django\accounts` 模块内完成飞书 OAuth 登录的视图与路由层：

1. **`accounts\views.py`**
   - 导入区新增：`from django.conf import settings`、`from rest_framework_simplejwt.tokens import RefreshToken`（置于 `wharttest_django.permissions` 导入之后、`rest_framework_simplejwt.views` 导入块附近）；`.serializers` 导入块之后新增 `from .feishu import (...)` 六项（`FeishuAuthError`、`build_authorize_url`、`build_state`、`exchange_code_for_token`、`get_feishu_user`、`verify_state`）。
   - 文件末尾新增：
     - `FeishuAuthorizeUrlView`（GET，AllowAny）：未配置 `FEISHU_APP_ID`/`FEISHU_APP_SECRET` → 503「飞书登录未配置，请联系管理员。」；否则返回 200 `{authorize_url, state}`。
     - `_generate_feishu_username(email)`：取邮箱前缀生成用户名，`username__iexact` 冲突时追加数字后缀（zhangsan → zhangsan1）。
     - `FeishuLoginView`（POST，AllowAny）：缺 code/state → 400；`verify_state` 失败 → 400「登录 state 校验失败，请重新发起飞书登录。」；飞书 token/用户信息失败（`FeishuAuthError`）→ 400（`str(exc)`）；无邮箱 → 400；`OperationalError` → 503「认证服务正在启动，请稍后重试。」；按邮箱（不区分大小写）匹配活跃用户，未匹配则自动建号（默认密码 `Jt123456`，first_name=飞书姓名，is_active=True），已匹配且姓名变化则更新 first_name；成功返回 200 `{access, refresh, user}`（`UserDetailSerializer`）。

2. **`accounts\urls.py`**
   - views 导入按既有风格追加 `FeishuAuthorizeUrlView, FeishuLoginView`。
   - `me/` 路由之后插入两条：`feishu/authorize-url/`（name=`feishu-authorize-url`）、`feishu/login/`（name=`feishu-login`）。

3. **`accounts\tests.py`**
   - 导入区合并为简报最终形态：新增 `from django.contrib.auth.models import User`、`TestCase`，views 导入改为含 `FeishuLoginView` 的元组形式。
   - 末尾追加 `FeishuLoginViewTests`（8 个测试）与 `FeishuAuthorizeUrlViewTests`（2 个测试），共 10 个，与简报逐字一致（仅两处偏差，见下）。

## TDD 证据

### RED（先写测试）

命令（cwd：`WHartTest_Django`）：

```
venv\Scripts\python.exe manage.py test accounts.tests.FeishuLoginViewTests accounts.tests.FeishuAuthorizeUrlViewTests -v 2
```

关键失败输出：

```
ImportError: Failed to import test module: tests
  File "C:\app\WHartTest\WHartTest_Django\accounts\tests.py", line 20, in <module>
    from accounts.views import (
ImportError: cannot import name 'FeishuLoginView' from 'accounts.views' (...)
FAILED (errors=1)
```

**为何符合预期**：测试导入了尚不存在的 `FeishuLoginView`，与简报 Step 2 预期的 `ImportError: cannot import name 'FeishuLoginView'` 完全一致，证明测试先于实现、且确实在驱动实现。

### GREEN（实现后）

同一命令重跑：

```
Found 10 test(s).
test_existing_user_login_by_email ... ok
test_feishu_token_error_returns_400 ... ok
test_inactive_user_treated_as_absent_creates_new_account ... ok
test_invalid_state_rejected ... ok
test_missing_code_or_state_rejected ... ok
test_missing_email_rejected ... ok
test_new_user_created_with_default_password ... ok
test_new_user_username_conflict_appends_suffix ... ok
test_returns_503_when_feishu_not_configured ... ok
test_returns_authorize_url_and_state ... ok
Ran 10 tests in 3.360s
OK
```

## 全量验证

命令（cwd：`WHartTest_Django`）：

```
venv\Scripts\python.exe manage.py test accounts -v 2
```

结果：**Ran 27 tests in 7.664s — OK**（既有 17 个：MyTokenObtainPairView 1 + ContentTypeSerializerMenuGrouping 3 + FeishuServiceTests 9 + test_i18n 4，含 Task 2 全部服务层测试；新增 10 个）。

输出纯净性：
- 新增测试零 WARNING 杂音（`test_feishu_token_error_returns_400` 已用 `assertLogs` 包裹服务层 warning）。
- `test_i18n` 的 3 行 WARNING（Unauthorized/Forbidden/Bad Request）为既有测试自身行为，本次未触碰，非本次引入。
- 「USER_AGENT environment variable not set」与 MCP INFO 行为环境级噪音，RED 阶段（无任何实现时）即存在，与被测代码无关。

## 文件变更

- `WHartTest_Django\accounts\views.py`（+106 行：导入 +2 项与 feishu 导入块、2 个视图类、1 个用户名生成函数）
- `WHartTest_Django\accounts\urls.py`（+2 路由、导入追加）
- `WHartTest_Django\accounts\tests.py`（+170 行：导入区合并 + 2 个测试类 10 个测试）

Commit：`6b86779` `feat: 新增飞书登录视图与路由（邮箱匹配登录/自动建号）`（分支 `feat/feishu-login`，仅含上述 3 个文件）。

## 与简报的偏差（2 处，均为简报内部矛盾/明确备忘的处理）

1. **`test_feishu_token_error_returns_400` 增加 `assertLogs` 包裹**：该测试经 mock 触发服务层 `logger.warning("飞书授权码换取令牌失败…")`，按任务上下文备忘（Task 2 同类修复先例）用 `self.assertLogs('accounts.feishu', level='WARNING')` 包裹登录调用，避免日志经 lastResort 打到 stderr。测试断言本身未改。
2. **invalid state 的 detail 文案**：简报测试断言 `assertIn('state', response.data['detail'])`，但简报给的实现文案「登录状态校验失败，请重新发起飞书登录。」不含拉丁字母 `state`，按简报逐字实现必然挂测试（首次 GREEN 实测 9/10，正是此处失败）。以测试为契约（TDD），将文案改为「**登录 state 校验失败，请重新发起飞书登录。**」——与简报另一条消息「缺少 code 或 state 参数。」的中文夹拉丁参数名风格一致，仍为中文提示。

## Self-review 结论

- 10 个测试全部写入；RED/GREEN 证据齐全。
- 状态码约定符合全局约束：认证类失败一律 400（非 401），未配置/数据库未就绪 503，成功 200。
- username 生成：邮箱前缀 + `iexact` 冲突追加数字后缀，与测试 `zhangsan → zhangsan1` 一致。
- 成功响应 `{access, refresh, user}` 已核实命中 `renderers.py` 67-70 行 token 专门分支（message=「Token 获取成功」）；未修改 `renderers.py`。
- 全量 27/27 通过，输出无新增杂音；Task 2 测试未被改动。
- Commit 干净，仅含简报指定 3 文件；message 沿用仓库惯例。

## 问题与顾虑

- 无阻塞问题。唯一记录在案的偏差是上述 invalid state 文案（简报自相矛盾的必然取舍），如 Task 4 前端对该文案有逐字匹配的断言或展示预期，请注意其为「登录 state 校验失败，请重新发起飞书登录。」。
- 环境级噪音（USER_AGENT 提示、MCP INFO 日志）在所有测试命令中均出现，与本任务代码无关。
