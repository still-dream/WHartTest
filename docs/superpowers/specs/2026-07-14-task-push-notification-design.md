# 任务中心推送通知功能 - 设计规格

> 日期: 2026-07-14
> 状态: 已批准（待用户最终审查）
> 基于: brainstorming skill 流程产出

---

## 1. 概述

### 1.1 功能目标

为任务中心新增三项能力：

1. **APPUI 自动化任务支持**：任务中心表单支持创建 APPUI 自动化测试任务（后端模型已部分存在，需补全序列化器和前端表单）
2. **Webhook 推送地址管理**：在系统管理模块中配置飞书机器人 webhook 地址，仅管理员可查看和编辑
3. **消息模板与推送**：任务执行完成后向订阅的飞书群推送消息，支持默认格式模板、引入模板后编辑、变量替换

### 1.2 关键决策摘要

| 决策点 | 选择 | 说明 |
|--------|------|------|
| 推送平台 | 飞书 | 仅支持飞书自定义机器人 webhook |
| 推送时机 | 任务级可配 | 总是推送 / 仅失败时推送 / 不推送，默认总是推送 |
| 订阅关系 | 多对多 | 一个任务可订阅多个推送地址 |
| 模板模型 | 任务级保存 | 消息内容按任务独立保存；可选从共享模板库引入再编辑 |
| 模板库 | 所有用户可维护 | 所有认证用户可新增模板，创建者可编辑删除自己的模板 |
| Webhook 管理 | 全局，管理员专属 | 在系统管理模块配置，仅管理员可查看完整信息和编辑 |
| 架构方案 | 新建 notifications app | 推送地址、模板库、推送服务统一内聚 |
| 消息格式 | Markdown + 飞书卡片 | 用户编辑 Markdown，发送时包装为飞书交互卡片 |
| 变量系统 | 简单字符串替换 | `{{var}}` 占位符替换，不引入模板引擎 |

### 1.3 现有代码缺口修复

后端 `ScheduledTask` 模型已定义 `APP_UI_AUTOMATION` 模块类型和 `app_ui_scripts`/`app_ui_device` 字段，`tasks.py` 已实现执行逻辑，但存在以下缺口：
- `ScheduledTaskSerializer.fields` 未包含 `app_ui_scripts` 和 `app_ui_device`
- 前端模块下拉仅有 `ui_automation` 和 `test_suite` 两个选项
- 前端 `TaskModule` 类型定义缺少 `app_ui_automation`

本设计一并修复这些缺口。

---

## 2. 架构概览

### 2.1 新建 `notifications` 应用

```
WHartTest_Django/notifications/
├── models.py          # WebhookAddress + MessageTemplate
├── views.py           # 视图集 (WebhookAddressViewSet, MessageTemplateViewSet)
├── serializers.py     # 序列化器
├── urls.py            # 路由
├── services.py        # 飞书推送服务 (变量渲染 + HTTP 发送)
├── variables.py       # 变量注册表与上下文构建
├── admin.py
├── apps.py
└── migrations/
```

注册到 `INSTALLED_APPS`，URL 前缀 `api/notifications/`。

### 2.2 组件职责

| 组件 | 职责 |
|------|------|
| `WebhookAddress` 模型 | 存储飞书机器人 webhook 地址（全局，管理员管理） |
| `MessageTemplate` 模型 | 共享模板库（所有用户可增删改查自己的模板） |
| `services.py` | 接收执行上下文 + webhook 地址 + 消息内容，渲染变量，发送飞书卡片 |
| `variables.py` | 定义可用变量列表，从任务执行结果构建变量上下文 |

### 2.3 `task_center` 改动

- **模型**：`ScheduledTask` 新增推送配置字段（推送策略、订阅的 webhook 地址 M2M、消息内容）
- **序列化器**：补全 `app_ui_scripts`/`app_ui_device`（修复已有缺口）+ 新增推送字段
- **tasks.py**：任务执行完成后，检查推送策略并调用 `notifications.services` 发送消息

### 2.4 推送数据流

