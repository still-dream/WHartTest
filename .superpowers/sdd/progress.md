# 飞书登录功能 SDD 进度 Ledger

Base commit: 74f2139
Plan: docs/superpowers/plans/2026-09-17-feishu-login.md
Branch: feat/feishu-login

## Task Status

Task 1: complete (commits 74f2139..2a3dd7d, review clean)

Task 2: complete (commits 2a3dd7d..fc49fb6, review clean; fix: assertLogs 消音)
- Minor: token 成功用例未断言 timeout/redirect_uri 入参（覆盖面）
- Minor: exchange_code_for_token 对 FEISHU_REDIRECT_URI 直接属性访问 vs getattr 不对称
- Minor: verify_state 未来时间戳无上限（风险可忽略）

Task 3: complete (commits fc49fb6..6b86779, review clean; 简报矛盾裁决: state 错误文案含'state'以测试为契约)
- Minor (plan-mandated): username 生成 TOCTOU 竞态（并发同邮箱首登 IntegrityError→500，唯一约束兜底重试自愈）
- Minor (plan-mandated): 冲突循环无上界；超长邮箱前缀可能 DataError
- Minor: iexact 大小写不敏感匹配无专门用例；first_name 同步分支无覆盖
- Minor: test_missing_code_or_state_rejected 只覆盖缺 state 分支（简报原文如此）

Task 4: complete (commits 6b86779..58adebe, review clean)
- Minor: feishuLogin 的 CSRF_TOKEN 副本未携带既有 login() 的 TODO 背景注释（简报未含）
- Minor: catch 块行内解释注释未随模式同步（简报未含）
- Minor: CSRF_TOKEN 静态副本增至第三处（跨任务重构机会）

Task 5: complete (commits 58adebe..8be5629, review clean)
- Minor (plan-mandated): loginWithFeishu 与 login() 约 40 行样板重复（简报要求逐字转写+禁改既有代码的取舍）

Task 6: complete (commits 8be5629..ff7001c, review clean)
- Minor: 成功跳转分支 return 后 finally 仍复位 feishuLoading（整页卸载无实际影响，简报原文）
- Minor: 简报插入点描述与实际位置偏差（约束本意已满足）

Task 7: complete (commits ff7001c..582cb62, review clean)
- Minor (plan-mandated): 回调页 await loginWithFeishu 无 try/catch（依赖 Task 5 实际 Promise<boolean> 语义成立；若未来改 reject 会变未处理 rejection）
- Minor (边界记录): 已登录用户访问回调页会被守卫反重定向到 Dashboard（非本任务引入，简报未要求）
- Minor: loading spinner/错误图标无 aria-hidden/role（简报原文）

Task 8: complete (验证：后端 27/27、vite build 通过、vue-tsc 4 错误为基线存量)

## 最终整分支审查（74f2139..582cb62，结论：With fixes 后可合并）
- I-1 (Important, plan-mandated): state 缺随机串，偏离设计 §4.2 → 用户裁决：修复
- I-2 (Important): 匿名端点无限流 → 用户裁决：修复
- 其余 Minor findings 15 条：triage 后全部延后（4 条 plan 明确接受）

## 修复轮（fix commit 2c0e7eb，re-review: Approved）
- I-1 修复：build_state 改为 随机串.时间戳.HMAC(随机串+时间戳)，verify_state 三段解析+常量时间比较，TTL 语义不变，前端零改动
- I-2 修复：FeishuAuthThrottle(AnonRateThrottle) rate='10/min' 应用于两个飞书匿名视图；测试 setUp cache.clear() 隔离 + 2 个 429 用例
- 测试：32/32 passing（基线 27 + 新增 5），输出干净
- Re-review Minor（3 条，延后）：HMAC 载荷无分隔符拼接（不可利用，拼接形式即批准规格原文）；tests.py:208 旧两段格式样例语义漂移；多进程部署 locmem 限速按 worker 放大（部署层既有限制）

## 状态：全部完成，进入 finishing-a-development-branch
