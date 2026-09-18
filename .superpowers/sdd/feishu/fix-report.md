# 飞书登录 Important Findings 修复报告

- 分支：`feat/feishu-login`
- Commit：`2c0e7eb` `fix: state 增加随机串防重放，飞书匿名端点添加限流`
- 日期：2026-09-17
- 测试结果：**32/32 passing**（基线 27 + 新增 5），输出与基线一致、无新增杂音

---

## 一、实现内容

### I-1 state 增加随机串（防预伪造重放）

**文件：`SkillForge_Django/accounts/feishu.py`**

- `build_state()`：由 `时间戳.HMAC(时间戳)` 改为 **`随机串.时间戳.HMAC(随机串+时间戳)`** 三段格式。
  随机串使用 `secrets.token_urlsafe(16)`（CSPRNG，每次调用唯一）。
- `verify_state()`：按 3 段解析（`state.count(".") != 2` 拒绝）；校验随机串非空、时间戳为数字；
  用 `hmac.compare_digest` 对 `HMAC(SECRET_KEY, 随机串+时间戳)` 做**常量时间比较**；
  保留 10 分钟 TTL 语义（`time.time() - int(timestamp) <= STATE_TTL_SECONDS`）。
  校验失败仍返回 `False`，由 `FeishuLoginView` 转为 400，调用方契约不变。
- `sign_state(payload)`：签名载荷参数从"时间戳"泛化为"随机串+时间戳"字符串，函数名与导出不变。
- `FeishuAuthError`、token 交换、用户信息获取、`build_authorize_url` 均未改动；前端零改动（仅透传 state）。

### I-2 匿名端点限流

**文件：`SkillForge_Django/accounts/views.py`**

- 新增 `FeishuAuthThrottle(AnonRateThrottle)`，类属性 `rate = "10/min"`（每 IP 每分钟 10 次）。
- **方案选择依据**：读取 `skillforge_django/settings.py` 后确认 `REST_FRAMEWORK` 中不存在
  `DEFAULT_THROTTLE_CLASSES` / `DEFAULT_THROTTLE_RATES`，项目无 scope 式节流配置模式，
  故采用任务建议的类属性 `rate` 方案（DRF `SimpleRateThrottle.__init__` 优先读取类属性 `rate`，
  完全绕开全局 settings，零影响其他端点）。
- `throttle_classes = [FeishuAuthThrottle]` 应用于 `FeishuAuthorizeUrlView` 与 `FeishuLoginView`。
- DRF 节流在 `initial()` 中先于业务 handler 执行，即使请求会 400/503 也先计数，有效封顶出站 HTTPS 放大量。

**测试隔离（关键陷阱处理）**

`accounts/tests.py` 中 `FeishuLoginViewTests` 与 `FeishuAuthorizeUrlViewTests` 的 `setUp` 均执行
`django.core.cache.cache.clear()`：DRF 节流基于 locmem cache 按 IP（`127.0.0.1`）计数且跨测试用例共享，
逐用例清空保证 10 个既有视图测试互不污染、不触发 429。

---

## 二、TDD 证据（RED → GREEN）

### I-1 RED（先改测试，旧实现下运行）

更新 4 个既有 state 测试并新增 2 个：

| 测试 | 旧行为下结果 |
| --- | --- |
| `test_state_roundtrip_verification`（断言 3 段结构） | FAIL `AssertionError: 2 != 3` |
| `test_build_state_generates_unique_nonce`（patch `time.time` 固定同一秒） | FAIL 两次 state 完全相同 |
| `test_verify_state_accepts_nonce_signed_state`（手工构造 `nonce.timestamp.HMAC(nonce+timestamp)`） | FAIL `False is not true` |
| `test_verify_state_rejects_tampered_nonce`（解包 3 段） | ERROR `unpack expected 3, got 2`（同样源于旧两段格式） |
| `test_verify_state_rejects_tampered_signature` / `..._expired_timestamp` / `..._malformed_state`（改造为新格式构造） | PASS（守护测试：拒绝语义新旧等价） |