```
任务执行完成 (task_center/tasks.py)
    │
    ├─ 检查 push_config: disabled->跳过, failure_only+成功->跳过
    │
    ├─ 构建变量上下文 (notifications/variables.py)
    │   -> {task_name, project_name, status, total, passed, failed, ...}
    │
    ├─ 渲染消息内容 (变量替换 {{task_name}} -> 实际值)
    │
    └─ 遍历订阅的 webhook 地址 (notifications/services.py)
        -> 包装为飞书交互卡片 (绿色头=成功, 红色头=失败)
        -> HTTP POST 发送到飞书 webhook URL
```

---

## 3. 数据模型

### 3.1 WebhookAddress（推送地址）

```python
class WebhookAddress(models.Model):
    """飞书 Webhook 推送地址（全局，仅管理员管理）"""
    PLATFORM_CHOICES = [('feishu', '飞书')]

    name = models.CharField('地址名称', max_length=100)
    url = models.URLField('Webhook URL')
    platform_type = models.CharField(
        '平台类型', max_length=20, choices=PLATFORM_CHOICES, default='feishu'
    )
    description = models.TextField('描述', blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '推送地址'
        verbose_name_plural = '推送地址'
        ordering = ['-created_at']
```

### 3.2 MessageTemplate（消息模板）

```python
class MessageTemplate(models.Model):
    """消息模板库（所有用户可维护）"""
    PLATFORM_CHOICES = [('feishu', '飞书')]

    name = models.CharField('模板名称', max_length=100)
    content = models.TextField(
        '模板内容', help_text='Markdown格式，支持{{变量}}占位符'
    )
    platform_type = models.CharField(
        '平台类型', max_length=20, choices=PLATFORM_CHOICES, default='feishu'
    )
    description = models.TextField('描述', blank=True, default='')
    is_system = models.BooleanField('系统内置', default=False)
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '消息模板'
        verbose_name_plural = '消息模板'
        ordering = ['-is_system', '-created_at']
```

### 3.3 ScheduledTask 模型扩展

在现有 `ScheduledTask` 模型上新增字段：

```python
class PushConfig(models.TextChoices):
    ALWAYS = 'always', '总是推送'
    FAILURE_ONLY = 'failure_only', '仅失败时推送'
    DISABLED = 'disabled', '不推送'

# 新增字段
push_config = models.CharField(
    '推送策略', max_length=20,
    choices=PushConfig.choices, default='always'
)
webhook_addresses = models.ManyToManyField(
    WebhookAddress, blank=True, verbose_name='推送地址'
)
push_message_content = models.TextField(
    '推送消息内容', blank=True, default='',
    help_text='Markdown格式，支持{{变量}}'
)
```

### 3.4 系统内置默认模板

系统初始化时（通过 data migration）自动创建一个内置模板（`is_system=True`），内容如下：

```markdown
## {{task_name}} 执行{{status}}

**项目**: {{project_name}}
**触发方式**: {{trigger_type}}
**执行人**: {{executor}}
**执行时间**: {{current_date}}
**执行时长**: {{duration}}

### 执行统计
- 用例总数: {{total}}
- 通过: {{passed}}
- 失败: {{failed}}
- 通过率: {{pass_rate}}

### 失败用例
{{failed_cases}}

[查看完整报告]({{report_url}})
```

### 3.5 模型关系

```
WebhookAddress (全局)          MessageTemplate (共享库)
       │                              │
       │ M2M                          │ 引入(复制内容)
       ▼                              ▼
ScheduledTask ──── push_message_content (任务级独立保存)
       │
       │ FK
       ▼
  TaskExecution (执行记录)
```

- `WebhookAddress` 是全局资源，多个任务可订阅同一个地址
- `MessageTemplate` 是共享库，引入时仅复制内容到任务的 `push_message_content`，后续编辑互不影响
- `ScheduledTask.webhook_addresses` 为 M2M，一个任务可订阅多个地址

---

## 4. 变量系统与推送服务

### 4.1 变量注册表

在 `notifications/variables.py` 中定义所有可用变量：

