#!/usr/bin/env python3
"""new_project.py - novelkit の作品ディレクトリを作る（既存作品への取り込みにも使う）

使い方:
  python3 new_project.py <作品のディレクトリ> [--title <仮題>] [--link] [--adopt]

- 新しいディレクトリなら、scaffold の規則ファイル（CLAUDE.md、AGENTS.md、GEMINI.md、.kiro/steering/）と
  スキル（skills/novelkit/）を置き、各エージェントのスキルディレクトリからリンクし、git init と初回コミットを行う。
- --adopt: 既存の作品に取り込む。既存のファイルは上書きせず、衝突したものは一覧にするだけにする。
  git リポジトリなら初回コミットは作らない（変更は作者が確かめてからコミットする）。
- --link: スキルをコピーせず、scaffold のスキルへのシンボリックリンクにする（scaffold の更新がすぐ反映される）。
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
RULE_FILES = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", ".gitignore",
              ".kiro/steering/language.md", ".kiro/steering/novel-writing.md"]
AGENT_SKILL_DIRS = [".claude/skills", ".agents/skills", ".kiro/skills"]


def main() -> None:
    ap = argparse.ArgumentParser(description="novelkit の作品ディレクトリを作る")
    ap.add_argument("target")
    ap.add_argument("--title", default="")
    ap.add_argument("--link", action="store_true", help="スキルを scaffold へのシンボリックリンクにする")
    ap.add_argument("--adopt", action="store_true", help="既存の作品に取り込む（上書きしない）")
    args = ap.parse_args()

    target = Path(args.target).expanduser().resolve()
    if target.exists() and any(target.iterdir()) and not args.adopt:
        sys.exit(f"{target} は空ではありません。既存の作品に取り込むなら --adopt を付けてください。")
    target.mkdir(parents=True, exist_ok=True)
    added, skipped = [], []

    for rel in RULE_FILES:
        src, dst = SCAFFOLD / rel, target / rel
        if dst.exists():
            skipped.append(rel)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        added.append(rel)

    skills_src = SCAFFOLD / "skills" / "novelkit"
    skills_dst = target / "skills" / "novelkit"
    if skills_dst.exists() or skills_dst.is_symlink():
        skipped.append("skills/novelkit/")
    else:
        skills_dst.parent.mkdir(parents=True, exist_ok=True)
        if args.link:
            skills_dst.symlink_to(skills_src, target_is_directory=True)
        else:
            shutil.copytree(skills_src, skills_dst, ignore=shutil.ignore_patterns("__pycache__"))
        added.append("skills/novelkit/" + ("（リンク）" if args.link else ""))

    for base in AGENT_SKILL_DIRS:
        d = target / base
        d.mkdir(parents=True, exist_ok=True)
        for s in sorted(p.name for p in skills_src.iterdir() if p.is_dir()):
            link = d / s
            if link.exists() or link.is_symlink():
                continue
            rel = os.path.relpath(skills_dst / s, d)
            try:
                link.symlink_to(rel, target_is_directory=True)
            except OSError:
                shutil.copytree(skills_src / s, link, ignore=shutil.ignore_patterns("__pycache__"))
        added.append(base + "/")

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
    print("\n次の手順:")
    if args.adopt:
        print("  1. 追加されたファイルを確かめてコミットする")
        print("  2. .novelkit/config.yaml の paths を既存の配置に合わせる")
        print("  3. python3 skills/novelkit/novelkit-status/scripts/novelkit.py init で、足りないディレクトリだけを作る")
        print("  4. /novelkit-constitution（取り込み）と /novelkit-canon --adopt <設定のディレクトリ> を実行する")
    else:
        print(f"  cd {target} && claude \"/novelkit-bootstrap <1 文のコンセプト>\"")


if __name__ == "__main__":
    main()
