#!/usr/bin/env node
'use strict';

/**
 * Playwright 持久化会话服务
 *
 * 协议：stdin/stdout 行分隔 JSON
 * 请求：
 *   { id, method: "ping", params: {} }
 *   { id, method: "exec", params: { args: string[], env?: object } }
 *   { id, method: "close", params: {} }
 *
 * 响应：
 *   { id, ok: boolean, stdout?: string[], stderr?: string[], error?: string, state?: object }
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const Module = require('module');
const { execSync } = require('child_process');

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + '\n');
}

function serverLog(...args) {
  try {
    process.stderr.write(args.map(String).join(' ') + '\n');
  } catch (_) {}
}

function parseCli(argv) {
  const out = { skillDir: '' };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--skill-dir') {
      out.skillDir = argv[i + 1] || '';
      i++;
    }
  }
  return out;
}

function checkPlaywrightInstalled(requireFromSkill) {
  try {
    requireFromSkill.resolve('playwright');
    return true;
  } catch (_) {
    return false;
  }
}

function installPlaywright(skillDir) {
  const allow = (process.env.PLAYWRIGHT_AUTO_INSTALL || 'true').toLowerCase() !== 'false';
  if (!allow) return false;

  serverLog('[playwright_persistent_server] Playwright not found. Installing...');
  try {
    execSync('npm install', { stdio: 'inherit', cwd: skillDir });
    execSync('npx playwright install chromium', { stdio: 'inherit', cwd: skillDir });
    serverLog('[playwright_persistent_server] Playwright installed successfully');
    return true;
  } catch (e) {
    serverLog('[playwright_persistent_server] Failed to install Playwright:', e?.message || String(e));
    return false;
  }
}

function createCapturedConsole() {
  const stdout = [];
  const stderr = [];

  const fmt = (args) =>
    args
      .map((a) => {
        if (typeof a === 'string') return a;
        try {
          return JSON.stringify(a);
        } catch (_) {
          return String(a);
        }
      })
      .join(' ');

  return {
    stdout,
    stderr,
    console: {
      log: (...args) => stdout.push(fmt(args)),
      info: (...args) => stdout.push(fmt(args)),
      warn: (...args) => stderr.push(fmt(args)),
      error: (...args) => stderr.push(fmt(args)),
      debug: (...args) => stdout.push(fmt(args)),
    },
  };
}

async function safeClose(target) {
  if (!target) return;
  try {
    await target.close();
  } catch (_) {}
}

async function main() {
  const cli = parseCli(process.argv.slice(2));
  if (!cli.skillDir) {
    serverLog('Usage: node playwright_persistent_server.js --skill-dir <path>');
    process.exit(2);
  }

  const skillDir = path.resolve(cli.skillDir);
  process.chdir(skillDir);

  const requireAnchor = fs.existsSync(path.join(skillDir, 'package.json'))
    ? path.join(skillDir, 'package.json')
    : path.join(skillDir, 'run.js');
  const requireFromSkill = Module.createRequire(requireAnchor);

  if (!checkPlaywrightInstalled(requireFromSkill)) {
    const installed = installPlaywright(skillDir);
    if (!installed) {
      serverLog('[playwright_persistent_server] Playwright unavailable.');
    }
  }

  let playwright = null;
  let chromium = null;
  let firefox = null;
  let webkit = null;
  let devices = null;
  let helpers = null;

  const state = {
    browser: null,
    context: null,
    page: null,
  };
  
  // 页面状态快照，用于会话恢复
  let savedPageState = {
    url: null,
    cookies: [],
    localStorage: {},
    sessionStorage: {},
    timestamp: 0,
  };

  async function loadDeps() {
    if (playwright && helpers) return;
    playwright = requireFromSkill('playwright');
    chromium = playwright.chromium;
    firefox = playwright.firefox;
    webkit = playwright.webkit;
    devices = playwright.devices;
    try {
      helpers = requireFromSkill('./lib/helpers');
    } catch (_) {
      helpers = {
        launchBrowser: async (type) => {
          const browsers = { chromium, firefox, webkit };
          return browsers[type || 'chromium'].launch({ headless: false });
        },
        getExtraHeadersFromEnv: () => null,
      };
    }
  }

  function getContextOptionsWithHeaders(options = {}) {
    const localeOptions = { locale: 'zh-CN' };
    if (!helpers?.getExtraHeadersFromEnv) return { ...localeOptions, ...options };
    const extra = helpers.getExtraHeadersFromEnv();
    if (!extra) return { ...localeOptions, ...options };
    return {
      ...localeOptions,
      ...options,
      extraHTTPHeaders: {
        ...(extra || {}),
        ...(options?.extraHTTPHeaders || {}),
      },
    };
  }

  async function savePageState() {
    try {
      if (!state.page || typeof state.page.isClosed === 'function' && state.page.isClosed()) {
        return;
      }
      
      const url = await state.page.url();
      const cookies = state.context ? await state.context.cookies() : [];
      
      const localStorage = await state.page.evaluate(() => {
        const data = {};
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          data[key] = localStorage.getItem(key);
        }
        return data;
      }).catch(() => ({}));
      
      const sessionStorage = await state.page.evaluate(() => {
        const data = {};
        for (let i = 0; i < sessionStorage.length; i++) {
          const key = sessionStorage.key(i);
          data[key] = sessionStorage.getItem(key);
        }
        return data;
      }).catch(() => ({}));
      
      savedPageState = {
        url,
        cookies,
        localStorage,
        sessionStorage,
        timestamp: Date.now(),
      };
      
      serverLog('[savePageState] 页面状态已保存:', url);
    } catch (e) {
      serverLog('[savePageState] 保存失败:', e.message);
    }
  }

  async function restorePageState() {
    if (!savedPageState.url || !state.page) {
      serverLog('[restorePageState] 跳过恢复：无保存的 URL 或页面不存在');
      return false;
    }

    if (state.page.isClosed && state.page.isClosed()) {
      serverLog('[restorePageState] 跳过恢复：页面已关闭');
      return false;
    }

    try {
      serverLog('[restorePageState] 尝试恢复页面状态:', savedPageState.url);

      // 设置 cookies
      if (state.context && savedPageState.cookies && savedPageState.cookies.length > 0) {
        try {
          await state.context.addCookies(savedPageState.cookies);
        } catch (cookieErr) {
          serverLog('[restorePageState] 设置 cookies 失败:', cookieErr.message);
        }
      }

      // 导航到保存的 URL（带超时）
      await state.page.goto(savedPageState.url, { timeout: 30000, waitUntil: 'domcontentloaded' });

      // 恢复 localStorage
      if (savedPageState.localStorage && Object.keys(savedPageState.localStorage).length > 0) {
        try {
          await state.page.evaluate((data) => {
            for (const [key, value] of Object.entries(data)) {
              localStorage.setItem(key, value);
            }
          }, savedPageState.localStorage);
        } catch (lsErr) {
          serverLog('[restorePageState] 恢复 localStorage 失败:', lsErr.message);
        }
      }

      // 恢复 sessionStorage
      if (savedPageState.sessionStorage && Object.keys(savedPageState.sessionStorage).length > 0) {
        try {
          await state.page.evaluate((data) => {
            for (const [key, value] of Object.entries(data)) {
              sessionStorage.setItem(key, value);
            }
          }, savedPageState.sessionStorage);
        } catch (ssErr) {
          serverLog('[restorePageState] 恢复 sessionStorage 失败:', ssErr.message);
        }
      }

      serverLog('[restorePageState] 页面状态恢复成功');
      return true;
    } catch (e) {
      serverLog('[restorePageState] 恢复失败:', e.message);
      // 清除保存的状态，避免误导
      savedPageState = { url: null, cookies: [], localStorage: {}, sessionStorage: {}, timestamp: 0 };
      return false;
    }
  }

  async function ensureBrowserContextPage() {
    await loadDeps();
    
    const wasConnected = state.browser && typeof state.browser.isConnected === 'function' && state.browser.isConnected();

    if (!state.browser || !state.browser.isConnected()) {
      const browserType = (process.env.PW_BROWSER_TYPE || 'chromium').toLowerCase();
      state.browser = await helpers.launchBrowser(browserType);
      state.context = null;
      state.page = null;
    }

    if (!state.context) {
      state.context = await state.browser.newContext(getContextOptionsWithHeaders({}));
    }

    const pageWasClosed = !state.page || (typeof state.page.isClosed === 'function' && state.page.isClosed());

    if (pageWasClosed) {
      state.page = await state.context.newPage();

      // 如果之前有保存的页面状态，尝试恢复（无论是浏览器断开还是页面关闭）
      if (savedPageState.url) {
        await restorePageState();
      }
    }
  }

  function resolveCodeFromArgs(args) {
    const a = Array.isArray(args) ? args : [];
    if (a.length > 0) {
      const first = a[0];
      if (typeof first === 'string' && fs.existsSync(first)) {
        const filePath = path.resolve(first);
        return fs.readFileSync(filePath, 'utf8');
      }
      return a.join(' ');
    }
    return '';
  }

  async function runUserCode(code) {
    const captured = createCapturedConsole();
    const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

    const safeProcess = Object.assign({}, process, {
      exit: (code) => {
        throw new Error(`process.exit(${code}) blocked in persistent session`);
      },
    });

    // 调试：记录实际执行的代码
    serverLog('[runUserCode] Code length:', code.length);
    serverLog('[runUserCode] Code preview:', code.slice(0, 200));

    const fn = new AsyncFunction(
      'console',
      'state',
      'helpers',
      'chromium',
      'firefox',
      'webkit',
      'devices',
      'require',
      'process',
      'getContextOptionsWithHeaders',
      `
let { browser, context, page } = state;
${code}
state.browser = browser;
state.context = context;
state.page = page;
`
    );

    try {
      await fn(
        captured.console,
        state,
        helpers,
        chromium,
        firefox,
        webkit,
        devices,
        requireFromSkill,
        safeProcess,
        getContextOptionsWithHeaders
      );
      return { ok: true, stdout: captured.stdout, stderr: captured.stderr };
    } catch (e) {
      const msg = e?.stack || e?.message || String(e);
      captured.stderr.push(msg);
      return { ok: false, stdout: captured.stdout, stderr: captured.stderr, error: msg };
    }
  }

  let chain = Promise.resolve();
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

  rl.on('line', (line) => {
    const raw = (line || '').trim();
    if (!raw) return;

    chain = chain.then(async () => {
      let req;
      try {
        req = JSON.parse(raw);
      } catch (_) {
        // 无效 JSON，忽略
        return;
      }

      // 验证请求格式：必须是对象且包含 id
      if (!req || typeof req !== 'object' || Array.isArray(req) || !req.id) {
        // 畸形请求，忽略（无法响应因为没有有效 id）
        serverLog('[playwright_persistent_server] Malformed request ignored:', raw.slice(0, 100));
        return;
      }

      const id = req.id;
      const method = req.method;
      const params = req.params || {};

      // 仅处理允许的 env 变量，过滤敏感变量
      const BLOCKED_ENV_KEYS = ['NODE_OPTIONS', 'PATH', 'HOME', 'USERPROFILE', 'TEMP', 'TMP'];
      if (params.env && typeof params.env === 'object') {
        for (const [k, v] of Object.entries(params.env)) {
          if (BLOCKED_ENV_KEYS.includes(k.toUpperCase())) {
            continue; // 跳过敏感变量
          }
          if (v === null || v === undefined) {
            delete process.env[k];
          } else {
            process.env[k] = String(v);
          }
        }
      }

      try {
        if (method === 'ping') {
          send({ id, ok: true, state: { alive: true } });
          return;
        }

        if (method === 'close') {
          await safeClose(state.page);
          state.page = null;
          await safeClose(state.context);
          state.context = null;
          await safeClose(state.browser);
          state.browser = null;
          send({ id, ok: true });
          setTimeout(() => process.exit(0), 10);
          return;
        }

        if (method === 'exec') {
          await ensureBrowserContextPage();
          const code = resolveCodeFromArgs(params.args);
          if (!code) {
            send({
              id,
              ok: false,
              error: 'No code to execute (args empty)',
              stdout: [],
              stderr: [],
            });
            return;
          }

          const result = await runUserCode(code);
          
          // 执行成功后保存页面状态，用于会话恢复
          if (result.ok) {
            await savePageState();
          }
          
          const pageUrl = state.page && typeof state.page.url === 'function' ? state.page.url() : null;
          const hasSavedState = savedPageState.url ? true : false;
          send({
            id,
            ok: !!result.ok,
            stdout: result.stdout || [],
            stderr: result.stderr || [],
            error: result.error,
            state: { pageUrl, hasSavedState },
          });
          return;
        }

        send({ id, ok: false, error: `Unknown method: ${method}`, stdout: [], stderr: [] });
      } catch (e) {
        const msg = e?.stack || e?.message || String(e);
        send({ id, ok: false, error: msg, stdout: [], stderr: [msg] });
      }
    });
  });

  serverLog('[playwright_persistent_server] Ready. Waiting for commands...');
}

main().catch((e) => {
  serverLog('[playwright_persistent_server] fatal:', e?.stack || String(e));
  process.exit(1);
});
