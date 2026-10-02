#!/usr/bin/env python3
"""phrases.py - 類似性軸（novelkit-review originality）で Web 検索にかける候補を、本文から抜き出す

- 表現の検索: 各話から、特徴的な文（地の文・台詞）を均等に選び、完全一致の検索語（「…」）として並べる。
  ありふれた短い文より、固有の語が多く、ある程度の長さのある文を優先する。
- 展開の検索: 各話の要約（summaries.md）と、作品の題・主要人物・舞台から、あらすじの検索語の材料を並べる。
結果は Markdown で標準出力に出す（--out でファイルに書く）。判定はしない。判定は SKILL.md の手順で行う。
標準ライブラリだけで書く（Python 3.9 以上）。

使い方:
  phrases.py [--root <作品>] [--chapter <章>] [--per-episode 8] [--out <path>]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "novelkit-status" / "scripts"))
import nklib as nk  # noqa: E402

SENT_RE = re.compile(r"[^。！？!?」]+[。！？!?]?」?")
KANJI_KATA_RE = re.compile(r"[一-鿿々゠-ヿ]")
BREAK_RE = re.compile(r"^[\s　]*[＊*◇◆□■○●☆★※・―—\-]+[\s　]*$")


SIMILE_RE = re.compile(r"ような|ように|みてえ|みたいに|みたいな|ごとく|さながら")


def sentences(path: Path) -> list[tuple[int, str, bool]]:
    """(行番号, 文, 台詞か) の一覧。場面区切りの行は除く。"""
    out = []
    for no, line in nk.body_lines(path):
        s = line.strip().lstrip("　")
        if not s or BREAK_RE.match(line):
            continue
        is_dialogue = s[0] in "「『"
        for m in SENT_RE.finditer(s):
            t = m.group(0).strip().strip("「」『』")
            if t:
                out.append((no, t, is_dialogue))
    return out


def score(text: str) -> float:
    """固有の語が多く、12〜45 字程度の文ほど高い。短すぎる文は 0。"""
    n = len(text)
    if n < 10:
        return 0.0
    dens = len(KANJI_KATA_RE.findall(text)) / n
    length = 1.0 if 12 <= n <= 45 else 0.6
    return dens * length + len(set(text)) / 100


def pick_ranked(sents: list[tuple[int, str, bool]], k: int) -> list[tuple[str, int, str]]:
    """害の大きい順（最後の一文 → 台詞 → 比喩 → 地の文）に、合わせて k 件を選ぶ。(区分, 行番号, 文) を返す。"""
    chosen: list[tuple[str, int, str]] = []
    seen: set[str] = set()

    def take(kind: str, items, limit: int) -> None:
        for no, t, _ in items:
            if len(chosen) >= k or limit <= 0:
                return
            if t in seen or score(t) == 0:
                continue
            chosen.append((kind, no, t))
            seen.add(t)
            limit -= 1

    if not sents:
        return chosen
    take("最後の一文", [sents[-1]], 1)
    dialogue = sorted([x for x in sents if x[2]], key=lambda x: -score(x[1]))
    take("台詞", dialogue, max(1, k // 3))
    similes = [x for x in sents if SIMILE_RE.search(x[1])]
    take("比喩", similes, max(1, k // 4))
    rest = [x for x in sents if not x[2]]
    # 残りは、話の全体から偏りなく選ぶ
    if rest and len(chosen) < k:
        n = k - len(chosen)
        size = len(rest) / n
        segs = [rest[int(i * size): int((i + 1) * size)] or rest[-1:] for i in range(n)]
        take("地の文", [max(seg, key=lambda x: score(x[1])) for seg in segs], n)
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser(description="類似性軸の検索候補を抜き出す")
    ap.add_argument("--root")
    ap.add_argument("--chapter")
    ap.add_argument("--per-episode", type=int, default=8)
    ap.add_argument("--out")
    args = ap.parse_args()
    root = Path(args.root).resolve() if args.root else nk.find_root()
    cfg = nk.load_config(root)
    chapters, episodes = nk.load_work(root, cfg)
    if args.chapter:
        hits = nk.match_chapter(chapters, args.chapter)
        if len(hits) != 1:
            sys.exit(f"章を 1 つに決められません: {args.chapter}")
        chapters = hits
    lines = [f"# 類似性軸の検索候補 — {cfg.get('title') or root.name}", ""]
    lines += ["## 1. 表現の検索（完全一致）", "",
              "害の大きい順（最後の一文 → 台詞 → 比喩 → 地の文）に並べてある。上から順に、各文を引用符で囲んで検索する（例: `\"<文>\"`）。長い文は、文の中の特徴的な 12〜20 字を切り出して検索する。", ""]
    for ch in chapters:
        for e in ch.episodes:
            if not e.draft:
                continue
            lines.append(f"### {e.ep} {e.title}（{e.draft.relative_to(root)}）")
            lines.append("")
            for kind, no, t in pick_ranked(sentences(e.draft), args.per_episode):
                lines.append(f"- [ ] {kind} L{no}: 「{t}」")
            lines.append("")
    lines += ["## 2. 展開の検索（あらすじ・設定の組み合わせ）", "",
              "要約から、主人公の立場・目的・障害・結末の組み合わせを 3〜5 語の検索語にする（例: `盲目 花火師 弟子 小説`）。", ""]
    for ch in chapters:
        p = ch.dir / "summaries.md"
        if p.exists():
            for m in re.finditer(r"^## (" + nk.EPISODE_RE + r")" + nk.EP_END + r"(.*?)\n(.*?)(?=^## |\Z)",
                                 p.read_text(encoding="utf-8"), re.M | re.S):
                lines.append(f"- {m.group(1)}{m.group(2)}: {m.group(3).strip()}")
    lines.append("")
    canon = nk.load_canon(root, cfg)
    names = [c.name for c in canon if c.type == "character"]
    places = [c.name for c in canon if c.type == "place"]
    lines += ["## 3. 題名・固有名詞の検索", "",
              f"- 作品の題: 「{cfg.get('title') or ''}」（同じ題・よく似た題の作品。話の題は、固有の言い回しのものだけを検索する）",
              f"- 主要人物の名前の組み合わせ: {'、'.join(names) or '（正典に人物がない）'}",
              f"- 舞台: {'、'.join(places) or '（正典に場所がない）'}", ""]
    text = "\n".join(lines)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"PHRASES: {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
