const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const cv = require('@techstark/opencv-js');
const { PNG } = require('pngjs');

// ============ 工具函数 ============

/**
 * 简单截图保存
 */
async function takeScreenshot(page, filename) {
  await page.screenshot({ path: filename, fullPage: true });
  console.log(`截图已保存: ${filename}`);
}

/**
 * 等待 OpenCV WASM 初始化
 */
function waitForOpenCV() {
  return new Promise((resolve) => {
    if (cv.getBuildInformation) {
      resolve();
    } else {
      cv.onRuntimeInitialized = () => resolve();
    }
  });
}

/**
 * 将 Playwright 截图 Buffer (PNG) 转为 OpenCV Mat (BGR)
 */
function bufferToMat(buffer) {
  const png = PNG.sync.read(buffer);
  const { width, height, data } = png;

  // RGBA Mat
  const rgbaMat = new cv.Mat(height, width, cv.CV_8UC4);
  rgbaMat.data.set(new Uint8Array(data.buffer, data.byteOffset, data.byteLength));

  // RGBA -> BGR
  const bgrMat = new cv.Mat();
  cv.cvtColor(rgbaMat, bgrMat, cv.COLOR_RGBA2BGR);
  rgbaMat.delete();

  return bgrMat;
}

/**
 * OpenCV 边缘检测 + 模板匹配识别缺口位置
 */
function getGapOffsetOpenCV(bgBuffer, gapBuffer, searchStart = 200, searchEnd = 340) {
  let bgCv, gapCv, bgGray, gapGray, bgBlurred, gapBlurred;
  let bgEdges, gapEdges, roi, result;

  try {
    bgCv = bufferToMat(bgBuffer);
    gapCv = bufferToMat(gapBuffer);

    // 1. 灰度
    bgGray = new cv.Mat();
    gapGray = new cv.Mat();
    cv.cvtColor(bgCv, bgGray, cv.COLOR_BGR2GRAY);
    cv.cvtColor(gapCv, gapGray, cv.COLOR_BGR2GRAY);

    // 2. 高斯模糊
    bgBlurred = new cv.Mat();
    gapBlurred = new cv.Mat();
    const ksize = new cv.Size(3, 3);
    cv.GaussianBlur(bgGray, bgBlurred, ksize, 0);
    cv.GaussianBlur(gapGray, gapBlurred, ksize, 0);

    // 3. Canny 边缘
    bgEdges = new cv.Mat();
    gapEdges = new cv.Mat();
    cv.Canny(bgBlurred, bgEdges, 50, 150);
    cv.Canny(gapBlurred, gapEdges, 50, 150);

    const wGap = gapEdges.cols;
    const hBg = bgEdges.rows;
    const wBg = bgEdges.cols;

    // 4. 搜索区域限制
    let startX = searchStart;
    let endX = searchEnd;
    const maxX = wBg - wGap;
    if (startX > maxX) startX = Math.max(0, maxX - 50);
    if (endX > maxX) endX = maxX;

    const roiWidth = endX - startX + 1;
    roi = bgEdges.roi(new cv.Rect(startX, 0, roiWidth, hBg));

    // 5. 模板匹配
    result = new cv.Mat();
    cv.matchTemplate(roi, gapEdges, result, cv.TM_CCOEFF_NORMED);

    // 6. 取最佳匹配位置
    const { maxVal: matchRate, maxLoc } = cv.minMaxLoc(result);
    const offsetInRoi = maxLoc.x;
    const offsetX = startX + offsetInRoi;

    console.log(`🔍 模板匹配结果 | 位置: ${offsetX}px | 匹配度: ${(matchRate * 100).toFixed(2)}%`);

    // 7. 校验
    if (offsetX < 200 && matchRate < 0.2) {
      console.log('⚠️ 识别位置在左侧滑块区域，误匹配，刷新重试');
      return null;
    }
    if (matchRate < 0.2) {
      console.log('⚠️ 匹配度过低，可能识别失败');
      return null;
    }

    return offsetX;
  } catch (e) {
    console.log(`❌ OpenCV 识别异常: ${e}`);
    return null;
  } finally {
    [bgCv, gapCv, bgGray, gapGray, bgBlurred, gapBlurred, bgEdges, gapEdges, roi, result]
      .forEach((m) => { if (m && typeof m.delete === 'function') m.delete(); });
  }
}