命令：`venv\Scripts\python.exe manage.py test accounts.tests.FeishuServiceTests`
输出：`FAILED (failures=3, errors=1)` —— 失败原因均为新格式特性缺失，符合预期。

### I-1 GREEN

同命令输出：`Ran 12 tests ... OK`。

### I-2 RED（先加测试，未实现节流）

- `FeishuLoginViewTests.test_login_throttled_after_rate_limit`：FAIL `AssertionError: 400 != 429`
- `FeishuAuthorizeUrlViewTests.test_throttled_after_rate_limit`：FAIL `AssertionError: 200 != 429`
- 同时验证：`cache.clear()` 加入 setUp 后其余 10 个视图测试仍全部通过。

命令：`venv\Scripts\python.exe manage.py test accounts.tests.FeishuLoginViewTests accounts.tests.FeishuAuthorizeUrlViewTests`
输出：`FAILED (failures=2)`，其余 10 个 PASS。

### I-2 GREEN + 全量回归

命令：`venv\Scripts\python.exe manage.py test accounts`（SkillForge_Django 目录下）

```
Ran 32 tests in 5.153s
OK
```

与基线（27/27）输出对比：仅新增测试数量，`USER_AGENT environment variable not set` 提示与
3 行 Django request-logging WARNING（Unauthorized/Forbidden/Bad Request）均为基线既有，未引入新杂音。

---

## 三、变更文件

| 文件 | 变更 |
| --- | --- |
| `SkillForge_Django/accounts/feishu.py` | `import secrets`；`sign_state` 载荷泛化；`build_state` 三段随机串格式；`verify_state` 三段解析 + 非空随机串校验 |
| `SkillForge_Django/accounts/views.py` | `import AnonRateThrottle`；新增 `FeishuAuthThrottle`；两个飞书视图添加 `throttle_classes` |
| `SkillForge_Django/accounts/tests.py` | 改造 4 个 state 测试 + 新增 3 个（唯一 nonce / 新格式签名 / 篡改 nonce）；两个视图测试类 setUp 清 cache；新增 2 个 429 用例 |

统计：3 files changed, 94 insertions(+), 13 deletions(-)

---

## 四、自我审查发现

1. **签名必须覆盖随机串**：`test_verify_state_accepts_nonce_signed_state` 直接以 `sign_state(f"{nonce}{timestamp}")`
   拼接契约构造合法 state，锁定签名必须覆盖随机串；`test_verify_state_rejects_tampered_nonce`
   保证换随机串不换签名时被拒。攻击者即使拿到 10 分钟内的旧 state 也无法为新的随机串伪造签名。
2. **守护测试无法 RED 的说明**：`tampered_signature / expired / malformed / tampered_nonce` 四个拒绝类
   用例在旧实现下也返回 `False`（旧实现因格式解析失败拒绝），属行为守护而非驱动测试；驱动新行为的
   3 个接受/唯一性测试均已验证 RED。这是 TDD 下"拒绝语义不变"类改造的固有形态。
3. **限流对合法用户的影响**：10/min 按 IP 计，正常登录流程（authorize-url + login）单用户远低于阈值；
  若企业出口 NAT 后多用户共享 IP，极端场景可能触顶——属已批准方案的既定取舍。
4. **节流 cache 依赖**：节流计数存于默认 locmem cache，多进程部署（daphne 多 worker）下各进程独立计数，
   实际限速为 `10/min × worker 数`；单 worker 部署精确。如需精确全局限速需换 Redis cache，超出本次范围。
5. **无意范围外改动**：未触碰其他 Minor findings、`FeishuAuthError` 语义、前端代码与 settings.py。
   工作区中 `progress.md` 修改与 `docs/superpowers/` 未跟踪文件为修复前已存在，未纳入本 commit。
6. **畸形 state 防御补充**：空随机串（`.123456.xxx`）、4 段、非数字时间戳、两段式旧格式均在
   `verify_state` 中拒绝，`state=None`/空串由 `not state` 分支处理，无异常路径。
