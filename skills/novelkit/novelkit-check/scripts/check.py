#!/usr/bin/env python3
"""check.py - novelkit の機械検証（speckit の validate.py に当たる）

作品の成果物（シーン台帳・章仕様・正典・伏線台帳・筋の台帳・本文）を読み、機械で判定できる不整合を報告する。
ERROR が 1 件でもあれば終了コード 1 を返す。WARN は内容を確かめ、意図どおりなら報告に書けばよい。
macOS / Linux / Windows で動くように、標準ライブラリだけで書く（Python 3.9 以上）。

使い方:
  check.py [--root <作品>] [--only structure,canon,reveal,promises,threads,length,prose,glossary]
           [--chapter <章>] [--episode <話番号>] [--draft-dir <dir>] [--metrics]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "novelkit-status" / "scripts"))
import nklib as nk  # noqa: E402

CATEGORIES = ["structure", "canon", "reveal", "promises", "threads", "length", "prose", "glossary"]
SPEC_ID_RE = re.compile(r"(?<![A-Za-z])(RX|EV|IR|CH|SC)-[0-9]{3}(?![0-9])")
# 章仕様で ID を定義している行（「- EV-001: …」「### RX-001（P1）: …」）。本文中の参照や「上流からの変更」は数えない
SPEC_DEF_RE = re.compile(r"^\s*(?:[-*]|#{2,4})\s*\**\s*((?:RX|EV|IR|CH|SC)-[0-9]{3})(?![0-9])", re.M)
PLOT_ID_RE = re.compile(r"(?<![A-Za-z])[A-Z]{1,3}-[0-9]{2,3}(?![0-9])")
REQUIRED_FIELDS = ["視点", "変わること", "引き"]
KOSOADO_RE = re.compile(r"この|その|あの|これ|それ|あれ|ここ|そこ|あそこ")
KANJI_RE = re.compile(r"[一-鿿々]")
SENT_END_RE = re.compile(r"(?<=[。！？!?])")
# 記号だけの行（場面区切りの「＊」「◇」「――」など）
BREAK_LINE_RE = re.compile(r"^[\s　]*[＊*◇◆□■○●☆★※・―—\-]+[\s　]*$")


class Report:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.items: list[tuple[str, str, str, str]] = []

    def add(self, level: str, cat: str, where: str, msg: str) -> None:
        self.items.append((level, cat, where, msg))

    def loc(self, path: Path | None, line: int | str | None = None) -> str:
        if path is None:
            return "-"
        try:
            rel = path.resolve().relative_to(self.root)
        except ValueError:
            rel = path
        return f"{rel}:{line}" if line else str(rel)

    def dump(self) -> int:
        order = {"ERROR": 0, "WARN": 1, "INFO": 2}
        for level, cat, where, msg in sorted(self.items, key=lambda x: (order[x[0]], x[1], x[2])):
            print(f"{level:5} [{cat}] {where} {msg}")
        e = sum(1 for i in self.items if i[0] == "ERROR")
        w = sum(1 for i in self.items if i[0] == "WARN")
        print(f"\n結果: ERROR {e} 件 / WARN {w} 件")
        return 1 if e else 0


# ---------------------------------------------------------------- structure

def scenes_path(root: Path, cfg: dict, e) -> Path:
    return nk.pth(root, cfg, "chapters") / e.chapter / "scenes.md"


def spec_sections(text: str) -> str:
    """章仕様から「上流からの変更」と「Clarifications」の節を除いた本文。"""
    return re.sub(r"^## (上流からの変更|Clarifications).*?(?=^## |\Z)", "", text, flags=re.M | re.S)


def check_structure(rep: Report, root: Path, cfg: dict, chapters, episodes, scope) -> None:
    seen_ep: dict[str, str] = {}
    first_seen = {}
    for e in episodes:
        first_seen.setdefault(e.ep, f"{e.chapter}:{e.line}")
    for ch in chapters:
        if scope is not None and ch.name not in scope:
            continue
        spec = ch.dir / "spec.md"
        scenes = ch.dir / "scenes.md"
        if not spec.exists():
            rep.add("WARN", "structure", rep.loc(ch.dir), "章仕様 spec.md がない（novelkit-plot）")
        if not scenes.exists():
            if spec.exists():
                rep.add("INFO", "structure", rep.loc(ch.dir), "シーン台帳 scenes.md がまだない（novelkit-outline）")
            continue
        for no, line in ch.bad_lines:
            rep.add("WARN", "structure", rep.loc(scenes, no),
                    f"タスクの行として読めない（書式: - [ ] T001 [4-01] [EV-001] 題）: {line[:40]}")
        tids: dict[str, int] = {}
        for e in ch.episodes:
            if e.task_id in tids:
                rep.add("ERROR", "structure", rep.loc(scenes, e.line), f"タスク ID {e.task_id} が重複（{tids[e.task_id]} 行目）")
            tids[e.task_id] = e.line
            if e.ep in seen_ep or first_seen.get(e.ep) != f"{e.chapter}:{e.line}":
                rep.add("ERROR", "structure", rep.loc(scenes, e.line), f"話番号 {e.ep} が重複（{first_seen.get(e.ep)}）")
            seen_ep[e.ep] = f"{ch.name}:{e.line}"
            if int(e.ep.split("-")[0]) != ch.num:
                rep.add("ERROR", "structure", rep.loc(scenes, e.line), f"話番号 {e.ep} の章番号が章 {ch.name} と一致しない")
            for f in REQUIRED_FIELDS:
                if not e.fields.get(f, "").strip():
                    rep.add("WARN", "structure", rep.loc(scenes, e.line), f"{e.ep} の「{f}」が空")
            if e.done and not e.draft:
                rep.add("ERROR", "structure", rep.loc(scenes, e.line), f"{e.ep} は完了 [x] だが本文ファイルがない")
            if not e.done and e.draft and not e.human:
                rep.add("WARN", "structure", rep.loc(scenes, e.line), f"{e.ep} は本文があるが未完了 [ ] のまま（{rep.loc(e.draft)}）")
        for f in ch.fixes:
            if not f.done:
                rep.add("WARN", "structure", rep.loc(scenes, f.line), f"収束タスク {f.task_id}（{f.ep}）が未完了")
        if spec.exists():
            spec_ids = set(SPEC_DEF_RE.findall(spec_sections(spec.read_text(encoding="utf-8"))))
            used = set(r for e in ch.episodes for r in e.refs)
            for e in ch.episodes:
                for r in e.refs:
                    if SPEC_ID_RE.fullmatch(r) and r not in spec_ids:
                        rep.add("ERROR", "structure", rep.loc(scenes, e.line), f"{e.ep} の参照 {r} が spec.md にない")
            for sid in sorted(spec_ids):
                if sid in used:
                    continue
                if sid.startswith("EV-"):
                    rep.add("ERROR", "structure", rep.loc(spec), f"必須イベント {sid} を担う話がシーン台帳にない")
                elif sid.startswith(("IR-", "CH-")):
                    rep.add("WARN", "structure", rep.loc(spec), f"{sid} を担う話がシーン台帳にない")


# ---------------------------------------------------------------- canon

AGE_FIELD_RE = re.compile(r"([^\s,、，:：0-9０-９]+)\s*([0-9０-９〇一二三四五六七八九十]+)")


def age_text_re(names: list[str]) -> re.Pattern | None:
    """正典の名前・別名のどれかの直後に「（N歳）」「(N歳)」が続く形。"""
    names = sorted({n for n in names if n}, key=len, reverse=True)
    if not names:
        return None
    alt = "|".join(re.escape(n) for n in names)
    return re.compile(r"(?P<name>" + alt + r")\s*[（(](?P<age>[0-9０-９〇一二三四五六七八九十]+)\s*歳[）)]")


def check_canon(rep: Report, root: Path, cfg: dict, chapters, episodes, canon, scope_eps) -> None:
    epmap = nk.episode_index_map(episodes)
    chapters_with_eps = {e.chapter_num for e in episodes}
    if scope_eps is None:
        names: dict[str, Path] = {}
        for c in canon:
            if c.type not in nk.CANON_TYPES:
                rep.add("ERROR", "canon", rep.loc(c.path), f"type が不正: {c.type}（{', '.join(sorted(nk.CANON_TYPES))}）")
            if c.ai not in ("always", "mention", "never"):
                rep.add("ERROR", "canon", rep.loc(c.path), f"ai が不正: {c.ai}（always / mention / never）")
            for n in c.names:
                if n in names and names[n] != c.path:
                    rep.add("WARN", "canon", rep.loc(c.path), f"名前・別名「{n}」が {rep.loc(names[n])} と重複")
                names[n] = c.path
            kind, _, ch = nk.reveal_state(c.reveal_from, epmap)
            if c.reveal_from and kind == "none":
                rep.add("ERROR", "canon", rep.loc(c.path), f"reveal_from の形が読めない: {c.reveal_from}（話番号 3-05 か、第3章）")
            elif kind == "pending" and ch in chapters_with_eps:
                rep.add("ERROR", "canon", rep.loc(c.path), f"reveal_from {c.reveal_from} が第{ch}章のシーン台帳にない")
            elif kind == "pending":
                rep.add("INFO", "canon", rep.loc(c.path),
                        f"reveal_from {c.reveal_from} の章の台帳はまだない。それまでは第{ch}章より前の話で伏せる")
    by_name = {n: c for c in canon for n in c.names if c.born is not None}
    text_re = age_text_re(list(by_name))
    for e in episodes:
        if scope_eps is not None and e.ep not in scope_eps:
            continue
        year = (e.fields.get("作中年") or "").strip()
        if not year:
            continue
        y = nk.leading_int(year)
        if y is None:
            rep.add("ERROR", "canon", rep.loc(scenes_path(root, cfg, e), e.line), f"{e.ep} の作中年が整数でない: {year}（季節は柱に書く）")
            continue
        for name, age in AGE_FIELD_RE.findall(e.fields.get("年齢", "")):
            c = by_name.get(name.strip())
            a = nk.leading_int(age)
            if not c or a is None:
                continue
            expect = y - c.born
            if a not in (expect, expect - 1):
                rep.add("ERROR", "canon", rep.loc(scenes_path(root, cfg, e), e.line),
                        f"{e.ep} の {name} の年齢 {a} が正典と合わない（作中年 {y} − 生年 {c.born} = {expect}、誕生日前なら {expect - 1}）")
        if e.draft and text_re:
            for no, line in nk.body_lines(e.draft):
                for m in text_re.finditer(line):
                    c = by_name[m.group("name")]
                    a = nk.leading_int(m.group("age"))
                    if a is not None and a not in (y - c.born, y - c.born - 1):
                        rep.add("WARN", "canon", rep.loc(e.draft, no),
                                f"{m.group(0)} は正典の年齢（{y - c.born} か {y - c.born - 1}）と合わない")


# ---------------------------------------------------------------- reveal

def check_reveal(rep: Report, root: Path, cfg: dict, episodes, canon, scope_eps) -> None:
    epmap = nk.episode_index_map(episodes)
    for c in canon:
        if not c.hidden_names or not c.reveal_from:
            continue
        for e in episodes:
            if not e.draft or (scope_eps is not None and e.ep not in scope_eps):
                continue
            if not nk.before_reveal(e, c.reveal_from, epmap):
                continue
            for no, line in nk.body_lines(e.draft):
                for hn in c.hidden_names:
                    if hn and hn in line:
                        rep.add("ERROR", "reveal", rep.loc(e.draft, no),
                                f"「{hn}」は {c.reveal_from} まで伏せる予定（{rep.loc(c.path)}）")


# ---------------------------------------------------------------- promises / threads

def check_promises(rep: Report, root: Path, cfg: dict, episodes, scope_eps) -> None:
    path = nk.pth(root, cfg, "plot") / "promises.md"
    rows = nk.read_table(path, require="ID")
    epmap = nk.episode_index_map(episodes)
    chapters_with_eps = {e.chapter_num for e in episodes}
    ids = {r.get("ID", "").strip(): r for r in rows if r.get("ID", "").strip()}
    if scope_eps is None:
        last_drafted = max((e.index for e in episodes if e.draft), default=-1)
        seen = set()
        for r in rows:
            pid = r.get("ID", "").strip()
            if not pid:
                continue
            if pid in seen:
                rep.add("ERROR", "promises", rep.loc(path, r["_line"]), f"ID {pid} が重複")
            seen.add(pid)
            state = r.get("状態", "")
            for col in ("張る", "進展", "回収予定", "回収"):
                for ep in re.findall(nk.EPISODE_RE, r.get(col, "")):
                    if ep not in epmap and int(ep.split("-")[0]) in chapters_with_eps:
                        rep.add("WARN", "promises", rep.loc(path, r["_line"]), f"{pid} の{col} {ep} がシーン台帳にない")
            due = nk.ep_index(epmap, r.get("回収予定"))
            if "回収済" not in state and "破棄" not in state and due is not None and due <= last_drafted:
                rep.add("WARN", "promises", rep.loc(path, r["_line"]), f"{pid} は回収予定 {r.get('回収予定')} を過ぎたが未回収（状態: {state or '空'}）")
            if r.get("回収", "").strip() and "回収済" not in state:
                rep.add("WARN", "promises", rep.loc(path, r["_line"]), f"{pid} は回収の話があるのに状態が回収済でない")
    for e in episodes:
        if scope_eps is not None and e.ep not in scope_eps:
            continue
        for key in ("伏線", "約束"):
            for pid in PLOT_ID_RE.findall(e.fields.get(key, "")):
                if pid not in ids:
                    rep.add("ERROR", "promises", rep.loc(scenes_path(root, cfg, e), e.line), f"{e.ep} の{key} {pid} が promises.md にない")


def check_threads(rep: Report, root: Path, cfg: dict, episodes, scope_eps) -> None:
    path = nk.pth(root, cfg, "plot") / "threads.md"
    rows = nk.read_table(path, require="ID")
    epmap = nk.episode_index_map(episodes)
    ids = {r.get("ID", "").strip() for r in rows if r.get("ID", "").strip()}
    for e in episodes:
        if scope_eps is not None and e.ep not in scope_eps:
            continue
        for tid in PLOT_ID_RE.findall(e.fields.get("筋", "")):
            if tid not in ids:
                rep.add("ERROR", "threads", rep.loc(scenes_path(root, cfg, e), e.line), f"{e.ep} の筋 {tid} が threads.md にない")
    if scope_eps is not None:
        return
    spans = []
    for r in rows:
        if not r.get("ID", "").strip():
            continue
        kind = r.get("種類", "").strip()[:1].upper()
        if kind not in ("M", "I", "C", "E"):
            rep.add("ERROR", "threads", rep.loc(path, r["_line"]), f"{r.get('ID')} の種類が M/I/C/E でない: {r.get('種類')}")
        o, c = nk.ep_index(epmap, r.get("開く")), nk.ep_index(epmap, r.get("閉じる"))
        if o is not None and c is not None:
            if c < o:
                rep.add("ERROR", "threads", rep.loc(path, r["_line"]), f"{r.get('ID')} は開く前に閉じている")
            if not r.get("意図", "").strip():
                spans.append((o, c, r))
    for i, (o1, c1, r1) in enumerate(spans):
        for o2, c2, r2 in spans[i + 1:]:
            if o1 < o2 < c1 < c2 or o2 < o1 < c2 < c1:
                inner, outer = (r2, r1) if o1 < o2 else (r1, r2)
                rep.add("WARN", "threads", rep.loc(path, inner["_line"]),
                        f"{inner.get('ID')} と {outer.get('ID')} の入れ子が交差（後に開いた筋は先に閉じる: MICE）")


# ---------------------------------------------------------------- length

def _length_finding(rep: Report, path: Path, n: int, lo: float, hi: float, soft: float, label: str) -> None:
    """範囲外なら WARN。範囲外でも soft（例: 0.1 = 10%）の幅に収まれば、満たしたとみなして INFO にする。"""
    if lo <= n <= hi:
        return
    if lo * (1 - soft) <= n <= hi * (1 + soft):
        rep.add("INFO", "length", rep.loc(path), f"{n:,} 字。{label}をわずかに外れる（±{int(soft * 100)}% の幅に収まるので満たしたとみなす）")
    else:
        rep.add("WARN", "length", rep.loc(path), f"{n:,} 字。{label}を外れている")


def check_length(rep: Report, root: Path, cfg: dict, episodes, orphans) -> None:
    """シーン台帳の「目安」（±tolerance）と、config の 1 話の範囲（文体の決まり）の両方で判定する。"""
    ep_cfg = cfg["episode"]
    tol = float(ep_cfg.get("tolerance", 0.2))
    soft = float(ep_cfg.get("soft_margin", 0.1))
    lo, hi = ep_cfg["target_min"], ep_cfg["target_max"]
    for e in episodes:
        if not e.draft:
            continue
        n = nk.count_chars(e.draft)
        m = re.search(r"([0-9,，]+)\s*字", e.fields.get("目安", ""))
        if m:
            t = int(re.sub(r"[,，]", "", m.group(1)))
            _length_finding(rep, e.draft, n, t * (1 - tol), t * (1 + tol), soft, f"目安 {t:,} 字 ±{int(tol * 100)}% ")
        _length_finding(rep, e.draft, n, lo, hi, soft, f"1 話の範囲 {lo:,}〜{hi:,} 字（config の episode、文体の決まり）")
    for p in orphans:
        _length_finding(rep, p, nk.count_chars(p), lo, hi, soft, f"1 話の範囲 {lo:,}〜{hi:,} 字")


# ---------------------------------------------------------------- prose

def narrative_sentences(lines, with_breaks: bool = False):
    """地の文の文（行番号, 文）。台詞の行（「『で始まる）は除く。

    with_breaks=True のときは、台詞の行と場面区切りの位置に (行番号, None) を挟む（文末の連続を数え直すため）。
    """
    for no, line in lines:
        s = line.strip().lstrip("　")
        if not s:
            continue
        if s[0] in "「『（(" or BREAK_LINE_RE.match(line):
            if with_breaks:
                yield no, None
            continue
        for sent in SENT_END_RE.split(s):
            sent = sent.strip()
            if sent:
                yield no, sent


def check_prose(rep: Report, root: Path, cfg: dict, paths: list[Path], metrics: bool) -> None:
    pc = cfg["prose"]
    cap = int(pc.get("max_findings_per_file", 20))
    run_limit = int(pc.get("same_ending_run", 4))
    long_limit = int(pc.get("long_sentence", 120))
    kosoado_limit = float(pc.get("kosoado_per_1000", 15))
    banned = [str(b) for b in nk.as_list(pc.get("banned"))]
    for p in paths:
        lines = nk.body_lines(p)
        found = 0

        def add(level, where, msg):
            nonlocal found
            if found < cap:
                rep.add(level, "prose", where, msg)
            found += 1

        text = "\n".join(l for _, l in lines)
        breaks = sum(1 for _, l in lines if BREAK_LINE_RE.match(l))
        break_max = int(pc.get("scene_break_max", 12))
        if breaks > break_max:
            add("WARN", rep.loc(p), f"場面区切りだけの行が {breaks} 行ある（上限 {break_max}。意図した書式なら prose.scene_break_max を上げる）")
        lines = [(no, l) for no, l in lines if not BREAK_LINE_RE.match(l)]
        # 括弧の対応
        for o, c in (("「", "」"), ("『", "』"), ("（", "）")):
            if text.count(o) != text.count(c):
                add("WARN", rep.loc(p), f"{o}{c} の数が合わない（{o} {text.count(o)} / {c} {text.count(c)}）")
        for no, line in lines:
            # 三点リーダとダッシュは 2 つ重ねる
            if re.search(r"(?<!…)…(?!…)", line):
                add("WARN", rep.loc(p, no), "三点リーダが 1 つだけ（「……」と 2 つ重ねる）")
            if re.search(r"(?<![―—])[―—](?![―—])", line) and not BREAK_LINE_RE.match(line):
                add("WARN", rep.loc(p, no), "ダッシュが 1 つだけ（「――」と 2 つ重ねる）")
            # 感嘆符・疑問符の後は全角空白（閉じ括弧・連続する符号の前を除く）
            if re.search(r"[！？!?](?=[^！？!?」』）)\s　])", line):
                add("WARN", rep.loc(p, no), "！？ の後に全角空白がない")
            for b in banned:
                if b and b in line:
                    add("WARN", rep.loc(p, no), f"禁止表現「{b}」")
        # 文末の連続
        sents = [(no, x) for no, x in narrative_sentences(lines)]
        run, prev_end, run_start = 0, None, None
        for no, s in narrative_sentences(lines, with_breaks=True):
            if s is None:  # 台詞や場面区切りを挟んだら数え直す
                if run >= run_limit:
                    add("WARN", rep.loc(p, run_start), f"地の文の文末「{prev_end}」が {run} 文続く")
                run, prev_end, run_start = 0, None, None
                continue
            end = re.sub(r"[」』）)]+$", "", s)[-2:]
            if end == prev_end:
                run += 1
            else:
                if run >= run_limit:
                    add("WARN", rep.loc(p, run_start), f"地の文の文末「{prev_end}」が {run} 文続く")
                run, prev_end, run_start = 1, end, no
            if len(s) > long_limit:
                add("WARN", rep.loc(p, no), f"長い文（{len(s)} 字 > {long_limit}）: {s[:30]}…")
        if run >= run_limit:
            add("WARN", rep.loc(p, run_start), f"地の文の文末「{prev_end}」が {run} 文続く")
        narr = "".join(s for _, s in sents)
        if narr:
            dens = len(KOSOADO_RE.findall(narr)) * 1000 / len(narr)
            if dens > kosoado_limit:
                add("WARN", rep.loc(p), f"指示語（こそあど）が多い: 1,000 字あたり {dens:.1f}（上限 {kosoado_limit}）")
        if found > cap:
            rep.add("INFO", "prose", rep.loc(p), f"ほか {found - cap} 件を省略（prose.max_findings_per_file）")
        if metrics:
            flat = re.sub(r"\s", "", text)
            dialogue = sum(len(m) for m in re.findall(r"「[^」]*」", flat))
            n = len(flat) or 1
            lens = [len(s) for _, s in sents] or [0]
            rep.add("INFO", "prose", rep.loc(p),
                    f"字数 {len(flat):,} / 台詞 {dialogue * 100 / n:.0f}% / 漢字 {len(KANJI_RE.findall(flat)) * 100 / n:.0f}% "
                    f"/ 地の文の平均文長 {sum(lens) / len(lens):.0f} 字")


# ---------------------------------------------------------------- glossary

def load_variants(root: Path, cfg: dict, canon) -> list[tuple[str, str, str]]:
    """(揺れ, 正表記, 出典) の一覧。canon/glossary.md の表と、正典の variants から作る。"""
    out = []
    gpath = nk.pth(root, cfg, "canon") / "glossary.md"
    for r in nk.read_table(gpath, require="正表記"):
        right = r.get("正表記", "").strip()
        for v in nk.as_list(r.get("揺れ", "")):
            v = v.strip().strip("`")
            if v and v != "—" and v != right:
                out.append((v, right, f"glossary.md:{r['_line']}"))
    for c in canon:
        for v in nk.as_list(c.meta.get("variants")):
            if str(v) != c.name:
                out.append((str(v), c.name, c.path.name))
    return out


def check_glossary(rep: Report, root: Path, cfg: dict, paths: list[Path], canon) -> None:
    variants = load_variants(root, cfg, canon)
    if not variants:
        return
    for p in paths:
        for no, line in nk.body_lines(p):
            for v, right, src in variants:
                # 揺れが正表記の一部なら（正「煙硝」・揺れ「硝」）、正表記を伏せてから探す。
                # 揺れが正表記を含む場合（正「薬」・揺れ「火薬」）は、そのまま探せば揺れだけが見つかる
                masked = line.replace(right, "\0" * len(right)) if right and v in right else line
                if v in masked:
                    rep.add("WARN", "glossary", rep.loc(p, no), f"表記の揺れ「{v}」→「{right}」（{src}）")


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description="novelkit の機械検証")
    ap.add_argument("--root")
    ap.add_argument("--only", help=",".join(CATEGORIES))
    ap.add_argument("--chapter", help="対象の章（番号か名前）。本文の検査をその章に絞る")
    ap.add_argument("--episode", help="対象の話番号。本文の検査をその話に絞る")
    ap.add_argument("--draft-dir", help="シーン台帳を使わず、このディレクトリの .md を本文として検査する（既存作品の取り込み用）")
    ap.add_argument("--metrics", action="store_true", help="本文ごとの指標（台詞・漢字の比率、平均文長）も出す")
    args = ap.parse_args()
    root = Path(args.root).resolve() if args.root else nk.find_root()
    cfg = nk.load_config(root)
    only = set((args.only or ",".join(CATEGORIES)).split(","))
    unknown = only - set(CATEGORIES)
    if unknown:
        print(f"不明な分類: {', '.join(sorted(unknown))}", file=sys.stderr)
        sys.exit(2)
    rep = Report(root)
    if args.draft_dir:
        chapters, episodes = [], []
        orphans = sorted(p for p in Path(args.draft_dir).resolve().rglob("*.md") if not p.name.startswith("_"))
        only &= {"length", "prose", "glossary", "canon"}
    else:
        chapters, episodes = nk.load_work(root, cfg)
        orphans = nk.orphan_drafts(root, cfg, episodes)
    canon = nk.load_canon(root, cfg)

    scope_eps = None
    if args.chapter:
        hits = nk.match_chapter(chapters, args.chapter)
        if len(hits) != 1:
            print(f"章を 1 つに決められません: {args.chapter}（候補: {', '.join(h.name for h in hits) or 'なし'}）", file=sys.stderr)
            sys.exit(2)
        scope_eps = {e.ep for e in hits[0].episodes}
        orphans = []
    if args.episode:
        scope_eps = {args.episode} if scope_eps is None else scope_eps & {args.episode}
        orphans = []
    scope_chapters = {e.chapter for e in episodes if e.ep in scope_eps} if scope_eps is not None else None
    if args.chapter and scope_chapters is not None and not scope_chapters:
        scope_chapters = {nk.match_chapter(chapters, args.chapter)[0].name}
    targets = [e for e in episodes if e.draft and (scope_eps is None or e.ep in scope_eps)]
    draft_paths = [e.draft for e in targets if e.draft] + orphans

    if "structure" in only and not args.draft_dir:
        check_structure(rep, root, cfg, chapters, episodes, scope_chapters)
    if "canon" in only:
        check_canon(rep, root, cfg, chapters, episodes, canon, scope_eps)
    if "reveal" in only:
        check_reveal(rep, root, cfg, episodes, canon, scope_eps)
    if "promises" in only and not args.draft_dir:
        check_promises(rep, root, cfg, episodes, scope_eps)
    if "threads" in only and not args.draft_dir:
        check_threads(rep, root, cfg, episodes, scope_eps)
    if scope_eps is not None:
        rep.add("INFO", "scope", "-", "範囲を絞ったため、作品全体に関わる検査（正典の定義、伏線・筋の台帳の全体）は省いた")
    if "length" in only:
        check_length(rep, root, cfg, targets, orphans)
    if "prose" in only:
        check_prose(rep, root, cfg, draft_paths, args.metrics)
    if "glossary" in only:
        check_glossary(rep, root, cfg, draft_paths, canon)
    if orphans and not args.draft_dir:
        rep.add("INFO", "structure", "-", f"シーン台帳にない本文が {len(orphans)} 本ある（字数・文章・表記だけを検査した）")
    sys.exit(rep.dump())


if __name__ == "__main__":
    main()
