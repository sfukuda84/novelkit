#!/usr/bin/env python3
"""new_project.py - novelkit の作品ディレクトリを作る（既存作品への取り込みにも使う）

使い方:
  python3 new_project.py <作品のディレクトリ> [--title <仮題>] [--link] [--adopt]
  python3 new_project.py --relink <作品のディレクトリ>   # 各エージェントのスキルディレクトリのリンクだけを作り直す

- 新しいディレクトリなら、scaffold の規則ファイル（CLAUDE.md、AGENTS.md、GEMINI.md、.kiro/steering/）と
  スキル（skills/novelkit/）を置き、各エージェントのスキルディレクトリからリンクし、git init と初回コミットを行う。
- --adopt: 既存の作品に取り込む。既存のファイルは上書きせず、衝突したものは一覧にするだけにする。
  .gitignore が既にあれば、novelkit が動くのに要る行（scripts/gitignore-required.txt）のうち足りないものだけを末尾に足す。各エージェントのスキルディレクトリに同名のスキル
  （ディレクトリや別の場所へのリンク）があれば残し、CONFLICT として挙げる。
  git リポジトリなら初回コミットは作らない（変更は作者が確かめてからコミットする）。
- --link: スキルをコピーせず、scaffold のスキルへのシンボリックリンクにする（scaffold の更新がすぐ反映される）。
- --relink: CONFLICT のスキルを消した後などに、足りないリンクだけを張り直す。
標準ライブラリだけで書く（Python 3.9 以上）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCAFFOLD = Path(__file__).resolve().parents[1]
RULE_FILES = ["CLAUDE.md", "AGENTS.md", "GEMINI.md",
              ".kiro/steering/language.md", ".kiro/steering/novel-writing.md"]
AGENT_SKILL_DIRS = [".claude/skills", ".agents/skills", ".kiro/skills"]
STEERING_IMPORTS = ["@.kiro/steering/language.md", "@.kiro/steering/novel-writing.md"]
GITIGNORE_MARK = "# ===== novelkit の取り込みで追加 ====="
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def link_agent_dirs(target: Path, conflicts: list[str]) -> int:
    """各エージェントのスキルディレクトリから skills/novelkit/<skill> へ相対リンクを張る。作った数を返す。

    すでにある同名のディレクトリや、別の場所へのリンクは残し、conflicts に挙げる。
    リンクを作れない環境（Windows で開発者モードがオフなど）では、実体をコピーする。
    """
    skills_dir = target / "skills" / "novelkit"
    if not skills_dir.is_dir():
        sys.exit(f"{skills_dir} がありません。novelkit を取り込んだ作品のディレクトリを指定してください。")
    made = 0
    for base in AGENT_SKILL_DIRS:
        d = target / base
        d.mkdir(parents=True, exist_ok=True)
        for s in sorted(p.name for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith("__")):
            link = d / s
            want = os.path.relpath(skills_dir / s, d)
            if link.is_symlink():
                if os.readlink(link) == want:
                    continue
                conflicts.append(f"{base}/{s}（別の場所へのリンク: {os.readlink(link)}）")
                continue
            if link.exists():
                conflicts.append(f"{base}/{s}（既存のディレクトリ）")
                continue
            try:
                link.symlink_to(want, target_is_directory=True)
            except OSError:
                shutil.copytree(skills_dir / s, link, ignore=IGNORE)
                print(f"WARN: {base}/{s} はリンクを作れなかったため、実体をコピーしました。", file=sys.stderr)
            made += 1
    return made


def required_gitignore_lines(scaffold: Path) -> list[str]:
    """novelkit が動くのに要る .gitignore の行（scripts/gitignore-required.txt）。"""
    path = scaffold / "scripts" / "gitignore-required.txt"
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def merge_gitignore(target: Path, added: list[str], skipped: list[str]) -> None:
    """.gitignore がなければ scaffold のものをコピーする。あれば、novelkit が動くのに要る行のうち足りないものだけを足す。

    scaffold の .gitignore のほかの行（OS、エディタ、言語ごとの生成物など）は、既存のプロジェクトの事情に任せて足さない。
    """
    src, dst = SCAFFOLD / ".gitignore", target / ".gitignore"
    if not dst.exists():
        shutil.copy2(src, dst)
        added.append(".gitignore")
        return
    current = {line.strip() for line in dst.read_text(encoding="utf-8", errors="replace").splitlines()}
    wanted = [line for line in required_gitignore_lines(SCAFFOLD) if line not in current]
    if not wanted:
        skipped.append(".gitignore")
        return
    text = dst.read_text(encoding="utf-8", errors="replace")
    if text and not text.endswith("\n"):
        text += "\n"
    dst.write_text(text + f"\n{GITIGNORE_MARK}\n" + "\n".join(wanted) + "\n", encoding="utf-8")
    added.append(f".gitignore（{len(wanted)} 行を追記）")


def steering_hints(target: Path) -> list[str]:
    """既存の CLAUDE.md などが novelkit の steering を読み込んでいなければ、足す行を案内する。"""
    hints = []
    for name in ("CLAUDE.md", "GEMINI.md"):
        p = target / name
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace")
            missing = [line for line in STEERING_IMPORTS if line not in text]
            if missing:
                hints.append(f"{name} に次の行を足す: " + " / ".join(missing))
    p = target / "AGENTS.md"
    if p.exists():
        text = p.read_text(encoding="utf-8", errors="replace")
        missing = [rel for rel in RULE_FILES if rel.startswith(".kiro/steering/") and rel not in text]
        if missing:
            hints.append("AGENTS.md の読み込みリストに " + "、".join(f"`{m}`" for m in missing) + " を足す")
    return hints


def print_conflicts(conflicts: list[str]) -> None:
    if not conflicts:
        return
    print(f"CONFLICT（同名のスキルが既にあるため残した。{len(conflicts)} 件）:")
    for c in conflicts[:6]:
        print(f"  {c}")
    if len(conflicts) > 6:
        print(f"  ほか {len(conflicts) - 6} 件")


def relink_command(target: Path) -> str:
    """リンクを張り直すコマンド。uv で入れた new-novelkit-project から呼ばれたときは、scaffold が一時的な場所にあって
    終わると消えるので、このファイルのパスではなく、取り込みをもう一度実行するコマンドを示す（足りないリンクだけを作る）。"""
    launcher = os.environ.get("NOVELKIT_LAUNCHER")
    if launcher:
        return f'{launcher} "{target}" --adopt'
    return f"python3 {Path(__file__).resolve()} --relink {target}"


def main() -> None:
    ap = argparse.ArgumentParser(description="novelkit の作品ディレクトリを作る")
    ap.add_argument("target")
    ap.add_argument("--title", default="")
    ap.add_argument("--link", action="store_true", help="スキルを scaffold へのシンボリックリンクにする")
    ap.add_argument("--adopt", action="store_true", help="既存の作品に取り込む（上書きしない）")
    ap.add_argument("--relink", action="store_true", help="各エージェントのスキルディレクトリのリンクだけを作り直す")
    args = ap.parse_args()

    target = Path(args.target).expanduser().resolve()
    if args.relink:
        conflicts: list[str] = []
        made = link_agent_dirs(target, conflicts)
        print(f"LINKED: {made}")
        print_conflicts(conflicts)
        return
    if target.exists() and any(target.iterdir()) and not args.adopt:
        sys.exit(f"{target} は空ではありません。既存の作品に取り込むなら --adopt を付けてください。")
    target.mkdir(parents=True, exist_ok=True)
    added: list[str] = []
    skipped: list[str] = []
    conflicts = []

    for rel in RULE_FILES:
        src, dst = SCAFFOLD / rel, target / rel
        if dst.exists():
            skipped.append(rel)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        added.append(rel)
    merge_gitignore(target, added, skipped)

    skills_src = SCAFFOLD / "skills" / "novelkit"
    skills_dst = target / "skills" / "novelkit"
    if skills_dst.exists() or skills_dst.is_symlink():
        skipped.append("skills/novelkit/")
    else:
        skills_dst.parent.mkdir(parents=True, exist_ok=True)
        if args.link:
            skills_dst.symlink_to(skills_src, target_is_directory=True)
        else:
            shutil.copytree(skills_src, skills_dst, ignore=IGNORE)
        added.append("skills/novelkit/" + ("（リンク）" if args.link else ""))

    link_agent_dirs(target, conflicts)
    added.append("、".join(d + "/" for d in AGENT_SKILL_DIRS) + "（リンク）")

    is_repo = (target / ".git").exists()
    if not is_repo:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=target, check=True)
    helper = skills_dst / "novelkit-status" / "scripts" / "novelkit.py"
    cmd = [sys.executable, str(helper), "--root", str(target), "init"]
    if args.adopt:
        cmd.append("--config-only")  # paths を既存の配置に合わせる前に、空のディレクトリを作らない
    if args.title:
        cmd += ["--title", args.title]
    subprocess.run(cmd, check=True)

    # Claude Code のフック（Web 検索の回数を数え、セッションの区切りを判定する。novelkit-status §3「セッションの区切り」）
    subprocess.run([sys.executable, str(helper), "--root", str(target), "hooks", "install"], check=True)
    added.append(".claude/settings.json（フック）")

    if not is_repo:
        subprocess.run(["git", "add", "-A"], cwd=target, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "chore(novel): novelkit を初期化"], cwd=target, check=True)

    print(f"TARGET: {target}")
    print("ADDED: " + ", ".join(added))
    if skipped:
        print("SKIPPED（既存のため変更していない）: " + ", ".join(skipped))
    print_conflicts(conflicts)
    print("\n次の手順:")
    if args.adopt:
        step = 1
        print(f"  {step}. 追加されたファイルを確かめてコミットする"); step += 1
        for hint in steering_hints(target):
            print(f"  {step}. {hint}"); step += 1
        if conflicts:
            print(f"  {step}. CONFLICT のスキルは既存のものを残した。novelkit 版に揃えるなら、既存のものを消してから "
                  f"`{relink_command(target)}` を実行する（足りないリンクだけを作る）"); step += 1
        print(f"  {step}. .novelkit/config.yaml の paths を既存の配置に合わせる（ファイルは動かさない）"); step += 1
        print(f"  {step}. python3 skills/novelkit/novelkit-status/scripts/novelkit.py init で、足りないディレクトリだけを作る"); step += 1
        print(f"  {step}. /novelkit-bootstrap --adopt で、既存のプロット・設定・本文から足りない成果物だけを作る"
              "（文体の決まりと正典の取り込みも、この中で行う）")
    else:
        print(f"  cd {target} && claude \"/novelkit-bootstrap <1 文のコンセプト>\"")


if __name__ == "__main__":
    main()
