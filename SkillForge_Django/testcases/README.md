# UI 自动化公共模块使用指南

本目录包含可复用的 UI 自动化公共模块，用于简化 Playwright 自动化测试的开发。

---

## 📁 模块说明

### 1. slider_captcha.py - 滑块验证码处理模块

提供滑块验证码的识别和自动处理功能。

#### 主要函数

##### `get_gap_offset_opencv(bg_img_pil, gap_img_pil, search_start=200, search_end=340)`
使用 OpenCV 边缘检测 + 模板匹配识别缺口位置

**参数：**
- `bg_img_pil`: PIL Image 对象，背景图
- `gap_img_pil`: PIL Image 对象，缺口图（滑块）
- `search_start`: 搜索起始 X 坐标（避开左侧滑块），默认 200
- `search_end`: 搜索结束 X 坐标，默认 340

**返回值：**
- `int`: 缺口在背景图中的 X 坐标位置，识别失败返回 None

**示例：**
```python
from slider_captcha import get_gap_offset_opencv
from PIL import Image

bg_img = Image.open("background.png")
gap_img = Image.open("gap.png")

offset = get_gap_offset_opencv(bg_img, gap_img)
if offset:
    print(f"缺口位置: {offset}px")
```

##### `get_gap_offset(page, bg_selector=".verify-img-panel", gap_selector=".verify-sub-block")`
获取缺口在背景图中的绝对像素位置

**参数：**
- `page`: Playwright Page 对象
- `bg_selector`: 背景图元素的 CSS 选择器，默认 ".verify-img-panel"
- `gap_selector`: 缺口图元素的 CSS 选择器，默认 ".verify-sub-block"

**返回值：**
- `int`: 缺口的 X 坐标位置，失败返回 None

**示例：**
```python
from slider_captcha import get_gap_offset

offset = get_gap_offset(page)
if offset:
    print(f"缺口位置: {offset}px")
```

##### `human_like_slider(page, verify_box_selector=".verifybox", ...)`
模拟人类拖动滑块完成验证

**参数：**
- `page`: Playwright Page 对象
- `verify_box_selector`: 验证框容器的 CSS 选择器
- `slider_block_selector`: 滑块元素的 CSS 选择器
- `refresh_btn_selector`: 刷新按钮的 CSS 选择器
- `bg_selector`: 背景图元素的 CSS 选择器
- `gap_selector`: 缺口图元素的 CSS 选择器
- `max_retries`: 最大重试次数，默认 20

**返回值：**
- `bool`: 验证成功返回 True，失败返回 False

**示例：**
```python
from slider_captcha import human_like_slider

success = human_like_slider(
    page,
    verify_box_selector=".verifybox",
    slider_block_selector=".verify-move-block",
    refresh_btn_selector=".verify-refresh",
    bg_selector=".verify-img-panel",
    gap_selector=".verify-sub-block",
    max_retries=20
)

if success:
    print("验证成功！")
```

##### `handle_slider_captcha(page, ...)`
检测并处理滑块验证码（自动检测是否需要验证）

**参数：**
- `page`: Playwright Page 对象
- `verify_box_selector`: 验证框容器的 CSS 选择器
- `slider_block_selector`: 滑块元素的 CSS 选择器
- `refresh_btn_selector`: 刷新按钮的 CSS 选择器
- `bg_selector`: 背景图元素的 CSS 选择器
- `gap_selector`: 缺口图元素的 CSS 选择器
- `max_retries`: 最大重试次数，默认 20

**返回值：**
- `bool`: 验证成功或无需验证返回 True，验证失败返回 False

**示例：**
```python
from slider_captcha import handle_slider_captcha

success = handle_slider_captcha(page)
if success:
    print("验证通过或无需验证")
```

---

### 2. page_utils.py - 页面操作工具模块

提供常用的页面操作方法。

#### 主要函数

##### `safe_text(text)`
清理文本，去除空白和换行

**参数：**
- `text`: 原始文本

**返回值：**
- `str`: 清理后的文本，如果输入为 None 返回空字符串

**示例：**
```python
from page_utils import safe_text

text = safe_text("  Hello World  \n")
# 返回: "Hello World"
```

##### `collect_page_texts(page)`
收集当前页面中所有可见元素的中文文本

**参数：**
- `page`: Playwright Page 对象

**返回值：**
- `set`: 包含所有可见中文文本的集合