/**
 * 从页面获取缺口绝对像素位置
 */
async function getGapOffset(page, bgSelector = '.verify-img-panel', gapSelector = '.verify-sub-block') {
  try {
    const bgElement = page.locator(bgSelector).first();
    const gapElement = page.locator(gapSelector).first();

    await bgElement.waitFor({ state: 'visible', timeout: 5000 });
    await gapElement.waitFor({ state: 'visible', timeout: 5000 });

    const bgScreenshot = await bgElement.screenshot();  // Buffer
    const gapScreenshot = await gapElement.screenshot(); // Buffer

    return getGapOffsetOpenCV(bgScreenshot, gapScreenshot, 200, 340);
  } catch (e) {
    console.log(`❌ 获取缺口位置失败: ${e}`);
    return null;
  }
}

/**
 * 模拟人类拖动滑块
 */
async function humanLikeSlider(page, maxRetries = 20) {
  const VERIFY_BOX_SELECTOR = '.verifybox';
  const SLIDER_BLOCK_SELECTOR = '.verify-move-block';
  const REFRESH_BTN_SELECTOR = '.verify-refresh';

  const randInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
  const randFloat = (min, max) => Math.random() * (max - min) + min;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      console.log(`\n🔄 滑块验证尝试 ${attempt + 1}/${maxRetries}`);

      await page.waitForSelector(VERIFY_BOX_SELECTOR, { state: 'visible', timeout: 5000 });
      const slider = page.locator(SLIDER_BLOCK_SELECTOR).first();
      await slider.waitFor({ state: 'visible', timeout: 5000 });

      // 1. 获取缺口位置
      const gapAbsX = await getGapOffset(page);
      if (gapAbsX === null) {
        console.log('ℹ️ 识别失败，刷新验证码');
        await page.locator(REFRESH_BTN_SELECTOR).click();
        await page.waitForTimeout(500);
        continue;
      }

      // 2. 获取滑块和背景图容器的屏幕坐标
      const sliderBox = await slider.boundingBox();
      if (!sliderBox) {
        console.log('❌ 无法获取滑块位置，刷新重试');
        await page.locator(REFRESH_BTN_SELECTOR).click();
        await page.waitForTimeout(500);
        continue;
      }

      const bgContainer = page.locator('.verify-img-panel').first();
      const bgBox = await bgContainer.boundingBox();
      if (!bgBox) {
        console.log('❌ 无法获取背景图容器位置，刷新重试');
        await page.locator(REFRESH_BTN_SELECTOR).click();
        await page.waitForTimeout(500);
        continue;
      }

      // 3. 计算移动距离
      const startX = sliderBox.x + sliderBox.width / 2;
      const startY = sliderBox.y + sliderBox.height / 2;
      const targetScreenX = bgBox.x + gapAbsX + sliderBox.width / 2;
      const distance = targetScreenX - startX;

      console.log(`📏 移动距离: ${distance.toFixed(1)}px (缺口绝对坐标: ${gapAbsX}px)`);

      // 4. 人类式移动到起点
      await page.mouse.move(
        startX + randInt(-10, 10),
        startY + randInt(-3, 3),
        { steps: randInt(6, 10) }
      );
      await page.waitForTimeout(randInt(50, 100));
      await page.mouse.move(startX, startY, { steps: randInt(3, 5) });
      await page.waitForTimeout(randInt(30, 60));

      // 5. 按下鼠标
      await page.mouse.down();
      await page.waitForTimeout(randInt(40, 80));

      // 6. 自然轨迹：easeOutCubic 缓动 + 随机扰动
      const totalSteps = randInt(20, 30);
      for (let i = 0; i < totalSteps; i++) {
        const progress = i / totalSteps;
        const easeProgress = 1 - Math.pow(1 - progress, 3);

        let nextX = startX + distance * easeProgress;
        nextX += randFloat(-1.5, 1.5) * (1 - easeProgress);
        const nextY = startY + randFloat(-2, 2);

        await page.mouse.move(nextX, nextY, { steps: 1 });

        if (Math.random() < 0.1) {
          await page.waitForTimeout(randInt(2, 6));
        }
      }

      // 7. 终点微调：±2px 随机偏移 + 轻微过冲回弹
      const finalTargetX = targetScreenX + randFloat(-2, 2);
      const overshoot = randInt(1, 3);
      await page.mouse.move(finalTargetX + overshoot, startY, { steps: randInt(1, 2) });
      await page.waitForTimeout(randInt(10, 25));
      await page.mouse.move(finalTargetX, startY, { steps: 1 });
      await page.waitForTimeout(randInt(20, 50));

      // 8. 松开鼠标
      await page.mouse.up();
      await page.waitForTimeout(randInt(60, 100));

      // 9. 验证结果
      try {
        await page.waitForSelector(VERIFY_BOX_SELECTOR, { state: 'hidden', timeout: 2500 });
        console.log('🎉 滑块验证成功！');
        return true;
      } catch {
        console.log('❌ 验证失败，刷新重试');
        await page.locator(REFRESH_BTN_SELECTOR).click();
        await page.waitForTimeout(500);
        continue;
      }
    } catch (e) {
      console.log(`⚠️ 滑块验证异常: ${e}`);
      try {
        await page.locator(REFRESH_BTN_SELECTOR).click();
        await page.waitForTimeout(500);
      } catch {}
      continue;
    }
  }

  console.log('❌ 滑块验证尝试全部失败');
  return false;
}

