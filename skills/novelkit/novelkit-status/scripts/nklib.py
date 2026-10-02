#!/usr/bin/env python3
"""nklib.py - novelkit の共通ライブラリ（novelkit.py と check.py が使う）

作品のディレクトリ構成（.novelkit/config.yaml）、章と話の掲載順（chapters/<NN-slug>/scenes.md）、
正典の項目（canon/**/*.md のフロントマター）、本文（draft/<NN>/*.md）を読み込む。
macOS / Linux / Windows で動くように、標準ライブラリだけで書く（Python 3.9 以上）。
YAML はフロントマターと config.yaml に必要な範囲（入れ子の辞書、ブロックとインラインのリスト、スカラー）だけを解釈する。
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_REL = ".novelkit/config.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "title": "",
    "paths": {
        "concept": "docs/concept",
        "research": "docs/research",
        "plot": "docs/plot",
        "canon": "canon",
        "chapters": "chapters",
        "draft": "draft",
        "publish": "publish",
        "handover": "handover",
        "constitution": ".novelkit/memory/constitution.md",
    },
    "episode": {"target_min": 3000, "target_max": 6000, "tolerance": 0.2, "soft_margin": 0.1},
    "prose": {
        "long_sentence": 120,
        "same_ending_run": 6,
        "scene_break_max": 12,
        "kosoado_per_1000": 20,
        "max_findings_per_file": 20,
        "banned": [],
    },
    "session": {
        "web_search_limit": 200,   # 1 セッションの Web 検索の上限（Claude Code で観測した値。公式の記載はない）
        "reserve": 10,             # 見積もりの外に残しておく余裕
        "estimates": {"W2": 80, "W5": 100, "C7": 40, "chapter": 50},
        "stop_after_work": True,   # 作品の工程（W10）の後は、必ずセッションを区切る
        "chapters_unmetered": 1,   # 回数を数えられない環境で、1 セッションに進める章の数
    },
    "context": {
        "full_text_prev": 2,
        "summary_limit": 0,
        "always_files": ["canon/README.md", "canon/rules.md", "canon/glossary.md", "docs/research/anachronism.md"],
    },
}


# ---------------------------------------------------------------- mini YAML

class YamlError(Exception):
    pass


def _strip_comment(line: str) -> str:
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(text: str) -> Any:
    t = text.strip()
    if t == "":
        return None
    if (t[0] == t[-1]) and t[0] in ("'", '"') and len(t) >= 2:
        return t[1:-1]
    if t.startswith("[") and t.endswith("]"):
        inner = t[1:-1].strip()
        if not inner:
            return []
        return [_scalar(p) for p in _split_inline(inner)]
    if t in ("true", "True", "yes"):
        return True
    if t in ("false", "False", "no"):
        return False
    if t in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", t) and not (len(t) > 1 and t.lstrip("-").startswith("0")):
        return int(t)
    if re.fullmatch(r"-?\d+\.\d+", t):
        return float(t)
    return t


def _split_inline(inner: str) -> list[str]:
    parts, buf, quote = [], [], None
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            buf.append(ch)
        elif ch in (",", "、"):
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def parse_yaml(text: str) -> Any:
    lines = []
    for raw in text.splitlines():
        line = _strip_comment(raw.replace("\t", "  "))
        if line.strip():
            lines.append((len(line) - len(line.lstrip(" ")), line.strip()))
    if not lines:
        return {}
    value, pos = _parse_block(lines, 0, lines[0][0])
    if pos != len(lines):
        raise YamlError(f"解釈できない行があります: {lines[pos][1]}")
    return value


def _parse_block(lines, pos, indent):
    if lines[pos][1].startswith("- ") or lines[pos][1] == "-":
        result: list[Any] = []
        while pos < len(lines) and lines[pos][0] == indent and (lines[pos][1].startswith("- ") or lines[pos][1] == "-"):
            item = lines[pos][1][1:].strip()
            pos += 1
            if item == "":
                if pos < len(lines) and lines[pos][0] > indent:
                    val, pos = _parse_block(lines, pos, lines[pos][0])
                    result.append(val)
                else:
                    result.append(None)
            elif re.match(r"^[^\[\]{}\"']+?:(\s|$)", item) and not item.startswith("["):
                # "- key: value" 形式の辞書の要素
                sub = [(indent + 2, item)]
                while pos < len(lines) and lines[pos][0] > indent:
                    sub.append(lines[pos])
                    pos += 1
                val, _ = _parse_block(sub, 0, indent + 2)
                result.append(val)
            else:
                result.append(_scalar(item))
        return result, pos
    result_d: dict[str, Any] = {}
    while pos < len(lines) and lines[pos][0] == indent:
        text = lines[pos][1]
        m = re.match(r"^(.+?):(\s+(.*))?$", text)
        if not m:
            raise YamlError(f"「キー: 値」の形ではありません: {text}")
        key, rest = m.group(1).strip().strip("'\""), (m.group(3) or "").strip()
        pos += 1
        if rest == "" and pos < len(lines) and lines[pos][0] > indent:
            val, pos = _parse_block(lines, pos, lines[pos][0])
        elif rest == "" and pos < len(lines) and lines[pos][0] == indent and lines[pos][1].startswith("- "):
            val, pos = _parse_block(lines, pos, indent)
        else:
            val = _scalar(rest)
        result_d[key] = val
    return result_d, pos


FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(\n|\Z)", re.DOTALL)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str, int]:
    """(フロントマター, 本文, 本文の開始行番号(1 始まり)) を返す。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text, 1
    try:
        meta = parse_yaml(m.group(1))
    except YamlError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    body_start = text[: m.end()].count("\n") + 1
    return meta, text[m.end():], body_start


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [p for p in _split_inline(str(value))]


