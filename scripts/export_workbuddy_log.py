#!/usr/bin/env python3
"""导出 WorkBuddy 会话原始记录为可提交的 Markdown。

用途：麦当劳程序员创意开发大赛要求提交 workbuddy.md（WorkBuddy 对话上下文），
本脚本把本地会话 JSONL 转成带脱敏的可读记录。

用法：
  python scripts/export_workbuddy_log.py                 # 自动定位当前项目最近会话
  python scripts/export_workbuddy_log.py --session <id>  # 指定会话
  python scripts/export_workbuddy_log.py --out path.md   # 指定输出

安全：导出前对全文做密钥脱敏（MCP Token / JWT / 云 AK / 常见密钥字段），
结束后自动校验输出中不含已知密钥Pattern，含任何一项即报错退出。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = Path.home() / ".workbuddy" / "projects"

# ————————————————— 脱敏规则 —————————————————
SCRUB_PATTERNS = [
    # 已知密钥（具体值优先，来自本地 mcp.json / 环境变量）
    (re.compile(r"L51ggzZOOw9850uFYgpsZDTURAnV2YI1"), "<MCD_MCP_TOKEN>"),
    # JWT / Token 形态
    (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "<JWT>"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{16,}"), "Bearer <TOKEN>"),
    # 腾讯云 AK / 签名串
    (re.compile(r"AKID[A-Za-z0-9]{16,}"), "<CLOUD_AK>"),
    (re.compile(r"q-signature=[a-f0-9]{20,}"), "q-signature=<SIG>"),
    # 常见密钥字段赋值
    (re.compile(r"(?i)\b(token|password|passwd|secret|api[_-]?key|access[_-]?key)\b(\s*[=:]\s*)[\"']?[A-Za-z0-9_\-\.]{12,}"), r"\1\2<REDACTED>"),
]
FORBIDDEN_AFTER_SCRUB = ["L51ggzZOOw9850uFYgpsZDTURAnV2YI1", "eyJhbGciOi", "AKIDCD6mEcX25"]


def scrub(text: str) -> str:
    for pattern, repl in SCRUB_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _cwd_slug(cwd: str) -> str:
    return cwd.replace(":", "").replace("/", "-").replace("\\", "-").lstrip("-")


def find_session(explicit: str | None) -> Path:
    if explicit:
        p = PROJECTS_DIR / _cwd_slug("E:/Project/mmcode") / f"{explicit}.jsonl"
        if p.exists():
            return p
        for f in PROJECTS_DIR.rglob(f"{explicit}.jsonl"):
            return f
        raise SystemExit(f"找不到会话 {explicit}")
    # 当前项目目录下最近修改的会话
    slug = _cwd_slug("E:/Project/mmcode")
    candidates = sorted((PROJECTS_DIR / slug).glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise SystemExit(f"未找到 {slug} 下的会话记录")
    return candidates[0]


SYSTEM_REMINDER = re.compile(r"<system-reminder\b.*?</system-reminder>", re.S)


def clean_user_text(text: str) -> str:
    """压缩系统提示块，保留用户真实表述。"""
    text = SYSTEM_REMINDER.sub("<system-reminder 已省略>", text)
    return text.strip()


def render_entry(d: dict) -> str:
    t = d.get("type")
    ts = datetime.fromtimestamp(d.get("timestamp", 0) / 1000).strftime("%m-%d %H:%M")
    if t == "message":
        role = d.get("role", "?")
        parts = []
        for c in d.get("content", []):
            if c.get("type") in ("input_text", "output_text", "text"):
                parts.append(c.get("text", ""))
        text = "\n".join(p for p in parts if p).strip()
        if not text:
            return ""
        who = "👤 用户" if role == "user" else "🤖 助手"
        text = clean_user_text(text) if role == "user" else text
        return f"\n## [{ts}] {who}\n\n{text}\n"
    if t == "function_call":
        name = d.get("name", "?")
        args = d.get("arguments", "")
        if len(args) > 600:
            args = args[:600] + f"\n…（参数过长已截断，原长 {len(d.get('arguments', ''))} 字符）"
        return f"\n### 🔧 工具调用：`{name}`\n\n```json\n{args}\n```\n"
    if t == "function_call_result":
        result = d.get("result", d.get("content", ""))
        if isinstance(result, (dict, list)):
            result = json.dumps(result, ensure_ascii=False)
        result = str(result)
        if len(result) > 300:
            result = result[:300] + f"\n…（结果过长已截断，原长 {len(result)} 字符）"
        return f"\n<details><summary>📥 工具结果</summary>\n\n```\n{result}\n```\n\n</details>\n"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="导出 WorkBuddy 会话原始记录")
    ap.add_argument("--session", default=None, help="会话 ID（缺省取当前项目最近会话）")
    ap.add_argument("--out", default=None, help="输出路径（缺省 <repo>/workbuddy-raw-export.md）")
    args = ap.parse_args()

    session_file = find_session(args.session)
    out_path = Path(args.out) if args.out else REPO_ROOT / "workbuddy-raw-export.md"

    entries = []
    stats = {"message": 0, "function_call": 0, "function_call_result": 0, "reasoning": 0, "other": 0}
    for ln in session_file.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        t = d.get("type", "other")
        if t in ("message", "function_call", "function_call_result", "reasoning"):
            stats[t] += 1
        else:
            stats["other"] += 1
        if t == "reasoning":
            continue  # 内部推理过程，不属于对话上下文
        rendered = render_entry(d)
        if rendered:
            entries.append(scrub(rendered))

    session_id = session_file.stem
    header = [
        "# WorkBuddy 开发会话原始记录（导出件）",
        "",
        f"- 会话 ID：`{session_id}`",
        f"- 项目目录：`E:/Project/mmcode`（麦门食堂 McCanteen）",
        f"- 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 统计：用户/助手消息 {stats['message']} 条 · 工具调用 {stats['function_call']} 次 · 工具结果 {stats['function_call_result']} 个",
        "- 说明：本文件由 `scripts/export_workbuddy_log.py` 从本地会话记录自动导出；",
        "  系统提示块已压缩省略，内部推理过程未包含，全部密钥字段已脱敏；",
        "  人工整理版见同目录 `workbuddy.md`。",
        "",
        "---",
        "",
    ]
    content = "\n".join(header) + "\n".join(entries)

    # 安全校验：输出中不得残留已知密钥
    leaks = [p for p in FORBIDDEN_AFTER_SCRUB if p in content]
    if leaks:
        print(f"❌ 脱敏校验失败，输出中仍包含：{leaks}", file=sys.stderr)
        return 1

    out_path.write_text(content, encoding="utf-8")
    print(f"✅ 已导出：{out_path}")
    print(f"   大小：{out_path.stat().st_size / 1024:.0f} KB · 消息 {stats['message']} · 工具调用 {stats['function_call']}")
    print("   脱敏校验：通过（无已知密钥残留）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