// ============ 主流程 ============

async function run() {
  await waitForOpenCV();
  console.log('✅ OpenCV WASM 已就绪');

  const browser = await chromium.launch({
    headless: false,
    args: ['--lang=zh-CN'],
  });

  const videoDir = process.env.PLAYWRIGHT_VIDEO_DIR || '';
  const contextOptions = {
    ignoreHTTPSErrors: true,
    locale: 'zh-CN',
  };

  // 录制视频（Node 版写法）
  if (videoDir) {
    contextOptions.recordVideo = {
      dir: videoDir,
      size: { width: 1280, height: 720 },
    };
  }

  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();

  // 设置默认超时（对应 Python 的 page.set_default_timeout(100 * 1000)）
  page.setDefaultTimeout(100 * 1000);

  try {
    // 步骤1: 打开登录页面
    await page.goto('https://demo-station-admin.jtexpress.my');
    await takeScreenshot(page, 'step1_open_login_page.png');

    // 步骤2: 输入用户名
    await page.getByRole('textbox', { name: '请输入账号' }).fill('JT820024');
    await takeScreenshot(page, 'step2_input_username.png');

    // 步骤3: 输入密码
    await page.getByRole('textbox', { name: '请输入密码' }).fill('Aa123456');
    await takeScreenshot(page, 'step3_input_password.png');

    // 步骤4: 点击登录按钮
    await page.getByRole('button', { name: '登录' }).click();
    await takeScreenshot(page, 'step4_click_login.png');

    // 步骤5: 处理滑块验证
    const sliderResult = await humanLikeSlider(page, 20);
    if (!sliderResult) {
      console.log('滑块验证失败，脚本终止');
      await takeScreenshot(page, 'step5_slider_failed.png');
      return;
    }
    await takeScreenshot(page, 'step5_slider_success.png');

    // 步骤6: 验证登录成功
    await page.waitForLoadState('networkidle', { timeout: 10000 });
    await page.waitForTimeout(800);
    const visible = await page.getByText('欢迎使用 YoYi! Station').isVisible();
    if (!visible) {
      throw new Error('登录成功标识未出现: "欢迎使用 YoYi! Station" 不可见');
    }
    await takeScreenshot(page, 'step6_login_success.png');

    console.log('测试执行成功');
  } catch (e) {
    console.log('测试执行失败: %s', e);
    await takeScreenshot(page, 'error_screenshot.png');
    throw e;
  } finally {
    await context.close();
    await browser.close();
  }
}

// 入口
run().catch((e) => {
  console.error('顶层异常:', e);
  process.exit(1);
});
