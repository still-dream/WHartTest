# 全局约束（所有任务适用，逐字来自计划 Global Constraints）

1. **测试命令**：后端 `python manage.py test accounts -v 2`（cwd：`c:\app\WHartTest\WHartTest_Django`）；前端 `npx vue-tsc -b`（cwd：`c:\app\WHartTest\WHartTest_Vue`）。
2. **后端失败状态码约定**：飞书认证类失败（state 无效 / token 交换失败 / 无邮箱）一律返回 **400** 而非 401。原因：前端 `request.ts` 拦截器对所有非 `/token/` URL 的 401 触发 token 刷新流程，登录前的 401 会引发无意义的刷新与重定向，吞掉错误提示；400 不触发刷新，回调页能正常展示错误。数据库未就绪仍返回 503。
3. **响应格式**：`FeishuLoginView` 成功返回 `{access, refresh, user}`，命中 `renderers.py` 67-71 行的 token 专门分支（统一响应 message=「Token 获取成功」）。
4. **views.py 需新增 import**（已核实现有导入不含这些）：`from django.conf import settings`、`from rest_framework_simplejwt.tokens import RefreshToken`、`from .feishu import ...`。
5. **飞书图标**：使用内联 SVG，与现有 launcher 的渐变圆图标风格一致。
6. **不修改** `UserInfo`/`ApiTokenResponseData` 的既有定义方式；`FeishuCallbackView` 只消费 `AuthServiceLoginResponse`（已导出），无需导出内部接口。
7. **每个任务完成后 commit**，格式沿用仓库惯例：`feat: 中文描述`。
8. **代码注释、错误消息一律中文**，与现有代码风格一致。

环境：仓库根 `c:\app\WHartTest`，分支 `feat/feishu-login`；后端 `WHartTest_Django`，前端 `WHartTest_Vue`。