# ---------------------------------------------------------------- 作品

def find_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / CONFIG_REL).exists():
            return p
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return p
    return cur


def load_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_REL
    if not path.exists():
        return deep_merge(DEFAULT_CONFIG, {})
    return deep_merge(DEFAULT_CONFIG, parse_yaml(path.read_text(encoding="utf-8")) or {})


def pth(root: Path, cfg: dict, key: str) -> Path:
    return root / cfg["paths"][key]


# 話番号: <章番号>-<本章の番号|P|E|i<n>>（例: 4-03、4-P、4-i1、4-E）
EPISODE_RE = r"[0-9]+-(?:[0-9]+|P|E|i[0-9]+)"
EP_END = r"(?![0-9A-Za-z])"  # 話番号の直後（「## 4-03当番」のように空白がなくても区切る）
TASK_RE = re.compile(
    r"^- \[(?P<done>[ xX])\] (?P<tid>T[0-9]+)(?P<flags>(?: \[P\]| \[人\]| ★)*) "
    r"\[(?P<ep>" + EPISODE_RE + r")\](?P<refs>(?: ?\[[A-Z]+-[0-9]+\])*) ?(?P<title>.*)$"
)
SUB_RE = re.compile(r"^\s{2,}- (?P<key>[^:：]+)[:：]\s*(?P<val>.*)$")
CHAPTER_DIR_RE = re.compile(r"^(?P<num>[0-9]{2,3})(?:-(?P<slug>.+))?$")


@dataclass
class Episode:
    ep: str
    chapter: str  # 章ディレクトリ名（例: 04-bow-and-partner）
    chapter_num: int
    index: int = 0  # 作品全体の掲載順（0 始まり）
    task_id: str = ""
    done: bool = False
    parallel: bool = False
    human: bool = False
    star: bool = False
    refs: list[str] = field(default_factory=list)
    title: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    line: int = 0
    block: str = ""
    draft: Path | None = None
    fix: bool = False  # 「## 収束」の節のタスク（話ではなく、既存の話を直すタスク）


@dataclass
class Chapter:
    name: str
    num: int
    dir: Path
    episodes: list[Episode] = field(default_factory=list)
    fixes: list[Episode] = field(default_factory=list)
    bad_lines: list[tuple[int, str]] = field(default_factory=list)  # 「- [」で始まるのに読めない行


def list_chapters(root: Path, cfg: dict) -> list[Chapter]:
    base = pth(root, cfg, "chapters")
    chapters = []
    if base.is_dir():
        for d in sorted(base.iterdir()):
            m = CHAPTER_DIR_RE.match(d.name)
            if d.is_dir() and m:
                chapters.append(Chapter(name=d.name, num=int(m.group("num")), dir=d))
    chapters.sort(key=lambda c: c.num)
    return chapters


def match_chapter(chapters: list[Chapter], query: str) -> list[Chapter]:
    """番号（完全一致）・ディレクトリ名（完全一致）・名前の一部（一意なら）で章を探す。"""
    q = str(query).strip()
    exact = [c for c in chapters if c.name == q]
    if exact:
        return exact
    if re.fullmatch(r"[0-9]+", q):
        return [c for c in chapters if c.num == int(q)]
    return [c for c in chapters if q in c.name]


