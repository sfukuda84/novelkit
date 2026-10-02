#!/usr/bin/env python3
"""novelkit.py - novelkit の進捗管理・文脈パック・引き継ぎ書のヘルパー

ステップが終わるたびに trailer "Novelkit-Step: <STEP>"（章の工程では "Novelkit-Chapter: <章>" も）を付けて
コミットし、その trailer から完了済みのステップと次のステップを判定する。中断しても続きから再開できる。
macOS / Linux / Windows で動くように、標準ライブラリだけで書く（Python 3.9 以上）。

使い方:
  novelkit.py init [--title <作品名>]
  novelkit.py state [--chapter <章>] [--phase work|outline|write|all]
  novelkit.py checkpoint <STEP> "<subject>" [--chapter <章>] [--mode auto|normal]
  novelkit.py next --phase outline|write|all [--skip <章,...>]
  novelkit.py status
  novelkit.py chapters
  novelkit.py resolve <query>
  novelkit.py context <話番号> [--out <path>]
  novelkit.py ai-usage
  novelkit.py handover [--out <path>]
  novelkit.py budget [--step <STEP> | --need <N>]
  novelkit.py hooks install
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nklib as nk  # noqa: E402

WORK_STEPS = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W10"]
OUTLINE_STEPS = ["C2", "C3-1", "C3-2", "C3-3"]
WRITE_STEPS = ["C4", "C5", "C6", "C7", "C8", "C9", "C10"]
FINISH_STEP = "C11"
PHASE_STEPS = {
    "work": WORK_STEPS,
    "outline": OUTLINE_STEPS,
    "write": WRITE_STEPS,
    "all": OUTLINE_STEPS + WRITE_STEPS,
}
STEP_NAMES = {
    "W1": "種（novelkit-seed）", "W2": "広域調査（novelkit-research-wide）",
    "W3": "方向性の案（novelkit-direction）", "W4": "壁打ち（novelkit-sparring）",
    "W5": "焦点調査（novelkit-research-deep）", "W6": "文体の決まり（novelkit-constitution）",
    "W7": "プロット概要と核の設定（novelkit-synopsis）", "W8": "プロットの詳細化（novelkit-plot）",
    "W9": "設定の整理（novelkit-canon）", "W10": "全体の検証（novelkit-check）",
    "C2": "1 話ごとのアウトライン（novelkit-outline）",
    "C3-1": "矛盾検出 1 回目（novelkit-analyze）", "C3-2": "矛盾検出 2 回目（novelkit-analyze）",
    "C3-3": "矛盾検出 3 回目（novelkit-analyze）",
    "C4": "執筆（novelkit-draft）", "C5": "レビュー・物語軸（novelkit-review story）",
    "C6": "レビュー・整合軸（novelkit-review consistency）",
    "C7": "レビュー・類似性軸（novelkit-review originality）", "C8": "レビュー・文章軸（novelkit-review prose）",
    "C9": "収束と逆流（novelkit-converge）", "C10": "再レビュー（novelkit-review recheck）",
    "C11": "章の完了（novelkit-status finish）",
}
AI_USAGE_ORDER = ["AI本文", "AI下書き→作者推敲", "作者執筆＋AI補助", "AI不使用"]


def out(msg: str = "") -> None:
    print(msg)


def fail(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- 進捗

def completed_steps(root: Path) -> tuple[set[str], dict[str, set[str]]]:
    """(作品単位の完了ステップ, 章ごとの完了ステップ) を trailer から集める。"""
    if not nk.is_git_repo(root):
        return set(), {}
    proc = nk.git(root, ["log", "--format=%(trailers:key=Novelkit-Step,valueonly)%x1f"
                         "%(trailers:key=Novelkit-Chapter,valueonly)%x1e"], check=False)
    work: set[str] = set()
    chap: dict[str, set[str]] = {}
    for rec in proc.stdout.split("\x1e"):
        if "\x1f" not in rec:
            continue
        step, ch = (s.strip() for s in rec.split("\x1f", 1))
        if not step:
            continue
        if ch:
            chap.setdefault(ch, set()).add(step)
        else:
            work.add(step)
    return work, chap


def next_step(done: set[str], steps: list[str]) -> str | None:
    for s in steps:
        if s not in done:
            return s
    return None


def resolve_chapter(chapters: list[nk.Chapter], query: str) -> nk.Chapter:
    hits = nk.match_chapter(chapters, query)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        fail(f"章が見つかりません: {query}（chapters/ の下に <NN>-<slug> のディレクトリが必要です）", 3)
    fail("候補が複数あります: " + ", ".join(h.name for h in hits), 3)
    raise AssertionError


# ---------------------------------------------------------------- コマンド

def cmd_init(root: Path, args) -> None:
    cfgp = root / nk.CONFIG_REL
    created = []
    if not cfgp.exists():
        cfgp.parent.mkdir(parents=True, exist_ok=True)
        tmpl = Path(__file__).resolve().parent.parent / "templates" / "config.yaml"
        text = tmpl.read_text(encoding="utf-8") if tmpl.exists() else "title: \n"
        if args.title:
            title = args.title.replace('"', "'")
            text = re.sub(r"^title:.*$", lambda _m: f'title: "{title}"', text, count=1, flags=re.M)
        cfgp.write_text(text, encoding="utf-8")
        created.append(str(cfgp.relative_to(root)))
    cfg = nk.load_config(root)
    if args.config_only:
        out("CREATED: " + (", ".join(created) if created else "（なし）"))
        out("NOTE: config.yaml の paths を既存の配置に合わせてから、もう一度 init を実行するとディレクトリを作る")
        return
    for key in ("concept", "research", "plot", "canon", "chapters", "draft", "publish", "handover"):
        d = nk.pth(root, cfg, key)
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()
            created.append(str(d.relative_to(root)) + "/")
    for sub in ("character", "place", "org", "item"):
        d = nk.pth(root, cfg, "canon") / sub
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()
            created.append(str(d.relative_to(root)) + "/")
    (root / cfg["paths"]["constitution"]).parent.mkdir(parents=True, exist_ok=True)
    out("CREATED: " + (", ".join(created) if created else "（なし）"))
    out(f"ROOT: {root}")


def cmd_state(root: Path, args) -> None:
    work, chap = completed_steps(root)
    if args.chapter:
        cfg = nk.load_config(root)
        ch = resolve_chapter(nk.list_chapters(root, cfg), args.chapter)
        phase = args.phase or "all"
        steps = PHASE_STEPS[phase]
        done = chap.get(ch.name, set())
        out(f"CHAPTER: {ch.name}")
        out(f"PHASE: {phase}")
        out("COMPLETED_STEPS: " + " ".join(s for s in steps + [FINISH_STEP] if s in done))
        nxt = next_step(done, steps)
        blocked = next_step(done, OUTLINE_STEPS) if phase == "write" else None
        if blocked:
            out(f"NEXT_STEP: BLOCKED")
            out(f"BLOCKED: アウトライン工程（{blocked}）が未完了。novelkit-chapter で先に進める")
        else:
            out(f"NEXT_STEP: {nxt or (FINISH_STEP if FINISH_STEP not in done else 'DONE')}")
        missing_work = [s for s in WORK_STEPS if s not in work]
        if missing_work:
            out("WORK_PENDING: " + " ".join(missing_work))
    else:
        out("PHASE: work")
        out("COMPLETED_STEPS: " + " ".join(s for s in WORK_STEPS if s in work))
        out(f"NEXT_STEP: {next_step(work, WORK_STEPS) or 'DONE'}")


def cmd_checkpoint(root: Path, args) -> None:
    if not nk.is_git_repo(root):
        fail("Git リポジトリではありません。先に git init してください（novelkit-bootstrap の W0）。", 3)
    all_steps = WORK_STEPS + OUTLINE_STEPS + WRITE_STEPS + [FINISH_STEP]
    if args.step not in all_steps:
        fail(f"不明なステップです: {args.step}（{' '.join(all_steps)}）")
    if args.step.startswith("C") and not args.chapter:
        fail("章の工程のステップには --chapter が必要です。")
    trailers = [f"Novelkit-Step: {args.step}"]
    if args.chapter:
        cfg = nk.load_config(root)
        ch = resolve_chapter(nk.list_chapters(root, cfg), args.chapter)
        trailers.append(f"Novelkit-Chapter: {ch.name}")
    if args.mode:
        trailers.append(f"Novelkit-Mode: {args.mode}")
    if args.paths:
        # 指定したパスだけをコミットする（並行して進めた別のステップの成果物を混ぜないため）
        nk.git(root, ["add", "--", *args.paths])
        nk.git(root, ["commit", "--allow-empty", "-m", args.subject, "-m", "\n".join(trailers), "--", *args.paths])
    else:
        nk.git(root, ["add", "-A"])
        nk.git(root, ["commit", "--allow-empty", "-m", args.subject, "-m", "\n".join(trailers)])
    sha = nk.git(root, ["rev-parse", "--short", "HEAD"]).stdout.strip()
    out(f"CHECKPOINT: {args.step} {sha}")


def chapter_summary(root: Path, cfg: dict, ch: nk.Chapter, done: set[str]) -> dict:
    eps = ch.episodes
    drafted = [e for e in eps if e.draft]
    chars = sum(nk.count_chars(e.draft) for e in drafted if e.draft)
    return {
        "spec": (ch.dir / "spec.md").exists(),
        "tasks": len(eps),
        "done": sum(1 for e in eps if e.done),
        "human": sum(1 for e in eps if e.human and not e.done),
        "drafted": len(drafted),
        "final": sum(1 for e in drafted if e.draft and str(nk.draft_meta(e.draft).get("status", "")) == "確定"),
        "chars": chars,
        "next": next_step(done, PHASE_STEPS["all"]) or (FINISH_STEP if FINISH_STEP not in done else "完了"),
    }


def cmd_status(root: Path, args) -> None:
    cfg = nk.load_config(root)
    work, chap = completed_steps(root)
    chapters, episodes = nk.load_work(root, cfg)
    out(f"# 進捗 — {cfg.get('title') or root.name}（{dt.date.today().isoformat()}）")
    out()
    nxt = next_step(work, WORK_STEPS)
    out(f"作品の工程: {len([s for s in WORK_STEPS if s in work])}/{len(WORK_STEPS)} 完了"
        + (f"。次は {nxt} {STEP_NAMES[nxt]}" if nxt else "。すべて完了"))
    out()
    if not chapters:
        out("章はまだありません（novelkit-plot が chapters/<NN>-<slug>/ を作ります）。")
        return
    out("| 章 | 章仕様 | シーン台帳 | 本文（うち確定） | 字数 | 作者の担当（未完） | 次のステップ |")
    out("|---|---|---|---|---|---|---|")
    total = 0
    for ch in chapters:
        s = chapter_summary(root, cfg, ch, chap.get(ch.name, set()))
        total += s["chars"]
        nxt_c = s["next"]
        label = f"{nxt_c} {STEP_NAMES.get(nxt_c, '')}".strip()
        out(f"| {ch.name} | {'✓' if s['spec'] else '—'} | {s['done']}/{s['tasks']} | {s['drafted']}/{s['tasks']}（{s['final']}） "
            f"| {s['chars']:,} | {s['human']} | {label} |")
    out()
    out(f"本文の合計: {total:,} 字（{sum(1 for e in episodes if e.draft)} 本）")
    orphans = nk.orphan_drafts(root, cfg, episodes)
    if orphans:
        out(f"シーン台帳にない本文: {len(orphans)} 本（例: {orphans[0].relative_to(root)}）")


def cmd_next(root: Path, args) -> None:
    cfg = nk.load_config(root)
    _, chap = completed_steps(root)
    skip = set(filter(None, (args.skip or "").split(",")))
    steps = PHASE_STEPS[args.phase]
    for ch in nk.list_chapters(root, cfg):
        if ch.name in skip or str(ch.num) in skip:
            continue
        done = chap.get(ch.name, set())
        if FINISH_STEP in done:
            continue
        nxt = next_step(done, steps)
        if nxt:
            if args.phase == "write" and next_step(done, OUTLINE_STEPS):
                out(f"{ch.name}\tBLOCKED: アウトライン工程（{next_step(done, OUTLINE_STEPS)}）が未完了")
                return
            out(f"{ch.name}\t{nxt}")
            return
        if args.phase in ("write", "all"):
            out(f"{ch.name}\t{FINISH_STEP}")
            return
    out("")


def cmd_chapters(root: Path, args) -> None:
    cfg = nk.load_config(root)
    for ch in nk.list_chapters(root, cfg):
        out(ch.name)


def cmd_resolve(root: Path, args) -> None:
    cfg = nk.load_config(root)
    out(resolve_chapter(nk.list_chapters(root, cfg), args.query).name)


# ---------------------------------------------------------------- 文脈パック

def _section(title: str, body: str) -> str:
    return f"## {title}\n\n{body.strip()}\n" if body.strip() else ""


def demote(text: str, levels: int = 2) -> str:
    """埋め込む文書の見出しを levels 段下げる（文脈パックの見出しの階層を崩さないため）。"""
    return re.sub(r"^(#{1,6})(?=\s)", lambda m: "#" * min(6, len(m.group(1)) + levels), text, flags=re.M)


def state_before(ch_dir: Path, prev_ep: str | None) -> str:
    """state.md から、直前の話の終了時点の節（"## <話番号>"）を取り出す。"""
    p = ch_dir / "state.md"
    if not prev_ep or not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    m = re.search(r"^## " + re.escape(prev_ep) + nk.EP_END + r".*?(?=^## |\Z)", text, re.M | re.S)
    return m.group(0) if m else ""


def summaries_for(root: Path, chapters: list[nk.Chapter], upto: int, episodes: list[nk.Episode]) -> list[str]:
    wanted = {e.ep for e in episodes if e.index < upto}
    items = []
    for ch in chapters:
        p = ch.dir / "summaries.md"
        if not p.exists():
            continue
        for m in re.finditer(r"^## (" + nk.EPISODE_RE + r")" + nk.EP_END + r".*?(?=^## |\Z)",
                             p.read_text(encoding="utf-8"), re.M | re.S):
            if m.group(1) in wanted:
                items.append(m.group(0).strip())
    return items


def cmd_context(root: Path, args) -> None:
    cfg = nk.load_config(root)
    chapters, episodes = nk.load_work(root, cfg)
    target = next((e for e in episodes if e.ep == args.episode), None)
    if not target:
        fail(f"シーン台帳に話が見つかりません: {args.episode}", 3)
    ch = next(c for c in chapters if c.name == target.chapter)
    parts = [f"# 文脈パック — {target.ep} {target.title}\n",
             f"生成: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} / novelkit.py context\n"]

    const = root / cfg["paths"]["constitution"]
    if const.exists():
        parts.append(_section("文体の決まり（constitution）", demote(const.read_text(encoding="utf-8"))))

    # 常に入れるファイル（フロントマターを持たない正典や、時代錯誤の一覧など。config の context.always_files）
    for rel in nk.as_list(cfg["context"].get("always_files")):
        fp = root / str(rel)
        if fp.exists():
            _, body, _ = nk.split_frontmatter(fp.read_text(encoding="utf-8"))
            parts.append(_section(f"常に参照するもの: {rel}", demote(body)))

    parts.append(_section("この話のシーン台帳", target.block))

    spec = ch.dir / "spec.md"
    if spec.exists():
        spec_text = spec.read_text(encoding="utf-8")
        picked = [ln for ln in spec_text.splitlines() if any(r in ln for r in target.refs)]
        head = re.search(r"^## 章の役割.*?(?=^## |\Z)", spec_text, re.M | re.S)
        body = (demote(head.group(0), 1) if head else "") + "\n\n### この話が担う ID\n\n" + ("\n".join(picked) or "（なし）")
        parts.append(_section(f"章仕様（{ch.name}）の抜粋", body))

    # 正典: always と、この話のシーン台帳に名前が出る mention。never は渡さない。
    canon = nk.load_canon(root, cfg)
    epmap = nk.episode_index_map(episodes)
    probe = target.block + "\n" + target.title
    picked_entries, hidden_rules = [], []
    for c in canon:
        if c.hidden_names and nk.before_reveal(target, c.reveal_from, epmap):
            hidden_rules.append(f"- 「{'」「'.join(c.hidden_names)}」は {c.reveal_from} まで本文に出さない（{c.path.relative_to(root)}）")
        if c.ai == "never":
            continue
        if c.ai == "always" or any(n and n in probe for n in c.names):
            picked_entries.append(c)
    if hidden_rules:
        parts.append(_section("この話で伏せるもの（必ず守る）", "\n".join(hidden_rules)))
    if picked_entries:
        body = "\n\n".join(f"### {c.name}（{c.type} / {c.path.relative_to(root)}）\n\n{demote(c.body.strip(), 3)}"
                           for c in picked_entries)
        parts.append(_section("正典（この話に関係する項目）", body))

    promises = nk.read_table(nk.pth(root, cfg, "plot") / "promises.md", require="ID")
    block_ids = set(re.findall(r"(?<![A-Za-z])[A-Z]{1,3}-[0-9]{2,3}(?![0-9])", target.block))
    rel = [r for r in promises if r.get("ID", "").strip() and (
        r["ID"].strip() in block_ids
        or any(target.ep in re.findall(nk.EPISODE_RE, r.get(col, "")) for col in ("張る", "進展", "回収予定", "回収")))]
    if rel:
        cols = [k for k in promises[0].keys() if k != "_line"]
        lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        lines += ["| " + " | ".join(r.get(k, "") for k in cols) + " |" for r in rel]
        parts.append(_section("伏線・約束（この話で張る・進める・回収するもの）", "\n".join(lines)))

    prev = [e for e in episodes if e.index < target.index]
    prev_ep = prev[-1] if prev else None
    if prev_ep:
        st = state_before(next(c for c in chapters if c.name == prev_ep.chapter).dir, prev_ep.ep)
        parts.append(_section(f"直前の話（{prev_ep.ep}）の終了時点の状態", demote(st, 1) if st else "（state.md に記録がない）"))

    n_full = int(cfg["context"].get("full_text_prev", 2) or 0)
    full_eps = [e for e in prev if e.chapter == target.chapter][-n_full:] if n_full else []
    summ_upto = full_eps[0].index if full_eps else target.index
    summ = summaries_for(root, chapters, summ_upto, episodes)
    limit = int(cfg["context"].get("summary_limit", 0) or 0)
    if limit and len(summ) > limit:
        summ = summ[-limit:]
    if summ:
        parts.append(_section("これまでの話の要約", demote("\n\n".join(summ), 1)))
    for e in full_eps:
        if e.draft:
            _, body, _ = nk.split_frontmatter(e.draft.read_text(encoding="utf-8"))
            parts.append(_section(f"直前の本文 {e.ep} {e.title}", demote(body)))

    text = "\n".join(p for p in parts if p)
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(text, encoding="utf-8")
        out(f"CONTEXT: {op}（{len(text):,} 字）")
    else:
        out(text)


# ---------------------------------------------------------------- AI 関与・引き継ぎ

def cmd_ai_usage(root: Path, args) -> None:
    cfg = nk.load_config(root)
    _, episodes = nk.load_work(root, cfg)
    counts: dict[str, int] = {}
    missing, drafts = [], []
    for e in episodes:
        if not e.draft:
            continue
        meta = nk.draft_meta(e.draft)
        v = str(meta.get("ai") or "")
        if str(meta.get("status") or "") == "下書き":
            drafts.append(e.ep)
        if not v:
            missing.append(e.ep)
            continue
        counts[v] = counts.get(v, 0) + 1
    out("| AI の関与 | 本数 |")
    out("|---|---|")
    for k in AI_USAGE_ORDER + sorted(set(counts) - set(AI_USAGE_ORDER)):
        if k in counts:
            out(f"| {k} | {counts[k]} |")
    if missing:
        out(f"\n記録のない本文: {', '.join(missing)}")
    if drafts:
        out(f"\n確定していない下書き（作者の推敲前。申告の集計には、確定した後の値を使う）: {', '.join(drafts)}")
    strongest = next((k for k in AI_USAGE_ORDER if k in counts), None)
    if strongest:
        out(f"\n作品全体で最も強い関与: {strongest}（投稿先の申告区分は novelkit-publish で公式の規約を確かめて決める）")


def cmd_handover(root: Path, args) -> None:
    import io
    import contextlib
    cfg = nk.load_config(root)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_status(root, args)
    lines = [f"# 引き継ぎ書 {dt.date.today().isoformat()}", "", buf.getvalue().replace("# 進捗", "## 進捗", 1)]
    if nk.is_git_repo(root):
        log = nk.git(root, ["log", "-15", "--format=- %h %ad %s", "--date=short"], check=False).stdout
        lines += ["## 直近のコミット", "", log.strip(), ""]
    # 未決事項: [NEEDS CLARIFICATION] と auto-decisions の見直し優先度「高」
    todo = []
    bases = [nk.pth(root, cfg, k) for k in ("concept", "research", "plot", "canon", "chapters")]
    files = {p for b in bases if b.is_dir() for p in b.rglob("*.md")}
    if (root / "docs").is_dir():
        files |= set((root / "docs").glob("*.md"))
    for p in sorted(files):
        if "context" in p.parts:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        is_auto = p.name == "auto-decisions.md"
        for no, line in enumerate(text.splitlines(), 1):
            high = is_auto and re.search(r"(優先度[:：]?\s*高|\|\s*高\s*\|)", line)
            if "[NEEDS CLARIFICATION" in line or high:
                todo.append(f"- `{p.relative_to(root)}:{no}` {line.strip()[:120]}")
    lines += ["## 未決事項・見直しの候補", "", "\n".join(todo) or "（なし）", ""]
    text = "\n".join(lines)
    target = Path(args.out) if args.out else nk.pth(root, cfg, "handover") / f"{dt.date.today().isoformat()}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    out(f"HANDOVER: {target}")


# ---------------------------------------------------------------- セッションの区切り（検索の回数）

HOOK_SCRIPT = "skills/novelkit/novelkit-status/scripts/count_search.py"


def current_usage(root: Path) -> dict | None:
    """フックが記録した、今のセッションの回数。記録がなければ None（数えられない環境）。"""
    import json
    usage = root / ".novelkit" / "usage"
    cur = usage / "current"
    if not cur.exists():
        return None
    sid = cur.read_text(encoding="utf-8").strip()
    path = usage / f"{sid}.json"
    if not path.exists():
        return {"session_id": sid, "WebSearch": 0, "WebFetch": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def cmd_budget(root: Path, args) -> None:
    """次の工程に、今のセッションの Web 検索の残りが足りるかを判定する。

    終了コード: 0 = OK（続けてよい）、4 = STOP（工程の区切りで止まり、新しいセッションで再開する）、
    0 かつ VERDICT: UNMETERED = 数えられない環境（手順書の区切りの規則に従う）
    """
    cfg = nk.load_config(root)
    sc = cfg.get("session", {})
    limit = int(sc.get("web_search_limit", 200))
    reserve = int(sc.get("reserve", 10))
    est = sc.get("estimates", {}) or {}
    need = args.need if args.need is not None else int(est.get(args.step, 0) or 0) if args.step else 0
    u = current_usage(root)
    out(f"STEP: {args.step or '-'}")
    out(f"NEED: {need}")
    out(f"LIMIT: {limit}（reserve {reserve}）")
    if u is None:
        settings = root / ".claude" / "settings.json"
        registered = settings.exists() and HOOK_SCRIPT in settings.read_text(encoding="utf-8")
        out("VERDICT: UNMETERED")
        if registered:
            out("NOTE: フックは登録済みだが、まだ記録がない（登録した後に Claude Code を起動し直していない）。"
                f"このセッションは、手順書の区切りの規則に従う（1 セッション {sc.get('chapters_unmetered', 1)} 章まで）")
        else:
            out("NOTE: 検索の回数を数えるフックがない（Claude Code 以外、または novelkit.py hooks install の前）。"
                f"手順書の区切りの規則に従う（1 セッション {sc.get('chapters_unmetered', 1)} 章まで）")
        return
    used = int(u.get("WebSearch", 0))
    remaining = limit - reserve - used
    out(f"SESSION: {u.get('session_id')}")
    out(f"USED: WebSearch {used} / WebFetch {u.get('WebFetch', 0)}")
    out(f"REMAINING: {remaining}")
    if need > remaining:
        out("VERDICT: STOP")
        out("NOTE: 工程の区切りで止まり、新しいセッションで同じスキルを実行して再開する")
        sys.exit(4)
    out("VERDICT: OK")


def cmd_hooks(root: Path, args) -> None:
    """作品の .claude/settings.json に、検索の回数を数えるフックを登録する（既存の設定は残す）。"""
    import json
    if args.action != "install":
        fail("使い方: novelkit.py hooks install")
    path = root / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conf = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError:
        fail(f"{path} が JSON として読めません。手で直してから、もう一度実行してください。")
    command = f'python3 "$CLAUDE_PROJECT_DIR/{HOOK_SCRIPT}"'
    hooks = conf.setdefault("hooks", {})
    added = []
    for event, matcher in (("SessionStart", None), ("PostToolUse", "WebSearch|WebFetch")):
        entries = hooks.setdefault(event, [])
        if any(h.get("command") == command for e in entries for h in e.get("hooks", [])):
            continue
        entry = {"hooks": [{"type": "command", "command": command}]}
        if matcher:
            entry = {"matcher": matcher, **entry}
        entries.append(entry)
        added.append(event)
    path.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gi = root / ".gitignore"
    line = ".novelkit/usage/"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if line not in text.splitlines():
        gi.write_text(text.rstrip("\n") + ("\n" if text else "") + "\n# novelkit の検索回数の記録（セッションごと）\n" + line + "\n", encoding="utf-8")
    out(f"HOOKS: {path}（追加: {', '.join(added) or 'なし（登録済み）'}）")
    out("NOTE: 次に Claude Code を起動したセッションから数え始める")


def main() -> None:
    ap = argparse.ArgumentParser(description="novelkit の進捗管理ヘルパー")
    ap.add_argument("--root", help="作品のルート（省略時はカレントから探す）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("--title")
    p.add_argument("--config-only", action="store_true", help="config.yaml だけを作る（既存作品の取り込み用）")
    p = sub.add_parser("state"); p.add_argument("--chapter"); p.add_argument("--phase", choices=list(PHASE_STEPS))
    p = sub.add_parser("checkpoint"); p.add_argument("step"); p.add_argument("subject")
    p.add_argument("--chapter"); p.add_argument("--mode", choices=["auto", "normal"])
    p.add_argument("--paths", nargs="+", help="このパスだけをコミットする（省略時は変更をすべてコミットする）")
    p = sub.add_parser("next"); p.add_argument("--phase", choices=["outline", "write", "all"], required=True)
    p.add_argument("--skip")
    sub.add_parser("status"); sub.add_parser("chapters")
    p = sub.add_parser("resolve"); p.add_argument("query")
    p = sub.add_parser("context"); p.add_argument("episode"); p.add_argument("--out")
    sub.add_parser("ai-usage")
    p = sub.add_parser("handover"); p.add_argument("--out")
    p = sub.add_parser("budget"); p.add_argument("--step"); p.add_argument("--need", type=int)
    p = sub.add_parser("hooks"); p.add_argument("action", choices=["install"])
    args = ap.parse_args()
    root = Path(args.root).resolve() if args.root else nk.find_root()
    try:
        {
            "init": cmd_init, "state": cmd_state, "checkpoint": cmd_checkpoint, "next": cmd_next,
            "status": cmd_status, "chapters": cmd_chapters, "resolve": cmd_resolve,
            "context": cmd_context, "ai-usage": cmd_ai_usage, "handover": cmd_handover,
            "budget": cmd_budget, "hooks": cmd_hooks,
        }[args.cmd](root, args)
    except (RuntimeError, nk.YamlError) as e:
        fail(str(e))


if __name__ == "__main__":
    main()
