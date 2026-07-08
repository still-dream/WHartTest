# -*- coding: utf-8 -*-
"""
Airtest one-shot pipeline.

  STEP 1  runner   -- run .air script, write raw log
  STEP 2  reporter -- turn the log into an HTML report (with assets)
  STEP 3  pack     -- inline all assets into ONE standalone HTML (offline)

Usage:
    python run_all.py                  # full pipeline
    python run_all.py --skip-run       # reuse existing log, re-run report+pack
    python run_all.py --skip-pack      # stop after report
    python run_all.py --only-pack      # only repack the most recent report
    python run_all.py --no-open        # do not auto-open the HTML

Edit the CONFIG block below to match your setup.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ============================== CONFIG ==============================
AIRTEST_EXE = r"C:\Program Files\AirtestIDE-win-1.2.17\AirtestIDE\AirtestIDE"

SCRIPT_PATH = r"C:\scripts\untitled.air"
DEVICE_URI  = (r"android://127.0.0.1:5037/118f492e"
               r"?cap_method=MINICAP&&ori_method=MINICAPORI&&touch_method=MINITOUCH")

WORK_DIR   = r"C:\test\log_untitled"   # all outputs live under here
LANG       = "zh"
OPEN_AFTER = True                      # auto-open the standalone HTML in browser
# ====================================================================

# Internal layout (auto-derived, do not edit)
WORK       = Path(WORK_DIR)
LOG_DIR    = WORK / "log"              # raw runner output
REPORT_DIR = WORK / "report"           # timestamped reporter output
HTML_DIR   = WORK / "standalone"       # timestamped standalone HTMLs

SCRIPT_NAME = Path(SCRIPT_PATH).stem           # e.g. "untitled"
LOG_SUB     = f"{SCRIPT_NAME}.log"             # subdir the reporter creates


# ============================== HELPERS =============================
def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def line(c: str = "=", n: int = 64) -> None:
    print(c * n)


def header(title: str) -> None:
    line()
    print(f" {title}")
    line()


def fmt_cmd(cmd: list[str]) -> str:
    return " ".join(f'"{c}"' if " " in c else c for c in cmd)


def run_cmd(cmd: list[str], cwd: str | None = None) -> None:
    print("  $ " + fmt_cmd(cmd))
    if cwd:
        print(f"    (cwd: {cwd})")
    ret = subprocess.run(cmd, cwd=cwd)
    if ret.returncode != 0:
        raise RuntimeError(f"command exited with code {ret.returncode}")


def latest_subdir(parent: Path) -> Path:
    if not parent.exists():
        raise FileNotFoundError(f"directory not found: {parent}")
    subs = [p for p in parent.iterdir() if p.is_dir()]
    if not subs:
        raise FileNotFoundError(f"no sub-directories in: {parent}")
    subs.sort(key=lambda p: p.stat().st_mtime)
    return subs[-1]


# ============================== STEP 1 ==============================
def step_run() -> None:
    header(f"STEP 1/3  Run Airtest script  [{stamp()}]")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [AIRTEST_EXE, "runner", SCRIPT_PATH,
           "--device", DEVICE_URI,
           "--log", str(LOG_DIR)]
    t0 = time.time()
    run_cmd(cmd)
    print(f"  -> log saved to: {LOG_DIR}  ({time.time() - t0:.1f}s)")


# ============================== STEP 2 ==============================
def step_report(run_stamp: str) -> Path:
    """Generate the HTML report. Returns the path to the report folder
    that contains log.html + assets."""
    header(f"STEP 2/3  Generate HTML report  [{run_stamp}]")
    out = REPORT_DIR / run_stamp
    out.mkdir(parents=True, exist_ok=True)
    cmd = [AIRTEST_EXE, "reporter", SCRIPT_PATH,
           "--log_root", str(LOG_DIR),
           "--lang", LANG,
           "--export", str(out)]
    t0 = time.time()
    run_cmd(cmd)
    html_dir = out / LOG_SUB
    if not (html_dir / "log.html").is_file():
        raise FileNotFoundError(f"reporter did not produce {html_dir / 'log.html'}")
    print(f"  -> report saved to: {html_dir}  ({time.time() - t0:.1f}s)")
    return html_dir


# ============================== STEP 3 ==============================
# ---- pack_html: refactored from 打包单文件HTML.py as a pure function ----
MIME = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp",
    "ico": "image/x-icon", "bmp": "image/bmp",
    "eot": "application/vnd.ms-fontobject",
    "ttf": "font/ttf", "woff": "font/woff", "woff2": "font/woff2",
    "otf": "font/otf",
}

IMG_EXTS = ("jpg", "jpeg", "png", "gif", "webp")


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _to_uri(p: Path) -> str:
    ext = p.suffix.lstrip(".").lower() if p.suffix else ""
    mime = MIME.get(ext, "application/octet-stream")
    data = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def _resolve(base: Path, rel: str) -> Path:
    rel = rel.replace("\\", "/").replace("//", "/").lstrip("/")
    return (base / rel).resolve()


def _inline_css_urls(css: str, css_dir: Path) -> str:
    def repl(m: re.Match) -> str:
        q = m.group(1) or ""
        path = m.group(2)
        if path.startswith("data:") or "://" in path:
            return m.group(0)
        fp = _resolve(css_dir, path)
        return f"url({q}{_to_uri(fp)}{q})" if fp.is_file() else m.group(0)

    return re.sub(r'url\((["\']?)([^)"\']+)\1\)', repl, css)


def pack_html(html_path: Path, out_path: Path) -> Path:
    """Inline all assets referenced by `html_path` into a single standalone
    file written to `out_path`. Returns `out_path`."""
    html_path = Path(html_path)
    out_path = Path(out_path)
    log_dir = html_path.parent
    html = _read_text(html_path)
    print(f"  [1/7] read {html_path.name}  ({len(html):,} chars)")

    # 1) external CSS -> inline <style>
    def link_repl(m: re.Match) -> str:
        fp = _resolve(log_dir, m.group(1))
        if not fp.is_file():
            return m.group(0)
        return f"<style>{_inline_css_urls(_read_text(fp), fp.parent)}</style>"

    html = re.sub(r'<link[^>]+href=["\']([^"\']+)["\'][^>]*>', link_repl, html)
    print("  [2/7] inlined external CSS")

    # 2) external JS -> inline <script>
    def script_repl(m: re.Match) -> str:
        fp = _resolve(log_dir, m.group(1))
        return f"<script>{_read_text(fp)}</script>" if fp.is_file() else m.group(0)

    html = re.sub(r'<script[^>]+src=["\']([^"\']+)["\'][^>]*></script>',
                  script_repl, html)
    print("  [3/7] inlined external JS")

    # 3) <img src="...">
    def img_repl(m: re.Match) -> str:
        pre, src, post = m.group(1), m.group(2), m.group(3)
        if src.startswith("data:"):
            return m.group(0)
        fp = _resolve(log_dir, src)
        return f'<img{pre}src="{_to_uri(fp)}"{post}>' if fp.is_file() else m.group(0)

    html = re.sub(r'<img([^>]+)src=["\']([^"\']+)["\']([^>]*)>', img_repl, html)
    print("  [4/7] inlined <img> tags")

    # 4) url() inside remaining <style> blocks (resolve against log_dir)
    def style_block_repl(m: re.Match) -> str:
        tag, body = m.group(1), m.group(2)
        return tag + _inline_css_urls(body, log_dir) + "</style>"

    html = re.sub(r'(<style[^>]*>)(.*?)</style>', style_block_repl,
                  html, flags=re.DOTALL)
    print("  [5/7] inlined url() in <style> blocks")

    # 5) image paths embedded in JSON data
    def data_repl(m: re.Match, key: str) -> str:
        p = m.group(1).replace("\\", "/").replace("//", "/")
        fp = log_dir / p
        return f'"{key}": "{_to_uri(fp)}"' if fp.is_file() else m.group(0)

    img_pat = r"(?:" + "|".join(IMG_EXTS) + r")"
    html = re.sub(rf'"src":\s*"((?:log[/\\]+)[^"]+\.{img_pat})"',
                  lambda m: data_repl(m, "src"), html, flags=re.IGNORECASE)
    html = re.sub(rf'"thumbnail":\s*"((?:log[/\\]+)[^"]+\.{img_pat})"',
                  lambda m: data_repl(m, "thumbnail"), html, flags=re.IGNORECASE)
    html = re.sub(rf'"image":\s*"([A-Za-z0-9_.-]+\.{img_pat})"',
                  lambda m: data_repl(m, "image"), html, flags=re.IGNORECASE)
    print("  [6/7] inlined image paths in JSON data")

    # 6) neutralize static_root so the JS doesn't try to rebuild paths
    html = html.replace('"static_root": "static//"', '"static_root": ""')

    # 7) build a lookup of static images and inject a fixup that rewrites
    #    src= attributes on dynamically-created <img> elements at runtime
    static_img_dir = log_dir / "static" / "image"
    lookup: dict[str, str] = {}
    if static_img_dir.is_dir():
        for f in static_img_dir.iterdir():
            if f.is_file():
                lookup[f"image/{f.name}"] = _to_uri(f)

    fixup = (
        "<script>\n(function(){\n"
        f"  var __imgs = {json.dumps(lookup, ensure_ascii=False)};\n"
        "  function fixImg(img){"
        "var a=['src','data-src','orgin-src'];"
        "for(var i=0;i<a.length;i++){var v=img.getAttribute(a[i]);"
        "if(!v||v.indexOf('data:')===0)continue;"
        "var k=v,idx=v.indexOf('image/');if(idx>=0)k=v.substring(idx);"
        "if(__imgs[k])img.setAttribute(a[i],__imgs[k]);}}"
        "  function fixAll(){var imgs=document.querySelectorAll('img');"
        "for(var i=0;i<imgs.length;i++)fixImg(imgs[i]);}"
        "  function start(){fixAll();setTimeout(fixAll,200);setTimeout(fixAll,1500);"
        "if(window.MutationObserver&&document.body)"
        "new MutationObserver(fixAll).observe(document.body,"
        "{childList:true,subtree:true,attributes:true,"
        "attributeFilter:['src','data-src','orgin-src']});}"
        "  if(document.readyState==='loading')"
        "document.addEventListener('DOMContentLoaded',start);else start();"
        "})();\n</script>"
    )

    idx = html.lower().rfind("</body>")
    html = html[:idx] + fixup + html[idx:] if idx >= 0 else html + fixup
    print("  [7/7] injected image-path fixup script")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    size = out_path.stat().st_size
    print(f"  -> wrote {out_path}  ({size / 1024 / 1024:.2f} MB)")
    return out_path


def step_pack(html_dir: Path, run_stamp: str) -> Path:
    header(f"STEP 3/3  Pack into standalone HTML  [{run_stamp}]")
    src = html_dir / "log.html"
    if not src.is_file():
        raise FileNotFoundError(f"log.html not found in {html_dir}")
    out = HTML_DIR / f"{run_stamp}.html"
    t0 = time.time()
    pack_html(src, out)
    print(f"  -> done in {time.time() - t0:.1f}s")
    return out


# ============================== MAIN ================================
def main() -> int:
    ap = argparse.ArgumentParser(description="Airtest one-shot pipeline.")
    ap.add_argument("--skip-run",  action="store_true",
                    help="reuse existing log, only re-generate report+pack")
    ap.add_argument("--skip-pack", action="store_true",
                    help="stop after generating the report")
    ap.add_argument("--only-pack", action="store_true",
                    help="pack the most recent report, skip run+report")
    ap.add_argument("--stamp",     default=None,
                    help="custom timestamp folder name (default: now)")
    ap.add_argument("--no-open",   action="store_true",
                    help="do not auto-open the standalone HTML")
    args = ap.parse_args()

    WORK.mkdir(parents=True, exist_ok=True)
    run_stamp = args.stamp or stamp()
    t0 = time.time()
    standalone: Path | None = None

    try:
        if args.only_pack:
            html_dir = latest_subdir(REPORT_DIR) / LOG_SUB
            standalone = step_pack(html_dir, run_stamp)
        else:
            if args.skip_run:
                print("[STEP 1/3] skipped (--skip-run)")
            else:
                step_run()

            html_dir = step_report(run_stamp)

            if args.skip_pack:
                print("[STEP 3/3] skipped (--skip-pack)")
            else:
                standalone = step_pack(html_dir, run_stamp)
    except Exception as e:
        print()
        line("!")
        print(f" PIPELINE FAILED: {e}")
        line("!")
        return 1

    line()
    print(f" DONE in {time.time() - t0:.1f}s")
    if standalone:
        print(f" Standalone HTML : {standalone}")
        if OPEN_AFTER and not args.no_open:
            try:
                if hasattr(os, "startfile"):
                    os.startfile(str(standalone))   # Windows
                else:
                    import webbrowser
                    webbrowser.open(standalone.as_uri())  # macOS/Linux
            except Exception as e:
                print(f"  (could not auto-open: {e})")
    line()
    return 0


if __name__ == "__main__":
    sys.exit(main())
