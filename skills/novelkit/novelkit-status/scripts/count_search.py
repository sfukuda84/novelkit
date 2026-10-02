#!/usr/bin/env python3
"""count_search.py - Claude Code のフックから呼ばれ、セッションごとの Web 検索の回数を記録する

.claude/settings.json の hooks に登録して使う（novelkit.py hooks install が登録する）。
- SessionStart: そのセッションの記録を 0 件で作り、「今のセッション」として印を付ける
- PostToolUse（WebSearch / WebFetch）: そのセッションの回数を 1 つ増やす

記録は <作品>/.novelkit/usage/<session_id>.json に書き、今のセッションの ID を .novelkit/usage/current に書く。
novelkit.py budget がこれを読み、次の工程に検索の回数が足りるかを判定する。
フックの失敗で作業を止めないよう、どんな入力でも終了コード 0 で終わる。標準ライブラリだけで書く（Python 3.9 以上）。
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path


def project_root(data: dict) -> Path | None:
    for cand in (os.environ.get("CLAUDE_PROJECT_DIR"), data.get("cwd"), os.getcwd()):
        if not cand:
            continue
        p = Path(cand).resolve()
        for d in [p, *p.parents]:
            if (d / ".novelkit" / "config.yaml").exists():
                return d
    return None


def main() -> None:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return
    sid = str(data.get("session_id") or "").strip()
    root = project_root(data)
    if not sid or root is None:
        return
    usage = root / ".novelkit" / "usage"
    usage.mkdir(parents=True, exist_ok=True)
    path = usage / f"{sid}.json"
    try:
        rec = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        rec = {}
    now = dt.datetime.now().isoformat(timespec="seconds")
    rec.setdefault("session_id", sid)
    rec.setdefault("started", now)
    rec.setdefault("WebSearch", 0)
    rec.setdefault("WebFetch", 0)
    event = data.get("hook_event_name")
    tool = data.get("tool_name")
    if event == "PostToolUse" and tool in ("WebSearch", "WebFetch"):
        rec[tool] = int(rec.get(tool, 0)) + 1
    rec["updated"] = now
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    if event == "SessionStart" or not (usage / "current").exists():
        (usage / "current").write_text(sid, encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - フックの失敗で作業を止めない
        pass
    sys.exit(0)
