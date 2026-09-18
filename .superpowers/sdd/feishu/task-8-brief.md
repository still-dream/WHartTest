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
