## Task 6: LoginView 新增飞书登录入口

**Files:**

- Modify: `WHartTest_Vue\src\views\LoginView.vue`（模板 / script / style 三处）

**Interfaces:**

- Consumes：`getFeishuAuthorizeUrl`（Task 4）
- Produces：点击飞书 launcher → 整页跳转飞书授权页

**Step 1: 修改模板**

将现有单个 `.login-launcher` 按钮（第 15-39 行，含 `ref="launcherButtonRef"` 的整个 `<button>`）包进行容器，并在其后新增飞书按钮：

```html
      <div class="launcher-row">
        <button
          ref="launcherButtonRef"
          type="button"
          class="login-launcher"
          aria-label="打开登录弹窗"
          @click="openLoginDialog"
        >
          <span class="launcher-aura" />
          <span class="launcher-icon" aria-hidden="true">
            <img
              v-if="!fingerprintImageLoadFailed && currentFingerprintAsset"
              :src="currentFingerprintAsset"
              alt=""
              class="launcher-fingerprint-img"
              @error="handleFingerprintAssetError"
            />
            <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.8" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V7.875a4.5 4.5 0 00-9 0V10.5m9 0h.75A2.25 2.25 0 0119.5 12.75v5.625a2.25 2.25 0 01-2.25 2.25h-10.5a2.25 2.25 0 01-2.25-2.25V12.75A2.25 2.25 0 016.75 10.5h.75" />
            </svg>
          </span>
          <span class="launcher-copy">
            <strong>账号登录</strong>
            <span>点击展开登录框</span>
          </span>
        </button>

        <button
          type="button"
          class="login-launcher feishu-launcher"
          aria-label="使用飞书登录"
          :disabled="feishuLoading"
          @click="handleFeishuLogin"
        >
          <span class="launcher-aura feishu-aura" />
          <span class="launcher-icon feishu-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10.9 10.9H2A8.9 8.9 0 0 1 10.9 2v8.9Z" fill="#3370FF" />
              <path d="M13.1 13.1H22A8.9 8.9 0 0 1 13.1 22v-8.9Z" fill="#3370FF" />
              <path d="M13.1 2A8.9 8.9 0 0 1 22 10.9h-8.9V2Z" fill="#00D6B9" />
              <path d="M10.9 22A8.9 8.9 0 0 1 2 13.1h8.9V22Z" fill="#00D6B9" />
              <circle cx="12" cy="12" r="2.4" fill="#fff" />
            </svg>
          </span>
          <span class="launcher-copy">
            <strong>飞书登录</strong>
            <span>使用飞书账号快捷登录</span>
          </span>
        </button>
      </div>
```

> 内联 SVG 为飞书品牌风格的多色风车标识（外部 CDN 获取 logo 不可用，采用自绘几何图形），尺寸继承现有 `.launcher-icon svg` 的 36px 样式，fill 写死在 path 上不受 `color` 影响。

**Step 2: 修改 script**

导入区（第 157 行 `useStarryBackground` 导入附近）新增：

```typescript
import { getFeishuAuthorizeUrl } from '@/services/authService'
```

在 `const featureTags = [...]` 之后新增响应式状态与方法（放在 `openLoginDialog` 定义之前）：

```typescript
const feishuLoading = ref(false)

const handleFeishuLogin = async () => {
  if (feishuLoading.value) {
    return
  }

  feishuLoading.value = true
  try {
    const response = await getFeishuAuthorizeUrl()
    if (response.success && response.data) {
      // 整页跳转到飞书授权页，授权完成后由回调页接管
      window.location.href = response.data.authorize_url
      return
    }
    Message.error(response.error || '无法获取飞书授权地址，请稍后重试。')
  } catch {
    Message.error('无法获取飞书授权地址，请稍后重试。')
  } finally {
    feishuLoading.value = false
  }
}
```

**Step 3: 修改样式**

在 `.login-launcher` 相关样式块之后（`.launcher-copy span` 规则之后）追加：

```css
.launcher-row {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 20px;
}

.feishu-launcher .launcher-icon {
  background: linear-gradient(135deg, rgba(0, 102, 255, 0.9), rgba(0, 214, 185, 0.9));
  box-shadow: 0 12px 28px rgba(51, 112, 255, 0.35);
}

.feishu-launcher .launcher-aura {
  background: radial-gradient(circle, rgba(0, 214, 185, 0.22), transparent 72%);
}

.feishu-launcher:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}
```

在文件末尾 640px 媒体查询内（`.launcher-icon { width: 50px; height: 50px; }` 规则之后）追加：

```css
  .launcher-row {
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }
```

**Step 4: 验证**

```
npx vue-tsc -b
```

预期：无类型错误。

**Step 5: Commit**

```
git add WHartTest_Vue/src/views/LoginView.vue
git commit -m "feat: 登录页新增飞书登录入口"
```

---
