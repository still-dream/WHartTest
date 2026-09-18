# Task 1 简报：后端配置 FEISHU_REDIRECT_URI

> 本简报是你的需求文档，其中的精确值（代码、URL、变量名）必须逐字使用。

## Files

- Modify: `SkillForge_Django\skillforge_django\settings.py`（752-756 行现有 FEISHU 区块）
- Modify: `SkillForge_Django\.env.example`（文件末尾，Qdrant 区块之后）
- Modify: `SkillForge_Django\.env`（若存在；本地运行配置，不在 git 内）

## Step 1: 修改 settings.py

在现有 FEISHU 区块（`FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')` 之后）追加：

```python
# 飞书 OAuth 登录回调地址（前端回调页路由），需与飞书开放平台「重定向 URL」一致
FEISHU_REDIRECT_URI = os.environ.get(
    'FEISHU_REDIRECT_URI', 'http://localhost:5173/login/feishu/callback'
)
```

## Step 2: 修改 .env.example

在文件末尾（`QDRANT_URL=http://127.0.0.1:8918` 之后）追加：

```ini

# ============================== 飞书 OAuth 登录 ==============================
# 飞书开放平台应用凭证（OAuth 登录用；与上方通知功能共用同名变量，配置一个应用即可）
# FEISHU_APP_ID=cli_xxx
# FEISHU_APP_SECRET=xxx
# OAuth 回调地址，必须与飞书开放平台「安全设置-重定向 URL」中登记的地址完全一致
FEISHU_REDIRECT_URI=http://localhost:5173/login/feishu/callback
```

## Step 3: 更新本地 .env（若存在）

确认 `.env` 中 `FEISHU_APP_ID=cli_aa21520c0bb89cde`、`FEISHU_APP_SECRET=xxx`（若已有通知用途的同名值则保持一致即可），并新增 `FEISHU_REDIRECT_URI=http://localhost:5173/login/feishu/callback`。

## Step 4: 验证配置生效

运行（cwd：`SkillForge_Django`）：

```
python manage.py shell -c "from django.conf import settings; print(settings.FEISHU_REDIRECT_URI)"
```

预期输出 `http://localhost:5173/login/feishu/callback`。

## Step 5: Commit

```
git add SkillForge_Django/skillforge_django/settings.py SkillForge_Django/.env.example
git commit -m "feat: 新增飞书 OAuth 登录回调地址配置"
```

---

## 全局约束（适用本任务）

- commit 格式沿用仓库惯例：`feat: 中文描述`
- 代码注释一律中文
- 工作目录：`c:\app\SkillForge`（仓库根）；后端目录：`c:\app\SkillForge\SkillForge_Django`
- 当前分支：`feat/feishu-login`（已创建，直接在此分支提交）
