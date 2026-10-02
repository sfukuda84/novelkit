"""new-novelkit-project（作成・取り込み・update）のテスト。作業ツリーの scaffold を一時的な Git リポジトリにして、そこから作る。"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCAFFOLD = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCAFFOLD / "tool" / "src"))

from new_novelkit_project import cli, update  # noqa: E402

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
}
SKILL = "skills/novelkit/novelkit-bootstrap/SKILL.md"
OTHER = "skills/novelkit/novelkit-seed/SKILL.md"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def call(*argv: str, scaffold_dir: Path | None = None) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cli.main(list(argv), scaffold_dir=scaffold_dir)
    return code, out.getvalue()


class ToolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.env_backup = dict(os.environ)
        os.environ.update(GIT_ENV)
        cls.tmp = Path(tempfile.mkdtemp()).resolve()
        os.environ["GIT_CONFIG_GLOBAL"] = str(cls.tmp / "gitconfig")
        Path(os.environ["GIT_CONFIG_GLOBAL"]).write_text("[user]\n\tname = t\n\temail = t@example.com\n",
                                                        encoding="utf-8")
        cls.repo = cls.tmp / "scaffold"
        shutil.copytree(SCAFFOLD, cls.repo, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", ".worktrees", "__pycache__"))
        git("init", "-q", "-b", "main", cwd=cls.repo)
        git("add", "-A", cwd=cls.repo)
        git("commit", "-qm", "scaffold", cwd=cls.repo)
        cls.url = cls.repo.as_uri()

    @classmethod
    def tearDownClass(cls) -> None:
        os.environ.clear()
        os.environ.update(cls.env_backup)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def work(self, name: str) -> Path:
        path = Path(tempfile.mkdtemp(dir=self.tmp)) / name
        return path

    def test_create_from_repo_records_state(self) -> None:
        target = self.work("p")
        code, out = call(str(target), "--repo", self.url, "--no-launch")
        self.assertEqual(code, 0, out)
        self.assertTrue((target / SKILL).is_file())
        self.assertTrue((target / ".claude" / "skills" / "novelkit-bootstrap").is_symlink())
        self.assertIn('"sha"', (target / update.STATE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(git("status", "--porcelain", cwd=target), "")
        self.assertIn("版を記録", git("log", "-1", "--format=%s", cwd=target))

    def test_link_requires_local_scaffold(self) -> None:
        code, out = call(str(self.work("p")), "--repo", self.url, "--link", "--no-launch")
        self.assertEqual(code, 1)
        self.assertIn("--link", out)

    def test_link_with_local_scaffold(self) -> None:
        target = self.work("p")
        code, out = call(str(target), "--link", "--no-launch", scaffold_dir=self.repo)
        self.assertEqual(code, 0, out)
        self.assertTrue((target / "skills" / "novelkit").is_symlink())

    def test_nonempty_target_without_adopt(self) -> None:
        target = self.work("p")
        target.mkdir(parents=True)
        (target / "x.txt").write_text("x", encoding="utf-8")
        code, out = call(str(target), "--repo", self.url, "--no-launch")
        self.assertEqual(code, 1)
        self.assertIn("--adopt", out)

    def test_update_flow(self) -> None:
        scaffold = self.work("sc")
        git("clone", "-q", self.url, str(scaffold), cwd=self.tmp)
        target = self.work("p")
        self.assertEqual(call(str(target), "--repo", scaffold.as_uri(), "--no-launch")[0], 0)
        # 作品側で 1 つ手で直す
        with (target / OTHER).open("a", encoding="utf-8") as f:
            f.write("\n手直し\n")
        git("commit", "-qam", "hand", cwd=target)
        # scaffold の新しい版
        with (scaffold / SKILL).open("a", encoding="utf-8") as f:
            f.write("\n新しい版\n")
        with (scaffold / OTHER).open("a", encoding="utf-8") as f:
            f.write("\n新しい版\n")
        (scaffold / "skills" / "novelkit" / "novelkit-bootstrap" / "added.md").write_text("added\n", encoding="utf-8")
        git("add", "-A", cwd=scaffold)
        git("commit", "-qm", "B", cwd=scaffold)

        code, out = call("update", str(target), "--repo", scaffold.as_uri(), "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertNotIn("新しい版", (target / SKILL).read_text(encoding="utf-8"))

        code, out = call("update", str(target), "--repo", scaffold.as_uri())
        self.assertEqual(code, 0, out)
        self.assertIn("新しい版", (target / SKILL).read_text(encoding="utf-8"))
        self.assertTrue((target / "skills" / "novelkit" / "novelkit-bootstrap" / "added.md").is_file())
        other = (target / OTHER).read_text(encoding="utf-8")
        self.assertIn("手直し", other)
        self.assertNotIn("新しい版", other)
        self.assertTrue((target / update.NEW_VERSIONS_DIR / OTHER).is_file())
        self.assertEqual(git("status", "--porcelain", cwd=target), "")
        self.assertIn("を更新", git("log", "-1", "--format=%s", cwd=target))
        code, out = call("update", str(target), "--repo", scaffold.as_uri())
        self.assertIn("すでに最新", out)

    def test_update_keeps_adopted_conflicts(self) -> None:
        target = self.work("p")
        target.mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=target)
        own = target / ".claude" / "skills" / "novelkit-bootstrap"
        own.mkdir(parents=True)
        (own / "SKILL.md").write_text("mine\n", encoding="utf-8")
        (target / "CLAUDE.md").write_text("# mine\n", encoding="utf-8")
        git("add", "-A", cwd=target)
        git("commit", "-qm", "init", cwd=target)
        code, out = call(str(target), "--adopt", "--repo", self.url)
        self.assertEqual(code, 0, out)
        git("add", "-A", cwd=target)
        git("commit", "-qm", "adopt", cwd=target)
        code, out = call("update", str(target), "--repo", self.url)
        self.assertEqual(code, 0, out)
        self.assertEqual((own / "SKILL.md").read_text(encoding="utf-8"), "mine\n")
        self.assertEqual((target / "CLAUDE.md").read_text(encoding="utf-8"), "# mine\n")
        self.assertIn("同名の既存のもの", out)

    def test_adopt_relink_hint_points_to_command(self) -> None:
        target = self.work("p")
        own = target / ".claude" / "skills" / "novelkit-bootstrap"
        own.mkdir(parents=True)
        (own / "SKILL.md").write_text("mine\n", encoding="utf-8")
        git("init", "-q", "-b", "main", cwd=target)
        git("add", "-A", cwd=target)
        git("commit", "-qm", "init", cwd=target)
        code, out = call(str(target), "--adopt", "--repo", self.url)
        self.assertEqual(code, 0, out)
        self.assertIn(f'{cli.PROG} "{target}" --adopt', out)
        self.assertNotIn("novelkit-scaffold-", out)  # 消える一時的な scaffold のパスを案内しない
        # 案内どおり、既存のものを消して取り込みをもう一度実行すると、足りないリンクだけを作る
        shutil.rmtree(own)
        code, out = call(str(target), "--adopt", "--repo", self.url)
        self.assertEqual(code, 0, out)
        self.assertTrue(own.is_symlink())

    def test_update_stops_on_dirty_tree(self) -> None:
        target = self.work("p")
        self.assertEqual(call(str(target), "--repo", self.url, "--no-launch")[0], 0)
        (target / "dirty.txt").write_text("x", encoding="utf-8")
        code, out = call("update", str(target), "--repo", self.url)
        self.assertEqual(code, 1)
        self.assertIn("未コミット", out)


if __name__ == "__main__":
    unittest.main()