**示例：**
```python
from page_utils import collect_page_texts

texts = collect_page_texts(page)
for text in texts:
    print(text)
```

##### `collect_menu_texts(page, menu_xpath_base="...")`
遍历所有菜单（包括子菜单），点击每个菜单项，收集当前页面中的中文文本

**参数：**
- `page`: Playwright Page 对象
- `menu_xpath_base`: 菜单项的 XPath 基础模板

**返回值：**
- `list`: 所有收集到的文本列表

**示例：**
```python
from page_utils import collect_menu_texts

menus = collect_menu_texts(page)
print(f"收集到 {len(menus)} 个菜单项")
```

##### `switch_language(page, target_lang="EN", lang_btn_xpath="...")`
切换到指定语言

**参数：**
- `page`: Playwright Page 对象
- `target_lang`: 目标语言，"EN" 或 "CN"，默认 "EN"
- `lang_btn_xpath`: 语言切换按钮的 XPath

**示例：**
```python
from page_utils import switch_language

switch_language(page, target_lang="EN")
```

##### `find_untranslated_elements(page, chinese_texts)`
遍历页面所有元素，找出文本内容与 chinese_texts 中任一完全相同的元素

**参数：**
- `page`: Playwright Page 对象
- `chinese_texts`: 中文文本列表或集合

**返回值：**
- `list`: 匹配的元素列表，每个元素为 (element, matched_text) 元组

**示例：**
```python
from page_utils import find_untranslated_elements

chinese_texts = ["用户管理", "系统设置"]
untranslated = find_untranslated_elements(page, chinese_texts)

for element, text in untranslated:
    print(f"未翻译: {text}")
```

##### `highlight_and_screenshot(page, element, text, index, save_dir="C:\\doc")`
高亮元素（红色边框）并截图整个窗口

**参数：**
- `page`: Playwright Page 对象
- `element`: 要高亮的 Playwright Locator 对象
- `text`: 元素的文本内容（用于生成文件名）
- `index`: 序号（用于生成文件名）
- `save_dir`: 截图保存目录，默认 "C:\\doc"

**示例：**
```python
from page_utils import highlight_and_screenshot

element = page.locator(".some-element")
highlight_and_screenshot(page, element, "用户管理", 1)
```

##### `wait_for_element_visible(page, selector, timeout=10000)`
等待元素可见

**参数：**
- `page`: Playwright Page 对象
- `selector`: 元素选择器
- `timeout`: 超时时间（毫秒），默认 10000

**返回值：**
- `bool`: 元素可见返回 True，超时返回 False

**示例：**
```python
from page_utils import wait_for_element_visible

if wait_for_element_visible(page, ".submit-button"):
    print("按钮已可见")
```

##### `wait_for_page_load(page, timeout=10000)`
等待页面加载完成

**参数：**
- `page`: Playwright Page 对象
- `timeout`: 超时时间（毫秒），默认 10000

**返回值：**
- `bool`: 页面加载完成返回 True，超时返回 False

**示例：**
```python
from page_utils import wait_for_page_load

if wait_for_page_load(page):
    print("页面加载完成")
```

##### `take_screenshot(page, filename, full_page=False)`
截取页面截图

**参数：**
- `page`: Playwright Page 对象
- `filename`: 截图文件名
- `full_page`: 是否截全页，默认 False（仅截视口）

**返回值：**
- `bool`: 截图成功返回 True，失败返回 False

**示例：**
```python
from page_utils import take_screenshot

take_screenshot(page, "screenshot.png")
take_screenshot(page, "full_page.png", full_page=True)
```

##### `click_element(page, selector, timeout=10000)`
点击元素

**参数：**
- `page`: Playwright Page 对象
- `selector`: 元素选择器
- `timeout`: 等待超时时间（毫秒），默认 10000

**返回值：**
- `bool`: 点击成功返回 True，失败返回 False

**示例：**
```python
from page_utils import click_element

if click_element(page, ".submit-button"):
    print("点击成功")
```

##### `fill_input(page, selector, value, timeout=10000)`
填充输入框

**参数：**
- `page`: Playwright Page 对象
- `selector`: 元素选择器
- `value`: 要填充的值
- `timeout`: 等待超时时间（毫秒），默认 10000

**返回值：**
- `bool`: 填充成功返回 True，失败返回 False

**示例：**
```python
from page_utils import fill_input

fill_input(page, ".username-input", "testuser")
fill_input(page, ".password-input", "password123")
```