| 分类 | 变量名 | 说明 | 示例值 |
|------|--------|------|--------|
| 任务信息 | `{{task_name}}` | 任务名称 | "登录模块回归测试" |
| | `{{project_name}}` | 项目名称 | "J&T Express" |
| | `{{status}}` | 执行状态 | 成功 / 失败 |
| | `{{trigger_type}}` | 触发方式 | 定时 / 手动 / API |
| 执行统计 | `{{total}}` | 用例总数 | 15 |
| | `{{passed}}` | 通过数 | 13 |
| | `{{failed}}` | 失败数 | 2 |
| | `{{pass_rate}}` | 通过率 | 86.7% |
| | `{{duration}}` | 执行时长 | 5分23秒 |
| 人员详情 | `{{executor}}` | 执行人 | admin |
| | `{{failed_cases}}` | 失败用例列表 | test_login / test_payment（无失败时显示"无"） |
| | `{{error_summary}}` | 错误摘要 | "2个用例执行失败" |
| 日期链接 | `{{current_date}}` | 当前日期时间 | 2026-07-14 15:30:00 |
| | `{{report_url}}` | 报告链接 | https://... |
| | `{{task_url}}` | 任务详情链接 | https://... |
| | `{{platform_name}}` | 平台名称 | WHartTest |

### 4.2 变量上下文构建

`notifications/variables.py` 中的 `build_context(task, execution, module_result)` 函数根据任务模块类型从对应的执行记录中提取统计数据：

```
task_center/tasks.py 执行完成后
    │
    ├─ 获取 TaskExecution 记录（status, started_at, finished_at）
    │
    ├─ 根据 task.module 获取模块级执行结果:
    │   ├─ app_ui_automation -> AppUiBatchExecutionRecord (统计脚本通过/失败)
    │   ├─ ui_automation -> UiTestCase 执行记录
    │   └─ test_suite -> TestSuite 执行结果
    │
    └─ 合并为统一变量上下文字典
```

### 4.3 变量渲染

采用简单的字符串替换（`{{var}}` -> 值），不引入模板引擎依赖：

```python
def render_content(content: str, context: dict) -> str:
    for key, value in context.items():
        content = content.replace(f'{{{{{key}}}}}', str(value))
    return content
```

### 4.4 飞书卡片格式

推送时将渲染后的 Markdown 包装为飞书交互卡片（`msg_type: interactive`）：

```
┌─────────────────────────────────────┐
│  测试任务执行通知          (绿色/红色头) │  ← header: 成功=green, 失败=red
├─────────────────────────────────────┤
│  ## 登录模块回归测试 执行成功           │
│                                      │
│  **项目**: J&T Express               │  ← 用户编辑的 Markdown 内容
│  **执行人**: admin                    │     (变量已替换为实际值)
│  **通过率**: 86.7%                    │
│  ...                                 │
├─────────────────────────────────────┤
│  [查看完整报告]    [任务详情]          │  ← action buttons
└─────────────────────────────────────┘
```

卡片结构：
- **Header**：标题"测试任务执行通知"，颜色随状态变化（成功绿色 / 失败红色）
- **Body**：用户编辑的 Markdown 内容（变量已替换），作为 `markdown` 元素
- **Actions**：两个按钮--"查看完整报告"链接到 `report_url`，"任务详情"链接到 `task_url`

### 4.5 推送服务流程

```python
# notifications/services.py

def send_task_notification(task, execution, module_result):
    """任务执行完成后调用"""
    # 1. 检查推送策略
    if task.push_config == 'disabled':
        return
    if task.push_config == 'failure_only' and execution.status == 'success':
        return

    # 2. 构建变量上下文
    context = build_context(task, execution, module_result)

    # 3. 渲染消息内容
    rendered = render_content(task.push_message_content, context)

    # 4. 遍历订阅的 webhook 地址发送
    for addr in task.webhook_addresses.filter(is_active=True):
        card = build_feishu_card(
            rendered, context['status'],
            context['report_url'], context['task_url']
        )
        try:
            requests.post(addr.url, json=card, timeout=10)
        except Exception as e:
            logger.warning(f"推送失败 {addr.name}: {e}")
```

### 4.6 错误处理

- 推送失败（网络超时、飞书返回错误）仅记录日志，**不影响任务执行结果**
- 单个地址推送失败不影响其他地址的推送
- 推送过程在 Celery 任务内同步执行（在任务执行完成之后、Celery 任务返回之前），不额外创建异步任务

---

## 5. API 与权限设计