def parse_scenes(path: Path, chapter: Chapter) -> list[Episode]:
    """シーン台帳を読む。「- [」で始まるのに書式に合わない行は chapter.bad_lines に入れる。"""
    if not path.exists():
        return []
    episodes: list[Episode] = []
    cur: Episode | None = None
    block: list[str] = []
    in_fix = False
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            in_fix = "収束" in line
        m = TASK_RE.match(line)
        if not m and re.match(r"^- \[[ xX]\]", line):
            chapter.bad_lines.append((no, line))
        if m:
            if cur:
                cur.block = "\n".join(block)
            flags = m.group("flags")
            cur = Episode(
                ep=m.group("ep"), chapter=chapter.name, chapter_num=chapter.num,
                task_id=m.group("tid"), done=m.group("done") != " ",
                parallel="[P]" in flags, human="[人]" in flags, star="★" in flags,
                refs=re.findall(r"\[([A-Z]+-[0-9]+)\]", m.group("refs")),
                title=m.group("title").strip(), line=no, fix=in_fix,
            )
            block = [line]
            episodes.append(cur)
            continue
        if cur is not None:
            s = SUB_RE.match(line)
            if s:
                cur.fields[s.group("key").strip()] = s.group("val").strip()
                block.append(line)
            elif line.strip() == "" or line.startswith("#") or line.startswith("- ["):
                cur.block = "\n".join(block)
                cur = None
                block = []
            else:
                block.append(line)
    if cur:
        cur.block = "\n".join(block)
    return episodes


def find_draft(root: Path, cfg: dict, ep: Episode) -> Path | None:
    out = ep.fields.get("出力")
    if out:
        p = root / out.split()[0]
        if p.exists():
            return p
    ddir = pth(root, cfg, "draft")
    for sub in (f"{ep.chapter_num:02d}", str(ep.chapter_num), ep.chapter):
        d = ddir / sub
        if d.is_dir():
            hits = sorted(d.glob(f"{ep.ep}-*.md")) + sorted(d.glob(f"{ep.ep}.md"))
            if hits:
                return hits[0]
    return None


def load_work(root: Path, cfg: dict) -> tuple[list[Chapter], list[Episode]]:
    chapters = list_chapters(root, cfg)
    all_eps: list[Episode] = []
    for ch in chapters:
        parsed = parse_scenes(ch.dir / "scenes.md", ch)
        ch.episodes = [e for e in parsed if not e.fix]
        ch.fixes = [e for e in parsed if e.fix]
        for ep in ch.episodes:
            ep.draft = find_draft(root, cfg, ep)
            ep.index = len(all_eps)
            all_eps.append(ep)
    return chapters, all_eps


def orphan_drafts(root: Path, cfg: dict, episodes: list[Episode]) -> list[Path]:
    """シーン台帳にない本文ファイル（既存作品の取り込み時など）。"""
    known = {e.draft.resolve() for e in episodes if e.draft}
    ddir = pth(root, cfg, "draft")
    if not ddir.is_dir():
        return []
    return [p for p in sorted(ddir.rglob("*.md")) if p.resolve() not in known and not p.name.startswith("_")]


# ---------------------------------------------------------------- 正典

CANON_TYPES = {"character", "place", "org", "item", "term", "rule", "culture", "other"}


@dataclass
class CanonEntry:
    path: Path
    name: str
    type: str
    aliases: list[str]
    ai: str  # always | mention | never
    reveal_from: str | None
    hidden_names: list[str]
    born: int | None
    meta: dict[str, Any]
    body: str

    @property
    def names(self) -> list[str]:
        return [self.name, *self.aliases]


def load_canon(root: Path, cfg: dict) -> list[CanonEntry]:
    base = pth(root, cfg, "canon")
    entries: list[CanonEntry] = []
    if not base.is_dir():
        return entries
    for p in sorted(base.rglob("*.md")):
        if p.name.startswith("_") or p.name.upper() == "README.MD":
            continue
        meta, body, _ = split_frontmatter(p.read_text(encoding="utf-8"))
        if not meta or "type" not in meta:
            continue
        name = str(meta.get("name") or p.stem)
        reveal = meta.get("reveal_from")
        hidden = [str(x) for x in as_list(meta.get("hidden_names"))]
        if reveal and not hidden:
            hidden = [name]
        born = meta.get("born")
        entries.append(CanonEntry(
            path=p, name=name, type=str(meta.get("type")),
            aliases=[str(x) for x in as_list(meta.get("aliases"))],
            ai=str(meta.get("ai") or "mention"),
            reveal_from=str(reveal) if reveal else None,
            hidden_names=hidden,
            born=born if isinstance(born, int) else None,
            meta=meta, body=body,
        ))
    return entries


# ---------------------------------------------------------------- 表（Markdown）

