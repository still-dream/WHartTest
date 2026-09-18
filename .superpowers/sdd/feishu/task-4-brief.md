## Task 4: 前端 authService 飞书 API

**Files:**

- Modify: `WHartTest_Vue\src\services\authService.ts`（末尾追加两个函数 + 接口定义）

**Interfaces:**

- Consumes：`request<T>`（`@/utils/request`，已导入）、`axios`（已导入）
- Produces（供 Task 5/6/7 消费）：
  - `export const getFeishuAuthorizeUrl = async (): Promise<FeishuAuthorizeUrlResponse>`
  - `export const feishuLogin = async (code: string, state: string): Promise<AuthServiceLoginResponse>`（成功 data 为既有 `ApiTokenResponseData`，与账号登录同构）

**Step 1: 实现（前端无单测设施，直接实现后以 vue-tsc 验证）**

在 `authService.ts` 末尾追加：

```typescript
// 飞书授权地址接口响应的数据结构
export interface FeishuAuthorizeUrlResponseData {
  authorize_url: string;
  state: string;
}

// 飞书授权地址函数返回的结构
export interface FeishuAuthorizeUrlResponse {
  success: boolean;
  data?: FeishuAuthorizeUrlResponseData;
  error?: string;
  statusCode?: number;
}

/**
 * 获取飞书 OAuth 授权页地址
 * @returns 返回一个 Promise，解析为包含授权地址与 state 的对象
 */
export const getFeishuAuthorizeUrl = async (): Promise<FeishuAuthorizeUrlResponse> => {
  const API_URL = '/accounts/feishu/authorize-url/';

  try {
    const response = await request<FeishuAuthorizeUrlResponseData>({
      url: API_URL,
      method: 'GET',
      headers: {
        'accept': 'application/json',
      }
    });

    if (response.success && response.data) {
      return { success: true, data: response.data, statusCode: 200 };
    }

    return {
      success: false,
      error: response.error || '获取飞书授权地址失败：响应数据格式不正确。',
      statusCode: (response as any).status ?? 500,
    };
  } catch (error) {
    let errorMessage = '获取飞书授权地址失败，请稍后再试。';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;
        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        }
      } else if (error.request) {
        errorMessage = '认证服务暂未就绪，请稍后重试。';
      }
    }
    return { success: false, error: errorMessage, statusCode };
  }
};

/**
 * 使用飞书授权码登录（返回结构与账号登录一致）
 * @param code 飞书回调携带的授权码
 * @param state 飞书回调携带的防 CSRF 状态
 * @returns 返回一个 Promise，解析为包含认证结果的对象
 */
export const feishuLogin = async (code: string, state: string): Promise<AuthServiceLoginResponse> => {
  const API_URL = '/accounts/feishu/login/';
  const CSRF_TOKEN = 'kMNlyN2uN6c2QRr9r2rDQbfxBGsVzjPFY1h1as93VNMRTjo5kRpDbVq5ii8FFcKW';

  try {
    const response = await request<ApiTokenResponseData>({
      url: API_URL,
      method: 'POST',
      data: { code, state },
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFTOKEN': CSRF_TOKEN,
        'accept': 'application/json',
      }
    });

    if (response.success && response.data) {
      return { success: true, data: response.data, statusCode: 200 };
    }

    const responseStatus = (response as any).status as number | undefined;
    let errorMessage = response.error || '飞书登录失败：响应数据格式不正确。';
    if (responseStatus === 503) {
      errorMessage = response.error || '认证服务正在启动，请稍后重试。';
    } else if (errorMessage.includes('服务器无响应') || errorMessage.includes('Network Error')) {
      errorMessage = '认证服务暂未就绪，请稍后重试。';
    }
    return { success: false, error: errorMessage, statusCode: responseStatus ?? 500 };
  } catch (error) {
    let errorMessage = '飞书登录暂时不可用，请稍后再试。';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;
        if (statusCode === 503) {
          errorMessage = '认证服务正在启动，请稍后重试。';
        } else if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else {
          errorMessage = `飞书登录失败：服务器错误 (${statusCode})。`;
        }
      } else if (error.request) {
        errorMessage = '认证服务暂未就绪，请稍后重试。';
      }
    }
    return { success: false, error: errorMessage, statusCode };
  }
};
```

**Step 2: 验证**

```
npx vue-tsc -b
```

cwd：`WHartTest_Vue`。预期：无类型错误（exit 0）。本函数暂无调用方，type-check 通过即可。

**Step 3: Commit**

```
git add WHartTest_Vue/src/services/authService.ts
git commit -m "feat: authService 新增飞书授权地址与飞书登录接口"
```

---
