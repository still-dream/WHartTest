# Task 8 报告：全量验证与手动测试清单

- 分支：`feat/feishu-login`（HEAD `582cb62`，Task 1-7 共 7 个 feat commit）
- 验证日期：2026-09-17
- 结论：**飞书 OAuth 功能本身全部验证通过，无回归**；`npm run build` 因 4 个与本功能无关的存量 TS 错误失败（已用基线 commit 复现证实为存量问题，非 Task 1-7 引入）。

## 一、验证步骤与结果

### Step 1: 后端全量测试 — ✅ 通过

命令（cwd `WHartTest_Django`，按环境备忘使用 venv）：

```
venv\Scripts\python.exe manage.py test accounts -v 2
```

实际输出摘要：

- `Ran 27 tests in 8.119s` → **OK**，退出码 0。
- 测试构成（共 27 个，全部通过）：
  - `FeishuLoginViewTests` 8 个（邮箱匹配登录 / token 错误返回 400 / 停用用户视为不存在并建新号 / state 无效拒绝 / 缺 code 或 state 拒绝 / 缺邮箱拒绝 / 新用户默认密码 / username 冲突加后缀）
  - `FeishuAuthorizeUrlViewTests` 2 个（未配置返回 503 / 返回授权地址与 state）
  - `FeishuServiceTests` 9 个（授权 URL 参数 / token 交换 / 用户信息 / state 签名往返、过期、篡改、格式错误）
  - 存量回归：`MyTokenObtainPairViewTests` 1 个、`ContentTypeSerializerMenuGroupingTests` 3 个、`ApiLocalizationTests` 4 个 — 全部通过，**无回归**。

### Step 2: 前端构建验证 — ⚠️ 部分通过（失败项均为与本功能无关的存量问题）

命令（cwd `WHartTest_Vue`）：

```
npm run build
```

实际输出：`vue-tsc -b` 阶段失败（退出码 1），4 个 TS 错误：

| 文件 | 错误 |
|---|---|
| `src/features/api-testing/components/testtasks/TestTaskExecutionDetail.vue`(80,5) | TS2322: `Timeout` 不能赋给 `number` |
| `src/features/api-testing/components/testtasks/TestTaskExecutionHistory.vue`(274,5) | TS2322: `Timeout` 不能赋给 `number` |
| `src/features/task-center/components/TaskFormModal.vue`(99,17) | TS2367: `TaskModule` 与 `"api_automation"` 类型无重叠 |
| `src/views/OperationLogManagementView.vue`(152,54) | TS2339: `UserInfo` 上不存在 `is_superuser` |

**存量问题取证**：切到基线 commit `74f2139`（Task 1 之前）执行 `npx vue-tsc -b --force`，**4 个错误逐字复现**，且错误文件均不在 Task 1-7 改动范围内（改动仅 11 个文件，见 `git diff --stat 74f2139..582cb62`）；飞书相关文件（`FeishuCallbackView.vue`、`LoginView.vue`、`authService.ts`、`authStore.ts`、`router/index.ts`）**0 个类型错误**。`UserInfo`/`ApiTokenResponseData` 定义未被修改（符合全局约束 6）。

**产物打包复核**：`npx vite build` → ✅ 成功（`✓ built in 40.62s`，3153 modules transformed，产出完整 dist），仅存量告警（大 chunk、caniuse-lite 过期、dynamic import 提示），无飞书相关错误。即 Task 1-7 前端代码可正常编译打包。

### Step 3: Commit — 跳过

按简报「若有修复则提交；无修改则跳过」。Task 1-7 代码无需修复，本任务未产生任何代码修改，故无新 commit。`git status` 确认无代码改动（仅 superpowers/docs 计划类文件为未跟踪状态，非本任务产物）。

## 二、手动测试清单（需人工 / 浏览器执行）

### 前置配置（飞书开放平台，应用 `cli_aa21520c0bb89cde`）

1. 「安全设置」→「重定向 URL」添加 `http://localhost:5173/login/feishu/callback`（生产环境需另加对应域名地址，并同步设置 `FEISHU_REDIRECT_URI` 环境变量）。
2. 「权限管理」开通：`获取用户基本信息`（authen 相关，user_info 接口必需）、`获取用户邮箱` 相关权限；然后「版本管理与发布」创建版本并发布（权限变更需发布后生效）。

### 验证路径

| # | 场景 | 操作 | 预期 |
|---|---|---|---|
| 1 | 登录页布局 | 打开 `/login` | 两个 launcher（账号登录 / 飞书登录）并排展示、大小一致；640px 以下纵向堆叠 |
| 2 | 跳转授权 | 点击「飞书登录」 | 跳转飞书授权页，URL 含 `response_type=code` 与 state |
| 3 | 授权成功 | 授权 → 等待回调 | 回调页短暂 loading → 提示「登录成功」→ 进入 Dashboard；`localStorage` 中 `auth-user` 的 `first_name` 为飞书名称 |
| 4 | 新邮箱用户 | 用全新邮箱的飞书账号登录 | Django 后台确认用户已创建，username 为邮箱前缀，密码 `Jt123456` 可登录（可用账号密码方式复核） |
| 5 | 已有同邮箱账号 | 用与既有账号同邮箱的飞书账号登录 | 登录后 username 不变，无新用户产生 |
| 6 | 取消授权 | 飞书授权页点「取消」 | 回调页显示「已取消授权」+「返回登录」按钮可用 |
| 7 | state 篡改 | 篡改回调 URL 的 state 参数 | 回调页显示登录失败及后端 detail 信息 |
| 8 | username 冲突 | 预先创建 username 同邮箱前缀的其他用户，再飞书登录 | 新账号 username 带数字后缀 |

## 三、发现的问题

1. **存量 TS 错误 4 个（非本功能引入，导致 `npm run build` 失败）**：已在基线 commit `74f2139` 复现证实。涉及 api-testing 测试任务组件（2 处 `Timeout`/`number` 定时器类型）、task-center `TaskFormModal`（枚举比较）、`OperationLogManagementView`（`is_superuser` 字段不在 `UserInfo` 类型上）。因简报明确本任务「无代码修改」且这些问题与飞书登录无关，未越权修复，建议另开任务处理。
2. 后端测试出现一次无害告警 `USER_AGENT environment variable not set`（来自依赖库，不影响结果）。
3. 手动测试清单按简报记录于本报告（简报 Files 标注「无代码修改」，未要求另建清单文档）。
