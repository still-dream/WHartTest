# Task 2 报告：后端服务层 accounts/feishu.py（TDD）

## What I Implemented

按简报逐字转写，TDD 流程执行：

1. **新建 `WHartTest_Django/accounts/feishu.py`**（125 行）：飞书 OAuth 服务层，含
   - `FeishuAuthError`（属性 `code`）
   - `sign_state` / `build_state` / `verify_state`（HMAC-SHA256 签名 + 600s TTL，`hmac.compare_digest` 防时序攻击）
   - `build_authorize_url`（response_type=code / client_id / redirect_uri / state）
   - `exchange_code_for_token`（v3 扁平 token 端点，code==0 且有 access_token 才成功）
   - `get_feishu_user`（Bearer user_access_token，返回 `data` 字段）
   - 注释/docstring/错误消息全部中文，与简报逐字一致
2. **修改 `WHartTest_Django/accounts/tests.py`**：
   - 导入区：新增 `import time`；`from django.test import SimpleTestCase` 合并为 `from django.test import SimpleTestCase, override_settings`；新增 `from accounts.feishu import (...)` 块（与实现公开的 `sign_state` 一致，采用简报"二选一"中的第一种）
   - 文件末尾追加 `FeishuServiceTests`（`@override_settings` 覆盖三个 FEISHU 配置）共 9 个测试，逐字来自简报

## TDD Evidence

### RED

- 命令：`venv\Scripts\python.exe manage.py test accounts -v 2`（cwd：`c:\app\WHartTest\WHartTest_Django`，此时已写入测试、尚未创建 `accounts/feishu.py`）
- 关键输出：
  ```
  Found 5 test(s).
  ERROR: accounts.tests (unittest.loader._FailedTest.accounts.tests)
  ImportError: Failed to import test module: accounts.tests
    File "C:\app\WHartTest\WHartTest_Django\accounts\tests.py", line 9, in <module>
      from accounts.feishu import (
  ModuleNotFoundError: No module named 'accounts.feishu'
  FAILED (errors=1)
  ```
- 失败原因符合预期：简报 Step 2 明确预期 `ModuleNotFoundError: No module named 'accounts.feishu'`；同时既有 4 个 `accounts.test_i18n` 测试在该次运行中全部 `ok`，证明破坏面仅来自待实现模块缺失。

### GREEN

- 命令：`venv\Scripts\python.exe manage.py test accounts -v 2`（实现写入后）
- 关键输出：9 个 `FeishuServiceTests` 全部 `ok`；`Ran 17 tests in 2.728s — OK`
- 两个错误分支测试运行时的 `logger.warning` 行（`飞书授权码换取令牌失败：…` / `获取飞书用户信息失败：…`）是实现的预期日志行为，非测试失败。

## Full Suite Result

`venv\Scripts\python.exe manage.py test accounts -v 2`：**Ran 17 tests — OK, 失败 0**
- 既有：`accounts.test_i18n` 4 个 + `accounts.tests` 既有 4 个（MyTokenObtainPairView 1 + ContentTypeSerializerMenuGrouping 3）= 8 个，全部通过
- 新增：`FeishuServiceTests` 9 个，全部通过
- `System check identified no issues`；输出中的 `USER_AGENT environment variable not set…` 为既有环境噪音（非本任务引入）

## Files Changed

- `c:\app\WHartTest\WHartTest_Django\accounts\feishu.py`（新建，125 行）
- `c:\app\WHartTest\WHartTest_Django\accounts\tests.py`（导入区融合 + 末尾追加 87 行，既有代码未动）

## Commit

- `aa2662c` `feat: 新增飞书 OAuth 服务层（授权地址/state 签名/令牌交换/用户信息）`（仅含上述 2 个文件，223 insertions / 1 deletion；工作区中本任务无关的未跟踪文件未被加入）

## Self-review Findings

- 9 个测试齐全且逐字来自简报；测试验证真实行为（真实 `urlencode`/HMAC/`settings`，仅在外部 HTTP 边界 mock `httpx.post/get`，并断言 URL、payload、headers 契约），非 mock 自证。
- `tests.py` 既有测试全部通过；无任务范围外改动。
- 环境备忘（供后续任务参考）：
  1. **必须用项目 venv**：`WHartTest_Django\venv\Scripts\python.exe`（Python 3.12.8，含 Django 5.2/httpx/langchain_community）。shell 默认 `python` 解析到全局 `C:\Python314`，缺 `langchain_community`，会导致 URL 导入链 `ModuleNotFoundError`（与 Task 2 代码无关）。
  2. 残留测试库会导致交互式删除提示在非交互 shell 中 EOFError；首次用 `--noinput` 重建后恢复正常（后续运行未再加参数）。
- 既有代码观察（未修改，超出本任务范围）：`tests.py` 中 `test_django_celery_beat_is_grouped_under_task_center` 相比同类测试缺少最后一行 `get_app_label_sort(...), 5)` 断言（仓库既有状态，方法语法合法、测试通过）。Task 3+ 无需依赖它，仅供知悉。

## Issues or Concerns

- 无阻塞问题。唯一关注点即上述"必须使用项目 venv 运行测试"的环境约束，已在本报告中给出确切解释器路径。

## Fix Report

**Finding**：`accounts/feishu.py` 的 `exchange_code_for_token`（原 98 行）与 `get_feishu_user`（原 121 行）失败分支的 `logger.warning(...)` 经 stdlib `lastResort` 打到 stderr，导致两个错误分支测试运行时输出有 WARNING 杂音。

**改动**（仅 `WHartTest_Django/accounts/tests.py` 两个测试，其余不变）：

1. `test_exchange_code_for_token_raises_on_error_code`：触发调用改由 `self.assertLogs('accounts.feishu', level='WARNING')` 包裹（内层保留 `assertRaises(FeishuAuthError)`），并新增断言 `assertIn('飞书授权码换取令牌失败', captured_logs.output[0])`（与 `feishu.py` 第 98 行日志文案一致）。
2. `test_get_feishu_user_raises_on_error_code`：同样以 `assertLogs('accounts.feishu', level='WARNING')` 包裹，并新增断言 `assertIn('获取飞书用户信息失败', captured_logs.output[0])`（与 `feishu.py` 第 121 行日志文案一致）。

`assertLogs` 在测试期间接管 `accounts.feishu` logger 的 handler，既断言日志内容，又消除 stderr 杂音。

**验证**：

- 命令：`venv\Scripts\python.exe manage.py test accounts -v 2`（cwd：`c:\app\WHartTest\WHartTest_Django`）
- 结果：`Ran 17 tests in 2.958s — OK`（17/17 通过，退出码 0）
- 输出纯净性：两个错误分支测试行均为纯 `ok`，其前后无任何 feishu WARNING 行；原输出中仅剩的 3 行 WARNING（`WARNING Unauthorized/Forbidden/Bad Request: ...`）来自既有 `accounts.test_i18n` 的 Django 请求日志，与本 finding 无关、非本次引入。

**Commit**：`fc49fb6`（由原 `aa2662c` amend 而来，仍为单 commit，仅含 `accounts/feishu.py` 与 `accounts/tests.py` 两个文件）