##### `get_element_text(page, selector, timeout=10000)`
获取元素文本

**参数：**
- `page`: Playwright Page 对象
- `selector`: 元素选择器
- `timeout`: 等待超时时间（毫秒），默认 10000

**返回值：**
- `str`: 元素文本，失败返回空字符串

**示例：**
```python
from page_utils import get_element_text

text = get_element_text(page, ".welcome-message")
print(f"欢迎信息: {text}")
```

##### `check_element_exists(page, selector, timeout=5000)`
检查元素是否存在

**参数：**
- `page`: Playwright Page 对象
- `selector`: 元素选择器
- `timeout`: 等待超时时间（毫秒），默认 5000

**返回值：**
- `bool`: 元素存在返回 True，否则返回 False

**示例：**
```python
from page_utils import check_element_exists

if check_element_exists(page, ".error-message"):
    print("存在错误消息")
```

---

## 🚀 完整示例

### 示例 1：简单的登录测试

```python
from playwright.sync_api import sync_playwright
from slider_captcha import handle_slider_captcha
from page_utils import fill_input, click_element, take_screenshot

def login_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            page.goto("https://example.com/login")
            
            fill_input(page, "#username", "testuser")
            fill_input(page, "#password", "password123")
            take_screenshot(page, "before_login.png")
            
            click_element(page, "#login-button")
            
            handle_slider_captcha(page)
            
            take_screenshot(page, "after_login.png")
            print("登录成功！")
            
        finally:
            browser.close()

if __name__ == "__main__":
    login_test()
```

### 示例 2：国际化检查

```python
from playwright.sync_api import sync_playwright
from page_utils import (
    collect_menu_texts,
    switch_language,
    find_untranslated_elements,
    highlight_and_screenshot
)

def check_i18n():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            page.goto("https://example.com")
            
            chinese_menus = collect_menu_texts(page)
            print(f"收集到 {len(chinese_menus)} 个中文菜单")
            
            switch_language(page, target_lang="EN")
            
            untranslated = find_untranslated_elements(page, chinese_menus)
            
            for idx, (el, text) in enumerate(untranslated, start=1):
                highlight_and_screenshot(page, el, text, idx)
            
            print(f"发现 {len(untranslated)} 个未翻译的文本")
            
        finally:
            browser.close()

if __name__ == "__main__":
    check_i18n()
```

### 示例 3：自定义滑块验证

```python
from playwright.sync_api import sync_playwright
from slider_captcha import human_like_slider

def custom_captcha_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            page.goto("https://example.com")
            
            success = human_like_slider(
                page,
                verify_box_selector=".custom-captcha-box",
                slider_block_selector=".custom-slider",
                refresh_btn_selector=".custom-refresh",
                bg_selector=".custom-bg",
                gap_selector=".custom-gap",
                max_retries=10
            )
            
            if success:
                print("验证成功！")
            else:
                print("验证失败")
                
        finally:
            browser.close()

if __name__ == "__main__":
    custom_captcha_test()
```

---

## 📋 重构对比

### 原始代码 (jt_login.py)
- 所有功能都在一个文件中
- 约 480 行代码
- 难以复用和维护

### 重构后代码
- **slider_captcha.py**: 滑块验证功能（约 200 行）
- **page_utils.py**: 页面操作工具（约 200 行）
- **jt_login_refactored.py**: 主流程（约 80 行）
- 模块化，易于复用和维护

---

## 💡 最佳实践

1. **模块化设计**
   - 将通用功能提取到公共模块
   - 保持单一职责原则
   - 便于测试和维护

2. **错误处理**
   - 所有公共函数都包含异常处理
   - 返回布尔值表示成功/失败
   - 记录详细的错误信息

3. **参数默认值**
   - 为常用参数提供合理的默认值
   - 减少调用时的参数传递
   - 提高代码可读性

4. **文档注释**
   - 每个函数都有详细的文档字符串
   - 说明参数、返回值和用法
   - 包含示例代码

5. **日志输出**
   - 使用 emoji 标识不同类型的日志
   - 提供清晰的执行步骤信息
   - 便于调试和问题排查

---

## 🔧 依赖安装

```bash
pip install playwright
pip install opencv-python
pip install pillow
pip install numpy

playwright install chromium
```

---

## 📞 联系支持

如有问题或建议，请联系开发团队。