### 5.1 推送地址 API

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `api/notifications/webhook-addresses/` | 所有认证用户 | 列表（非管理员仅返回 id+name+is_active，隐藏 url） |
| GET | `api/notifications/webhook-addresses/{id}/` | 管理员 | 详情（含完整字段） |
| POST | `api/notifications/webhook-addresses/` | 管理员 | 新增 |
| PUT/PATCH | `api/notifications/webhook-addresses/{id}/` | 管理员 | 编辑 |
| DELETE | `api/notifications/webhook-addresses/{id}/` | 管理员 | 删除 |
| POST | `api/notifications/webhook-addresses/{id}/test/` | 管理员 | 发送测试消息 |

**权限实现**：自定义 `IsAdminOrReadOnlyName` 权限类
- 管理员（`is_superuser` 或 `is_staff`）：完整 CRUD，可查看所有字段
- 普通用户：仅可 GET 列表（用于任务表单下拉选择），序列化器隐藏 `url` 字段，仅返回 `id`、`name`、`is_active`

### 5.2 消息模板 API

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `api/notifications/message-templates/` | 所有认证用户 | 列表（全部模板） |
| GET | `api/notifications/message-templates/{id}/` | 所有认证用户 | 详情 |
| POST | `api/notifications/message-templates/` | 所有认证用户 | 新增 |
| PUT/PATCH | `api/notifications/message-templates/{id}/` | 创建者或管理员 | 编辑 |
| DELETE | `api/notifications/message-templates/{id}/` | 创建者或管理员 | 删除 |

**规则**：
- 所有认证用户可查看全部模板（共享库）
- 所有认证用户可新增模板
- 仅创建者或管理员可编辑/删除自己的模板
- `is_system=True` 的系统内置模板：不可删除，仅管理员可编辑

### 5.3 任务中心序列化器扩展

`ScheduledTaskSerializer` 新增字段：

```python
class ScheduledTaskSerializer(serializers.ModelSerializer):
    # 补全已有缺口
    app_ui_scripts = PrimaryKeyRelatedField(
        many=True, queryset=AppUiScript.objects.all(), required=False
    )
    app_ui_device = PrimaryKeyRelatedField(
        queryset=AppUiDevice.objects.all(), required=False, allow_null=True
    )

    # 新增推送配置
    push_config = ChoiceField(choices=PushConfig.choices, default='always')
    webhook_addresses = PrimaryKeyRelatedField(
        many=True,
        queryset=WebhookAddress.objects.filter(is_active=True),
        required=False
    )
    push_message_content = CharField(allow_blank=True, default='')
```

**校验逻辑**（`validate` 方法新增）：
- 当 `module == 'app_ui_automation'` 时，`app_ui_scripts` 和 `app_ui_device` 必填
- 当 `push_config != 'disabled'` 时，`push_message_content` 必填，`webhook_addresses` 至少选一个

### 5.4 模板引入

任务表单中"引入模板"按钮调用现有的 `GET /api/notifications/message-templates/` 获取模板列表，用户选择后前端将模板 `content` 填入消息内容编辑框。无需额外接口，纯前端交互。

### 5.5 系统管理菜单分类

在 `accounts/serializers.py` 的 `ContentTypeSerializer.get_app_label_cn()` 中，将 `notifications` app 归入"系统管理"菜单分类下，子分类为"推送配置"。

---

## 6. 前端设计

### 6.1 新增前端目录结构

```
WHartTest_Vue/src/features/notifications/
├── views/
│   ├── WebhookAddressView.vue    # 推送地址管理页
│   └── MessageTemplateView.vue   # 消息模板库页
├── components/
│   ├── WebhookFormModal.vue      # 地址新增/编辑弹窗
│   ├── TemplateFormModal.vue     # 模板新增/编辑弹窗
│   └── VariableHintPanel.vue     # 变量参考面板组件（可复用）
├── services/
│   └── notificationService.ts    # API 调用与类型定义
└── types/
    └── index.ts
```

### 6.2 推送地址管理页（管理员可见）

- 顶部：标题"推送地址管理" + "新增地址"按钮
- 表格列：地址名称、平台类型、URL（脱敏显示）、状态、描述、操作（编辑/测试推送/删除）
- 路由：`/system/webhook-addresses`，菜单归类"系统管理 > 推送配置"
- 新增/编辑弹窗：地址名称、Webhook URL、描述、启用状态
- 测试推送：点击后发送一条测试卡片消息，显示成功/失败提示

