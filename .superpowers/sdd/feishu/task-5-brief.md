## Task 5: 前端 authStore loginWithFeishu

**Files:**

- Modify: `SkillForge_Vue\src\store\authStore.ts`（导入区 + actions 内追加）

**Interfaces:**

- Consumes：`feishuLogin as feishuLoginService`（Task 4）、既有 `loadUserPermissions()` action
- Produces：`async loginWithFeishu(code: string, state: string): Promise<boolean>`（供 Task 7 回调页消费；成功后登录态写入与 `login()` 完全一致）

**Step 1: 修改导入**

`authStore.ts` 第 2-7 行的 authService 导入块改为：

```typescript
import {
  login as loginService,
  register as registerService,
  feishuLogin as feishuLoginService,
  type AuthServiceLoginResponse,
  type AuthServiceRegisterResponse,
} from '@/services/authService';
```

**Step 2: 追加 action**

在 `actions` 内 `login(...)` 方法之后、`logout()` 之前追加：

```typescript
    /**
     * 飞书登录 Action（邮箱匹配已有账号，否则后端自动创建）
     * @param code 飞书回调携带的授权码
     * @param state 飞书回调携带的防 CSRF 状态
     * @returns 返回一个 Promise，解析为登录是否成功 (boolean)
     */
    async loginWithFeishu(code: string, state: string): Promise<boolean> {
      this.isLoading = true;
      this.loginError = null;
      try {
        const response: AuthServiceLoginResponse = await feishuLoginService(code, state);
        if (response.success && response.data) {
          this.isAuthenticated = true;
          this.user = response.data.user;
          this.accessToken = response.data.access;
          this.refreshToken = response.data.refresh;

          localStorage.setItem('auth-isAuthenticated', 'true');
          localStorage.setItem('auth-user', JSON.stringify(this.user));
          localStorage.setItem('auth-accessToken', this.accessToken);
          localStorage.setItem('auth-refreshToken', this.refreshToken);

          // 异步获取用户权限（不阻塞登录流程）
          this.loadUserPermissions().catch(error => {
            console.error('获取用户权限失败:', error);
          });

          this.isLoading = false;
          return true;
        }

        this.isAuthenticated = false;
        this.user = null;
        this.accessToken = null;
        this.refreshToken = null;
        this.loginError = response.error || '飞书登录失败，请重试。';
        localStorage.removeItem('auth-isAuthenticated');
        localStorage.removeItem('auth-user');
        localStorage.removeItem('auth-accessToken');
        localStorage.removeItem('auth-refreshToken');
        this.isLoading = false;
        return false;
      } catch (error: any) {
        this.isAuthenticated = false;
        this.user = null;
        this.accessToken = null;
        this.refreshToken = null;
        this.loginError = error.message || '发生未知错误，请稍后再试。';
        localStorage.removeItem('auth-isAuthenticated');
        localStorage.removeItem('auth-user');
        localStorage.removeItem('auth-accessToken');
        localStorage.removeItem('auth-refreshToken');
        this.isLoading = false;
        return false;
      }
    },
```

**Step 3: 验证**

```
npx vue-tsc -b
```

预期：无类型错误。

**Step 4: Commit**

```
git add SkillForge_Vue/src/store/authStore.ts
git commit -m "feat: authStore 新增飞书登录 action"
```

---