def read_table(path: Path, require: str | None = None) -> list[dict[str, str]]:
    """Markdown の表を辞書の列にする（見出し行をキーにする）。行番号は "_line" に入れる。

    require を指定すると、その列を見出しに持つ最初の表を読む（説明用の表を読み飛ばすため）。
    指定しなければ、最初の表を読む。
    """
    if not path.exists():
        return []
    tables: list[tuple[list[str], list[dict[str, str]]]] = []
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            if header is not None:
                tables.append((header, rows))
            header, rows = None, []
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            header = [re.sub(r"\*", "", c) for c in cells]
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        row = {header[i]: (cells[i] if i < len(cells) else "") for i in range(len(header))}
        row["_line"] = str(no)
        rows.append(row)
    if header is not None:
        tables.append((header, rows))
    for hdr, rws in tables:
        if require is None or require in hdr:
            return rws
    return []


# ---------------------------------------------------------------- 本文

RUBY_RE = re.compile(r"[|｜]([^《|｜]+)《[^》]*》")
RUBY_SIMPLE_RE = re.compile(r"《[^》]*》")


def body_lines(path: Path) -> list[tuple[int, str]]:
    """フロントマター・見出し・HTML コメントを除いた本文の行（行番号つき）。ルビの読みは除く。"""
    text = path.read_text(encoding="utf-8")
    _, body, start = split_frontmatter(text)
    body = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), body, flags=re.DOTALL)
    out = []
    for i, line in enumerate(body.splitlines()):
        if line.lstrip().startswith("#"):
            continue
        line = RUBY_RE.sub(r"\1", line)
        line = RUBY_SIMPLE_RE.sub("", line)
        out.append((start + i, line))
    return out


def count_chars(path: Path) -> int:
    return sum(len(re.sub(r"\s", "", line)) for _, line in body_lines(path))


def draft_meta(path: Path) -> dict[str, Any]:
    meta, _, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    return meta


# ---------------------------------------------------------------- 話番号の比較

REVEAL_CHAPTER_RE = re.compile(r"^\s*(?:第\s*)?([0-9]+)\s*章?\s*$")


def reveal_state(reveal_from: str | None, epmap: dict[str, int]) -> tuple[str, int | None, int | None]:
    """reveal_from を解釈する。(種類, 話の掲載順, 章番号) を返す。

    - "episode": 台帳にある話番号（例: 3-05）
    - "chapter": 章の指定（例: 第3章、3）。その章の最初の話から明かす
    - "pending": 話番号の形だが、まだ台帳にない（その章の台帳ができるまでは、章の単位で伏せる）
    - "none": 指定なし、または解釈できない
    """
    if not reveal_from:
        return "none", None, None
    r = str(reveal_from).strip()
    m = re.fullmatch(EPISODE_RE, r)
    if m:
        ch = int(r.split("-")[0])
        return ("episode", epmap[r], ch) if r in epmap else ("pending", None, ch)
    m = REVEAL_CHAPTER_RE.match(r)
    if m:
        return "chapter", None, int(m.group(1))
    return "none", None, None


def before_reveal(ep: "Episode", reveal_from: str | None, epmap: dict[str, int]) -> bool:
    """その話が、開示の前（伏せるべき話）かどうか。"""
    kind, idx, ch = reveal_state(reveal_from, epmap)
    if kind == "episode":
        return ep.index < idx
    if kind in ("chapter", "pending"):
        return ep.chapter_num < ch
    return False


def episode_index_map(episodes: list[Episode]) -> dict[str, int]:
    return {e.ep: e.index for e in episodes}


def ep_index(epmap: dict[str, int], ep: str | None) -> int | None:
    if not ep:
        return None
    m = re.search(EPISODE_RE, str(ep))
    return epmap.get(m.group(0)) if m else None


# ---------------------------------------------------------------- git

def git(root: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} が失敗しました: {proc.stderr.strip()}")
    return proc


def is_git_repo(root: Path) -> bool:
    return git(root, ["rev-parse", "--is-inside-work-tree"], check=False).returncode == 0


def leading_int(text: str | None) -> int | None:
    """「9」「-3」「９年春」「九歳」のような文字列の先頭の整数を返す。なければ None。"""
    if not text:
        return None
    m = re.match(r"\s*([-−－]?)([0-9０-９〇一二三四五六七八九十百]+)", str(text))
    if not m:
        return None
    n = kanji_to_int(m.group(2))
    if n is None:
        return None
    return -n if m.group(1) else n


KANJI_NUM = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def kanji_to_int(s: str) -> int | None:
    """「十五」「二十三」「百」などの簡単な漢数字と、全角・半角の算用数字を整数にする。"""
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if s.isdigit():
        return int(s)
    total, cur = 0, 0
    for ch in s:
        if ch in KANJI_NUM:
            cur = cur * 10 + KANJI_NUM[ch]  # 「二〇」のような位取りの書き方も読む
        elif ch == "十":
            total += (cur or 1) * 10
            cur = 0
        elif ch == "百":
            total += (cur or 1) * 100
            cur = 0
        else:
            return None
    return total + cur
