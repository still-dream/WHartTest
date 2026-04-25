"""
J&T 系统登录和国际化检查脚本（重构版）

使用公共模块实现滑块验证和页面操作功能。
"""

from playwright.sync_api import sync_playwright, expect
from slider_captcha import handle_slider_captcha
from page_utils import (
    collect_menu_texts,
    switch_language,
    find_untranslated_elements,
    highlight_and_screenshot,
    take_screenshot
)


def main():
    """
    主流程：登录系统、处理滑块验证、检查国际化
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized", "--window-position=0,0"]
        )
        context = browser.new_context(viewport=None)
        page = context.new_page()
        print("✅ 浏览器已最大化")

        step = 0
        try:
            step += 1
            page.goto("https://demo-home-admin.jtexpress.ph/login", wait_until="networkidle")
            expect(page).to_have_title("J&T Home")
            print(f"✅ 步骤{step}: 打开登录页面成功")
            take_screenshot(page, f"step{step}_open_login_page.png")

            step += 1
            account_input = page.get_by_role("textbox", name="请输入账号")
            account_input.wait_for(state="visible", timeout=10000)
            account_input.fill("JT940060")

            password_input = page.get_by_role("textbox", name="请输入密码")
            password_input.wait_for(state="visible", timeout=10000)
            password_input.fill("Jitu1633")
            print(f"✅ 步骤{step}: 输入用户名和密码成功")
            take_screenshot(page, f"step{step}_input_credentials.png")

            step += 1
            login_button = page.get_by_role("button", name="登录")
            login_button.wait_for(state="visible", timeout=5000)
            login_button.click()
            print(f"✅ 步骤{step}: 点击登录按钮成功")
            take_screenshot(page, f"step{step}_click_login.png")

            step += 1
            print(f"🔄 步骤{step}: 检测安全验证")
            
            slider_success = handle_slider_captcha(
                page,
                verify_box_selector=".verifybox",
                slider_block_selector=".verify-move-block",
                refresh_btn_selector=".verify-refresh",
                bg_selector=".verify-img-panel",
                gap_selector=".verify-sub-block",
                max_retries=20
            )
            
            if not slider_success:
                print("❌ 滑块验证失败，脚本终止")
                return
            
            take_screenshot(page, f"step{step}_slider_verification.png")

            step += 1
            print(f"🔄 步骤{step}: 验证登录结果")
            page.wait_for_load_state("networkidle", timeout=10000)
            page.wait_for_timeout(800)
            take_screenshot(page, f"step{step}_login_final_result.png")

            if "login" not in page.url:
                print("🎉 登录成功！")
            else:
                print("⚠️ 仍在登录页，请检查截图")

            print("\n📋 正现在收集中文菜单文本...")
            chinese_menus = collect_menu_texts(page)
            print(f"✅ 共收集到 {len(chinese_menus)} 个中文菜单项")

            print("\n🌐 正在切换语言到 English...")
            switch_language(page, target_lang="EN")
            print("✅ 语言切换完成")

            print("\n🔍 开始查找未翻译的文本...")
            untranslated = find_untranslated_elements(page, chinese_menus)

            if not untranslated:
                print("🎉 没有发现任何未翻译的文本！")
            else:
                print(f"⚠️ 发现 {len(untranslated)} 个未翻译的文本，正在截图...")
                for idx, (el, txt) in enumerate(untranslated, start=1):
                    highlight_and_screenshot(page, el, txt, idx)

            print("\n✅ 所有任务完成！")

        except Exception as e:
            print(f"❌ 脚本异常: {e}")
            take_screenshot(page, f"step{step}_error.png")

        finally:
            print("ℹ️ 浏览器将在3秒后关闭...")
            page.wait_for_timeout(3000)
            browser.close()


if __name__ == "__main__":
    main()