### 6.3 消息模板库页（所有用户可见）

- 顶部：标题"消息模板库" + "新增模板"按钮
- 表格列：模板名称、平台类型、内置标记（系统内置/用户创建）、创建人、更新时间、操作
- 操作列：编辑、删除（系统内置模板不可删除，仅管理员可编辑）
- 路由：`/system/message-templates`，菜单归类"系统管理 > 推送配置"
- 新增/编辑弹窗：
  - 模板名称、描述
  - 内容编辑区（左编辑右预览布局）：
    - 左侧：Markdown 文本编辑框 + 变量插入栏（点击变量按钮在光标处插入 `{{var}}`）
    - 右侧：实时 Markdown 预览

### 6.4 变量参考面板组件

`VariableHintPanel.vue` 为可复用组件，在模板编辑弹窗和任务表单的消息内容编辑区均使用：
- 展示所有可用变量及说明
- 点击变量可插入到关联的编辑框光标位置
- 可折叠/展开

### 6.5 任务中心表单扩展

修改现有 `TaskFormModal.vue`：

**a) 模块下拉新增 APPUI 选项**：

```
UI 自动化 (ui_automation)
测试套件 (test_suite)
APPUI 自动化 (app_ui_automation)  ← 新增
```

**b) APPUI 模块联动字段**（当 module = app_ui_automation 时显示）：
- 脚本选择：多选弹窗（从 `api/app-ui-automation/scripts/` 获取，复用现有选择弹窗模式）
- 执行设备：下拉选择（从 `api/app-ui-automation/devices/` 获取）

**c) 推送配置区**（所有模块通用，位于调度配置下方）：
- 推送策略：单选（总是推送 / 仅失败时推送 / 不推送），默认"总是推送"
- 当策略 != 不推送时显示：
  - 推送地址：下拉多选飞书地址（从 `api/notifications/webhook-addresses/` 获取）
  - 消息内容："引入模板"下拉按钮 + Markdown 编辑框
  - 变量参考：可折叠面板（复用 `VariableHintPanel.vue`）
- "引入模板"下拉：获取模板库列表，选择后将模板 content 填入编辑框（覆盖现有内容前弹出确认）

### 6.6 前端路由与菜单

新增路由注册在 `router/index.ts`：

```typescript
{
  path: '/system/webhook-addresses',
  component: WebhookAddressView,
  meta: { requiresAdmin: true }
},
{
  path: '/system/message-templates',
  component: MessageTemplateView
}
```

菜单分类在系统管理下新增"推送配置"子分类，包含两个页面入口。

---

## 7. 实现范围

### 7.1 后端改动清单

| 文件 | 改动 |
|------|------|
| `notifications/` (新建) | 完整新 app：models, views, serializers, urls, services, variables, admin, apps, migrations |
| `wharttest_django/settings.py` | INSTALLED_APPS 新增 `notifications` |
| `wharttest_django/urls.py` | 注册 `api/notifications/` 路由 |
| `task_center/models.py` | ScheduledTask 新增 push_config, webhook_addresses, push_message_content 字段 + PushConfig 枚举 |
| `task_center/serializers.py` | 新增 app_ui_scripts, app_ui_device, push_config, webhook_addresses, push_message_content 字段 + 校验 |
| `task_center/tasks.py` | 任务执行完成后调用 `notifications.services.send_task_notification` |
| `accounts/serializers.py` | ContentTypeSerializer 新增 notifications app 的中文映射 |

### 7.2 前端改动清单

| 文件 | 改动 |
|------|------|
| `features/notifications/` (新建) | 完整新功能模块：views, components, services, types |
| `features/task-center/components/TaskFormModal.vue` | 模块下拉新增 APPUI 选项 + APPUI 联动字段 + 推送配置区 |
| `features/task-center/services/taskService.ts` | TaskModule 类型新增 app_ui_automation + TaskFormData 新增推送字段 |
| `router/index.ts` | 新增推送地址和模板库路由 |
| 菜单配置 | 系统管理下新增"推送配置"子分类 |

### 7.3 数据迁移

- 创建 `notifications` app 的初始 migration（WebhookAddress + MessageTemplate 表）
- 创建 `task_center` 的 migration（ScheduledTask 新增字段）
- 创建 data migration：插入系统内置默认模板
