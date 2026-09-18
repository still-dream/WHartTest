## Task 7: 飞书回调页与路由

**Files:**

- Create: `SkillForge_Vue\src\views\FeishuCallbackView.vue`
- Modify: `SkillForge_Vue\src\router\index.ts`（import + 路由定义 + publicRoutes）

**Interfaces:**

- Consumes：`useAuthStore().loginWithFeishu`（Task 5）、`useStarryBackground`（既有 composable）、`Message`（Arco）
- Produces：路由 `path: '/login/feishu/callback'`、`name: 'FeishuCallback'`（即后端 `FEISHU_REDIRECT_URI` 的默认值路径）；处理三分支：`code+state` 正常登录 / `error=access_denied` 取消授权 / 其他错误

**Step 1: 新建 FeishuCallbackView.vue**

```vue
<template>
  <div class="feishu-callback-page">
    <canvas ref="canvasRef" class="starry-canvas" />

    <div class="callback-card">
      <template v-if="status === 'loading'">
        <svg class="spinner" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" opacity="0.25" />
          <path fill="currentColor" opacity="0.75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <h2>飞书登录中</h2>
        <p>正在验证飞书授权信息，请稍候...</p>
      </template>

      <template v-else>
        <div class="callback-icon">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
        </div>
        <h2>{{ status === 'denied' ? '已取消授权' : '登录失败' }}</h2>
        <p>{{ errorMessage }}</p>
        <button type="button" class="back-button" @click="goLogin">返回登录</button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useRoute, useRouter } from 'vue-router'
import { useStarryBackground } from '@/composables/useStarryBackground'
import { useAuthStore } from '@/store/authStore'

type CallbackStatus = 'loading' | 'denied' | 'error'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const status = ref<CallbackStatus>('loading')
const errorMessage = ref('')

useStarryBackground(canvasRef)

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const goLogin = () => {
  router.replace({ name: 'Login' })
}

onMounted(async () => {
  // 分支一：飞书携带 error 回调（用户拒绝授权等）
  const queryError = typeof route.query.error === 'string' ? route.query.error : ''
  if (queryError) {
    status.value = queryError === 'access_denied' ? 'denied' : 'error'
    errorMessage.value = queryError === 'access_denied'
      ? '您取消了飞书授权，可返回使用其他方式登录。'
      : '飞书授权失败，请返回重试。'
    return
  }

  const code = typeof route.query.code === 'string' ? route.query.code : ''
  const state = typeof route.query.state === 'string' ? route.query.state : ''
  if (!code || !state) {
    status.value = 'error'
    errorMessage.value = '回调参数缺失，无法完成飞书登录。'
    return
  }

  // 分支二：正常回调，交给后端换取令牌并登录
  const success = await authStore.loginWithFeishu(code, state)
  if (success) {
    Message.success('登录成功！')
    await router.replace({ name: 'Dashboard' })
    return
  }

  // 分支三：登录失败，展示后端返回的错误信息
  status.value = 'error'
  errorMessage.value = authStore.getLoginError || '飞书登录失败，请返回重试。'
})
</script>

<style scoped>
.feishu-callback-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: radial-gradient(ellipse at 20% 50%, #0a1628 0%, #020810 100%);
}

.starry-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.callback-card {
  position: relative;
  z-index: 1;
  width: min(100%, 380px);
  padding: 36px 32px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 24px;
  background: rgba(9, 20, 38, 0.72);
  backdrop-filter: blur(18px);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
  color: #e8f0ff;
  text-align: center;
  animation: fade-in-up 0.6s ease-out;
}

.spinner {
  width: 44px;
  height: 44px;
  animation: spin 1s linear infinite;
}

.callback-card h2 {
  margin: 16px 0 8px;
  font-size: 20px;
  font-weight: 700;
}

.callback-card p {
  margin: 0;
  color: rgba(180, 210, 255, 0.75);
  font-size: 14px;
  line-height: 1.6;
}

.callback-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(245, 83, 61, 0.16);
  color: #f87171;
}

.callback-icon svg {
  width: 30px;
  height: 30px;
}

.back-button {
  margin-top: 20px;
  padding: 10px 28px;
  border: none;
  border-radius: 999px;
  background: linear-gradient(135deg, #2563eb, #38bdf8);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.back-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.35);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
```

**Step 2: 修改 router/index.ts**

1. 在 `LoginView` 的 import 语句之后新增：

```typescript
import FeishuCallbackView from '@/views/FeishuCallbackView.vue'; // 导入飞书登录回调页面组件。
```

2. 在 `Register` 路由对象（第 40-44 行）之后新增路由：

```typescript
  {
    path: '/login/feishu/callback', // 飞书 OAuth 回调地址，与后端 FEISHU_REDIRECT_URI 默认值一致。
    name: 'FeishuCallback', // 定义飞书回调路由名称。
    component: FeishuCallbackView // 指定回调页组件，负责用 code 完成登录。
  },
```

3. 第 269 行白名单改为：

```typescript
  const publicRoutes = ['Login', 'Register', 'FeishuCallback']; // 声明公开路由名称白名单。
```

**Step 3: 验证**

```
npx vue-tsc -b
```

预期：无类型错误。

**Step 4: Commit**

```
git add SkillForge_Vue/src/views/FeishuCallbackView.vue SkillForge_Vue/src/router/index.ts
git commit -m "feat: 新增飞书登录回调页与路由"
```

---
