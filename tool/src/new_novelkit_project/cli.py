"""new-novelkit-project: novelkit の作品を作り、Claude Code で立ち上げ（novelkit-bootstrap）を始める。

手順:
  1. scaffold を用意する。既定では GitHub から clone する（--ref でブランチやタグ、--repo でリポジトリを指定できる）。
     --scaffold <ディレクトリ> を付けると、手元の scaffold を使う（scaffold の scripts/new-novelkit-project から呼んだときはその scaffold）。
  2. scaffold の scripts/new_project.py で作品を作る（規則ファイル、スキル、git init）。
  3. 1 文のコンセプトがあれば claude を対話モードで起動し、"/novelkit-bootstrap [--auto|--oneshot] <コンセプト>" を渡す。

- --link（スキルを scaffold へのシンボリックリンクにする）は、手元の scaffold を使うときだけ使える
  （GitHub から clone した scaffold は一時的な場所にあり、終わると消えるため）。
- --adopt（既存の作品への取り込み）のときはエージェントを起動しない。続きの手順は new_project.py が表示する。
- 作成済みの作品に scaffold の新しい版を取り込むには `new-novelkit-project update [ディレクトリ]`（手で直したファイルは上書きしない）。
- コマンドの更新は `uv tool upgrade new-novelkit-project`。scaffold は実行のたびに取得するので、スキルも最新の版で作られる。

macOS / Linux / Windows で動くように、標準ライブラリだけで書く（Python 3.9 以上）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__

KIT = "novelkit"
PROG = "new-novelkit-project"
DEFAULT_REPO = "https://github.com/sfukuda84/novelkit.git"
DEFAULT_REF = "main"
ENV_REPO = "NOVELKIT_SCAFFOLD_REPO"
ENV_REF = "NOVELKIT_SCAFFOLD_REF"
BOOTSTRAP = "/novelkit-bootstrap"


class CliError(Exception):
    """利用者に伝えて終了するエラー。"""


def info(message: str) -> None:
    print(message, file=sys.stderr)


def remove_tree(path: Path) -> None:
    """Windows の読み取り専用ファイル（.git/objects など）も消せるように削除する。"""

    def on_error(func, target, _exc_info):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if path.exists():
        shutil.rmtree(path, onerror=on_error)


def run_git(args: list[str], cwd: Path | None = None) -> str:
    if shutil.which("git") is None:
        raise CliError("git が見つかりません。Git をインストールしてください。")
    proc = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise CliError(f"git {' '.join(args)} が失敗しました。\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def clone_scaffold(repo: str, ref: str, dest: Path) -> str:
    """scaffold を clone し、コミットの SHA を返す。"""
    info(f"==> scaffold を取得します: {repo}（{ref}）")
    run_git(["clone", "--quiet", "--depth", "1", "--branch", ref, repo, str(dest)])
    return run_git(["rev-parse", "HEAD"], cwd=dest)


def check_scaffold(path: Path) -> Path:
    path = path.expanduser().resolve()
    if not (path / "scripts" / "new_project.py").is_file() or not (path / "skills" / KIT).is_dir():
        raise CliError(f"{path} は {KIT} の scaffold ではありません（scripts/new_project.py と skills/{KIT}/ が要る）。")
    return path


def check_target(target: Path, adopt: bool) -> None:
    """clone の前に確かめる（作れないと分かっているのに scaffold を取得しない）。"""
    if target.exists() and not target.is_dir():
        raise CliError(f"{target} はディレクトリではありません。")
    if not adopt and target.exists() and any(target.iterdir()):
        raise CliError(f"{target} は空ではありません。既存の作品に取り込むなら --adopt を付けてください。")
    if adopt and not target.is_dir():
        raise CliError(f"{target} がありません。--adopt には既存の作品のディレクトリを指定してください。")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog=PROG,
        description=f"{KIT} の作品を作り、Claude Code で立ち上げ（{KIT}-bootstrap）を始める。"
                    f"コマンドの更新は `uv tool upgrade {PROG}`。")
    ap.add_argument("target", help="作る作品のディレクトリ（存在しないか、空であること。--adopt なら既存の作品）")
    ap.add_argument("--title", default="", help="作品の仮題（.novelkit/config.yaml の title）")
    ap.add_argument("-m", "--message", default=None, help="1 文のコンセプト。省略時は対話で入力を受ける")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--auto", action="store_true", help=f"質問せず推奨案を採用して進める（{KIT}-bootstrap --auto）")
    mode.add_argument("--oneshot", action="store_true", help="最初に一度だけまとめて質問し、以降は自動で進める")
    ap.add_argument("--link", action="store_true",
                    help="スキルをコピーせず、scaffold へのシンボリックリンクにする（手元の scaffold を使うときだけ）")
    ap.add_argument("--adopt", action="store_true",
                    help=f"既存の作品に取り込む（上書きしない。エージェントは起動しない。続きは {BOOTSTRAP} --adopt）")
    ap.add_argument("--no-launch", action="store_true", help="エージェントを起動せず、次の手順だけを表示する")
    ap.add_argument("--scaffold", default=None, help="GitHub から取得せず、手元の scaffold のディレクトリを使う")
    ap.add_argument("--ref", default=os.environ.get(ENV_REF, DEFAULT_REF),
                    help=f"取得する scaffold のブランチまたはタグ（既定: {DEFAULT_REF}。環境変数 {ENV_REF}）")
    ap.add_argument("--repo", default=os.environ.get(ENV_REPO, DEFAULT_REPO),
                    help=f"scaffold の Git リポジトリ（既定: {DEFAULT_REPO}。環境変数 {ENV_REPO}）")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return ap


def new_project_command(scaffold: Path, target: Path, args: argparse.Namespace) -> list[str]:
    cmd = [sys.executable, str(scaffold / "scripts" / "new_project.py"), str(target)]
    if args.title:
        cmd += ["--title", args.title]
    if args.link:
        cmd.append("--link")
    if args.adopt:
        cmd.append("--adopt")
    return cmd


def launch(target: Path, args: argparse.Namespace) -> int:
    concept = args.message
    if concept is None and not args.no_launch and sys.stdin.isatty():
        try:
            concept = input("\n1 文のコンセプト（空のまま Enter で、起動せずに終える）: ").strip()
        except EOFError:
            concept = ""
    mode_flag = "--auto" if args.auto else "--oneshot" if args.oneshot else ""
    prompt = " ".join(p for p in [BOOTSTRAP, mode_flag, (concept or "").strip()] if p)

    claude = shutil.which("claude")
    if args.no_launch or not concept or not claude:
        # コンセプトがなければ、new_project.py が表示した「次の手順」で足りる（同じ案内を二度出さない）
        if concept:
            if not claude:
                print("\nclaude コマンドが見つからないため、起動しません。")
            print("\n立ち上げの始め方（コンセプトとモードを入れたもの）:")
            print(f'  cd "{target}" && claude "{prompt}"')
        return 0
    print(f"\nClaude Code を起動します: {prompt}")
    return subprocess.run([claude, prompt], cwd=str(target)).returncode


def record_state(target: Path, repo: str, ref: str, sha: str, commit: bool) -> None:
    """使った scaffold の版を記録する（update が使う）。新規のときは初回コミットに続けてコミットする。"""
    from . import update

    update.write_state(target, repo, ref, sha)
    if commit:
        run_git(["add", update.STATE_FILE], cwd=target)
        run_git(["commit", "--quiet", "-m", f"chore: {KIT} の版を記録（{sha[:7]}）",
                 "-m", f"Scaffold: {repo} {ref} ({sha})"], cwd=target)


def run(args: argparse.Namespace, scaffold_dir: Path | None) -> int:
    target = Path(args.target).expanduser().resolve()
    check_target(target, args.adopt)
    local = Path(args.scaffold) if args.scaffold else scaffold_dir
    if args.link and local is None:
        raise CliError("--link は、手元の scaffold を使うとき（--scaffold <ディレクトリ>）だけ使えます。"
                       "GitHub から取得した scaffold は一時的な場所にあり、終わると消えるためです。")
    if local is not None:
        scaffold = check_scaffold(local)
        code = subprocess.run(new_project_command(scaffold, target, args)).returncode
        repo, ref, sha = str(scaffold), "", ""
        if (scaffold / ".git").exists():
            ref = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=scaffold)
            sha = run_git(["rev-parse", "HEAD"], cwd=scaffold)
    else:
        repo, ref = args.repo, args.ref
        tmp = Path(tempfile.mkdtemp(prefix=f"{KIT}-scaffold-"))
        try:
            scaffold = tmp / "scaffold"
            sha = clone_scaffold(repo, ref, scaffold)
            info(f"==> scaffold の版: {sha[:7]}")
            code = subprocess.run(new_project_command(check_scaffold(scaffold), target, args)).returncode
        finally:
            remove_tree(tmp)
    if code != 0:
        return 1
    if sha:
        record_state(target, repo, ref, sha, commit=not args.adopt)
    if args.adopt:
        return 0
    return launch(target, args)


def main(argv: list[str] | None = None, scaffold_dir: Path | None = None) -> int:
    """scaffold_dir は、scaffold の scripts/new-novelkit-project から呼ぶときに、その scaffold を渡す。"""
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty() and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv and argv[0] == "update":
            from . import update

            return update.run_update(update.build_update_parser().parse_args(argv[1:]), scaffold_dir)
        return run(build_parser().parse_args(argv), scaffold_dir)
    except CliError as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n中断しました。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
