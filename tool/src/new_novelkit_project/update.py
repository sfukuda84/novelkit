"""new-novelkit-project update: 作成済みの作品に、scaffold の新しい版（スキル、ルールなど）を取り込む。

判定の考え方（speckit の new-speckit-project update と同じ）:
  scaffold の持ち物（MANAGED_PREFIXES / MANAGED_FILES）の各ファイルについて、scaffold の全履歴に現れた版の
  ハッシュを集める。作品側のファイルがそのどれかと一致すれば「手で直していない」とみなして、
  新しい版で上書きする（scaffold から消えたファイルは削除する）。一致しなければ手で直したものとして触らず、
  scaffold の新しい版を .scaffold-new/ に置いて報告する。
  作品の成果物（設定、憲章、docs/ など）は対象外。
  スキルを scaffold へのリンクで置いた作品（--link）は、スキルがすでに最新なので、リンクの外だけを更新する。
  取り込み（--adopt）で残した同名のスキル（既存のディレクトリ）は触らない。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import cli

# scaffold の持ち物（作品にコピーするもの）
SKILL_SETS = ("novelkit",)
MANAGED_PREFIXES = (
    "skills/novelkit/",
    ".claude/skills/novelkit-",
    ".agents/skills/novelkit-",
    ".kiro/skills/novelkit-",
    ".kiro/steering/",
)
MANAGED_FILES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md")
PATH_MAP: dict = {}   # scaffold のパス -> 作品でのパス（置き場所が違うもの）
STATE_FILE = ".novelkit/scaffold.json"   # 取り込んだ scaffold の版
MAIN_BRANCH_ENV = "NOVELKIT_MAIN_BRANCH"
NEW_VERSIONS_DIR = ".scaffold-new"
AGENT_SKILL_DIRS = (".claude/skills", ".agents/skills", ".kiro/skills")


def to_project(path: str) -> str:
    """scaffold のパスを、作品でのパスにする。"""
    return PATH_MAP.get(path, path)


def is_managed(path: str) -> bool:
    return path in MANAGED_FILES or path in PATH_MAP or path.startswith(MANAGED_PREFIXES)


@dataclass
class Plan:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)      # 手で直されているので触らないもの
    kept_removed: list[str] = field(default_factory=list)  # scaffold から消えたが手で直されているので残すもの
    occupied: list[str] = field(default_factory=list)      # 同名の既存のもの（取り込みで残したスキルなど）
    linked: list[str] = field(default_factory=list)        # scaffold へのリンクなので更新不要のスキル
    gitignore_lines: list[str] = field(default_factory=list)

    def changes(self) -> int:
        return len(self.added) + len(self.updated) + len(self.deleted) + len(self.gitignore_lines)


def git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise cli.CliError(f"git {' '.join(args)} が失敗しました。\n{proc.stderr.strip()}")
    return proc.stdout


def tree_entries(repo: Path, rev: str) -> dict[str, tuple[str, str]]:
    """path -> (mode, blob)。"""
    entries = {}
    for record in git(["ls-tree", "-r", "-z", rev], repo).split("\0"):
        if not record:
            continue
        meta, path = record.split("\t", 1)
        mode, kind, blob = meta.split()
        if kind == "blob":
            entries[path] = (mode, blob)
    return entries


def known_versions(repo: Path) -> dict[str, set[str]]:
    """scaffold の全履歴で、各パス（作品でのパス）に現れた版のハッシュ。"""
    known: dict[str, set[str]] = {}
    for rev in git(["rev-list", "HEAD"], repo).split():
        for path, (_mode, blob) in tree_entries(repo, rev).items():
            if is_managed(path):
                known.setdefault(to_project(path), set()).add(blob)
    return known


def project_entries(project: Path) -> dict[str, tuple[str, str]]:
    """作品で Git が追跡しているファイルの path -> (mode, blob)（作業ツリーはクリーンである前提）。"""
    entries = {}
    for record in git(["ls-files", "-s", "-z"], project).split("\0"):
        if not record:
            continue
        meta, path = record.split("\t", 1)
        mode, blob, _stage = meta.split()
        entries[path] = (mode, blob)
    return entries


def linked_roots(project: Path) -> list[str]:
    """scaffold へのリンクで置いたスキルの集まり（skills/<名前>）。"""
    return [f"skills/{name}" for name in SKILL_SETS if (project / "skills" / name).is_symlink()]


def build_plan(project: Path, scaffold: Path) -> tuple[Plan, dict[str, tuple[str, str, str]]]:
    """計画と、作品でのパス -> (scaffold でのパス, mode, blob)。"""
    new = {to_project(p): (p, *e) for p, e in tree_entries(scaffold, "HEAD").items() if is_managed(p)}
    known = known_versions(scaffold)
    have = {p: e for p, e in project_entries(project).items() if is_managed(p) or p in PATH_MAP.values()}
    plan = Plan(linked=linked_roots(project))
    skip = tuple(root + "/" for root in plan.linked)

    for path, (_src, _mode, blob) in sorted(new.items()):
        if path.startswith(skip):
            continue
        target = project / path
        if path not in have:
            if target.exists() or target.is_symlink():
                plan.occupied.append(path)  # 追跡していない既存のもの、または同名のディレクトリ
            else:
                plan.added.append(path)
        elif have[path][1] == blob:
            continue
        elif have[path][1] in known.get(path, set()):
            plan.updated.append(path)
        else:
            plan.modified.append(path)
    for path, (_mode, blob) in sorted(have.items()):
        if path in new or path.startswith(skip) or path in plan.linked:
            continue
        if blob in known.get(path, set()):
            plan.deleted.append(path)
        elif path in known:
            plan.kept_removed.append(path)
        # scaffold に一度も現れていないファイルは、作品独自のものなので触らない

    current = set((project / ".gitignore").read_text(encoding="utf-8").splitlines()) \
        if (project / ".gitignore").is_file() else set()
    # 足すのは、このキットが動くのに要る行（scaffold の scripts/gitignore-required.txt）だけにする。
    # scaffold の .gitignore のほかの行（OS、エディタ、言語ごとの生成物など）は、プロジェクトの事情に任せる。
    required = scaffold / "scripts" / "gitignore-required.txt"
    wanted = [line.strip() for line in required.read_text(encoding="utf-8").splitlines()
              if line.strip() and not line.lstrip().startswith("#")] if required.is_file() else []
    if f"{NEW_VERSIONS_DIR}/" not in wanted:
        wanted.append(f"{NEW_VERSIONS_DIR}/")
    current = {line.strip() for line in current}
    plan.gitignore_lines = [line for line in wanted if line not in current]
    return plan, new


def write_blob(scaffold: Path, project: Path, path: str, src: str, mode: str, blob: str) -> None:
    target = project / path
    if target.is_symlink() or target.is_file():
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "120000":
        # Git はリンク先を / 区切りで記録する。Windows のディレクトリへのリンクは / 区切りだとたどれないので、OS の区切りに直す
        link = git(["cat-file", "-p", blob], scaffold).strip().replace("/", os.sep)
        try:
            os.symlink(link, target, target_is_directory=True)
            if not target.exists():  # 作れてもたどれないリンクは使わない
                target.unlink()
                raise OSError(f"{target} のリンク先をたどれない")
        except (OSError, NotImplementedError):
            shutil.copytree((target.parent / link).resolve(), target)
    else:
        shutil.copy2(scaffold / src, target)


def apply_plan(plan: Plan, project: Path, scaffold: Path, new: dict[str, tuple[str, str, str]]) -> None:
    # 実体（skills/）を先に更新し、リンクはその後に作る
    order = sorted(plan.added + plan.updated, key=lambda p: (not p.startswith("skills/"), p))
    for path in order:
        src, mode, blob = new[path]
        write_blob(scaffold, project, path, src, mode, blob)
    for path in plan.deleted:
        target = project / path
        if target.is_symlink() or target.is_file():
            target.unlink()
        parent = target.parent
        while parent != project and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    # 手で直されたファイルは触らず、scaffold の新しい版を .scaffold-new/ に置く
    for path in plan.modified:
        src, mode, blob = new[path]
        dest = project / NEW_VERSIONS_DIR / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if mode == "120000":
            dest.write_text(git(["cat-file", "-p", blob], scaffold), encoding="utf-8")
        else:
            shutil.copy2(scaffold / src, dest)
    if plan.gitignore_lines:
        gi = project / ".gitignore"
        text = gi.read_text(encoding="utf-8") if gi.is_file() else ""
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"\n# ===== {cli.KIT} の更新で追加 =====\n" + "\n".join(plan.gitignore_lines) + "\n"
        gi.write_text(text, encoding="utf-8")


def write_state(project: Path, repo: str, ref: str, sha: str) -> None:
    state = project / STATE_FILE
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"repo": repo, "ref": ref, "sha": sha}, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")


def check_project(project: Path) -> None:
    if not (project / "skills" / cli.KIT).exists() and not (project / "skills" / cli.KIT).is_symlink():
        raise cli.CliError(f"{project} は {cli.KIT} の作品ではないようです（skills/{cli.KIT}/ がない）。")
    top = Path(git(["rev-parse", "--show-toplevel"], project).strip()).resolve()
    if top != project:
        raise cli.CliError(f"作品のルート（{top}）を指定してください。")
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], project).strip()
    main = os.environ.get(MAIN_BRANCH_ENV) or "main"
    if branch != main:
        raise cli.CliError(f"{main} ブランチで実行してください（現在: {branch}。既定のブランチが別なら環境変数 {MAIN_BRANCH_ENV}）。")
    if git(["status", "--porcelain"], project).strip():
        raise cli.CliError("未コミットの変更があります。コミットまたは stash してから実行してください。")


def print_plan(plan: Plan) -> None:
    def section(title: str, items: list[str]) -> None:
        if items:
            cli.info(f"{title}（{len(items)}）:")
            for item in items:
                cli.info(f"  {item}")

    section("追加", plan.added)
    section("更新", plan.updated)
    section("削除", plan.deleted)
    section(".gitignore に足す行", plan.gitignore_lines)
    section(f"手で直されているので触らない（新しい版は {NEW_VERSIONS_DIR}/ に置く）", plan.modified)
    section("scaffold から消えたが、手で直されているので残す", plan.kept_removed)
    section("同名の既存のものがあるので触らない（取り込みで残したスキルなど）", plan.occupied)
    section("scaffold へのリンクなので更新しない（すでに最新）", plan.linked)


def build_update_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog=f"{cli.PROG} update",
        description=f"作成済みの作品に、{cli.KIT} の scaffold の新しい版（スキル、ルールなど）を取り込み、1 つのコミットにする。"
                    f"手で直したファイルは上書きせず、新しい版を {NEW_VERSIONS_DIR}/ に置いて報告する。")
    parser.add_argument("project", nargs="?", default=".", help="更新する作品のディレクトリ（既定: 今のディレクトリ）")
    parser.add_argument("--ref", default=os.environ.get(cli.ENV_REF, cli.DEFAULT_REF),
                        help=f"取り込む scaffold のブランチまたはタグ（既定: {cli.DEFAULT_REF}）")
    parser.add_argument("--repo", default=os.environ.get(cli.ENV_REPO, cli.DEFAULT_REPO),
                        help="scaffold の Git リポジトリ")
    parser.add_argument("--scaffold", default=None, help="GitHub から取得せず、手元の scaffold（git リポジトリ）を使う")
    parser.add_argument("--dry-run", action="store_true", help="変更せずに、何が変わるかだけを表示する")
    return parser


def run_update(args, scaffold_dir: Path | None = None) -> int:
    project = Path(args.project).expanduser().resolve()
    check_project(project)
    worktrees = [line[len("worktree "):] for line in git(["worktree", "list", "--porcelain"], project).splitlines()
                 if line.startswith("worktree ")][1:]
    local = Path(args.scaffold).expanduser().resolve() if args.scaffold else scaffold_dir
    with tempfile.TemporaryDirectory() as tmp:
        if local is not None:
            scaffold = cli.check_scaffold(local)
            if git(["status", "--porcelain"], scaffold).strip():
                cli.info(f"注意: {scaffold} に未コミットの変更があります。取り込むのはコミット済みの版（HEAD）だけです。")
            # 作業ツリーではなく HEAD を取り込むため、手元の scaffold も一時ディレクトリに clone する
            repo, ref = str(scaffold), git(["rev-parse", "--abbrev-ref", "HEAD"], scaffold).strip()
            scaffold = Path(tmp) / "scaffold"
            git(["clone", "--quiet", "--no-hardlinks", repo, str(scaffold)], Path(tmp))
        else:
            repo, ref = args.repo, args.ref
            scaffold = Path(tmp) / "scaffold"
            cli.info(f"==> scaffold を取得します: {repo}（{ref}）")
            git(["clone", "--quiet", "--branch", ref, repo, str(scaffold)], Path(tmp))
        sha = git(["rev-parse", "HEAD"], scaffold).strip()
        plan, new = build_plan(project, scaffold)
        print_plan(plan)
        if args.dry_run:
            cli.info("確認のみ行いました（--dry-run）。")
            return 0
        apply_plan(plan, project, scaffold, new)
        write_state(project, repo, ref, sha)
    git(["add", "-A"], project)
    if git(["status", "--porcelain"], project).strip():
        git(["commit", "--quiet", "-m", f"chore: {cli.KIT} を更新（{sha[:7]}）",
             "-m", f"Scaffold: {repo} {ref} ({sha})"], project)
        cli.info(f"==> 更新をコミットしました: {git(['rev-parse', '--short', 'HEAD'], project).strip()}")
    else:
        cli.info("==> すでに最新です。")
    if plan.modified:
        cli.info(f"==> 手で直されたファイルが {len(plan.modified)} 件あります。scaffold の新しい版と比べて、必要なら取り込んでください:")
        cli.info(f"      git diff --no-index <ファイル> {NEW_VERSIONS_DIR}/<ファイル>")
    if worktrees:
        cli.info("==> 作業中の worktree があります。worktree の中のスキルは、main にマージするまで更新前のままです:")
        for wt in worktrees:
            cli.info(f"      {wt}")
    return 0
