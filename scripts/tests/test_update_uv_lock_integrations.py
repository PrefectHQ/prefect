"""Safe regression tests: GitHub, index access, and sleeps are mocked."""

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "updater", ROOT / "scripts/update_uv_lock_integrations.py"
)
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class UpdateTests(unittest.TestCase):
    def test_release_validation(self):
        self.assertEqual(
            updater.release("prefect-redis-0.3.0"), ("prefect-redis", "0.3.0")
        )
        with self.assertRaises(ValueError):
            updater.release("main")

    @patch.object(updater.time, "sleep")
    @patch.object(updater, "run")
    @patch.object(updater, "pins")
    def test_index_eventually_available(self, pins, run, sleep):
        pins.side_effect = [{"prefect-redis": "0.2.11"}, {"prefect-redis": "0.3.0"}]
        run.side_effect = [subprocess.CalledProcessError(1, "uv"), ""]
        updater.upgrade("prefect-redis", "0.3.0")
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(30)
        self.assertIn("prefect-redis==0.3.0", run.call_args.args)

    @patch.object(updater.time, "sleep")
    @patch.object(updater, "run", return_value="")
    @patch.object(updater, "pins", return_value={"prefect-redis": "0.2.11"})
    def test_version_mismatch_fails_bounded(self, pins, run, sleep):
        with self.assertRaises(RuntimeError):
            updater.upgrade("prefect-redis", "0.3.0", attempts=3)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch.object(updater, "run")
    @patch.object(updater, "pins", return_value={"prefect-redis": "0.4.0"})
    def test_old_release_never_downgrades(self, pins, run):
        updater.upgrade("prefect-redis", "0.3.0")
        run.assert_not_called()

    def test_branch_recovery(self):
        for state in (None, "OPEN", "CLOSED", "MERGED"):
            with (
                self.subTest(state=state),
                patch.dict(
                    os.environ, {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2"}
                ),
            ):
                prs = [] if state is None else [{"state": state}]
                with patch.object(
                    updater,
                    "run",
                    side_effect=[json.dumps(prs), "sha", "", "", "uv.lock", ""],
                ) as run:
                    branch, is_open = updater.prepare_branch("automation/test")
                self.assertEqual(is_open, state == "OPEN")
                self.assertEqual(
                    branch.endswith("-123-2"), state in ("CLOSED", "MERGED")
                )
                self.assertIn(
                    ("git", "merge", "--no-edit", "origin/main"),
                    [c.args for c in run.call_args_list],
                )

    @patch.object(updater, "run", side_effect=["[]", "sha", "", "", "other.py"])
    def test_unrelated_branch_changes_rejected(self, run):
        with self.assertRaises(RuntimeError):
            updater.prepare_branch("automation/test")

    def test_recover_orphan_and_existing_pr_without_new_changes(self):
        for open_pr in (False, True):
            with (
                self.subTest(open_pr=open_pr),
                patch.dict(os.environ, {"RELEASE_TAG": "prefect-redis-0.3.0"}),
                patch.object(updater, "pins", return_value={"prefect-redis": "0.3.0"}),
                patch.object(
                    updater, "prepare_branch", return_value=("automation/test", open_pr)
                ),
                patch.object(updater, "run") as run,
            ):
                run.side_effect = lambda *args: (
                    "existing lock diff"
                    if args[:3] == ("git", "diff", "origin/main...HEAD")
                    else ""
                )
                updater.main()
                calls = [c.args for c in run.call_args_list]
                self.assertTrue(any(c[:2] == ("git", "push") for c in calls))
                self.assertEqual(
                    any(c[:3] == ("gh", "pr", "create") for c in calls), not open_pr
                )

    @patch.dict(os.environ, {"RELEASE_TAG": ""})
    @patch.object(
        updater,
        "pins",
        return_value={"prefect-redis": "0.3.0", "prefect-aws": "0.7.12"},
    )
    @patch.object(updater, "prepare_branch", return_value=("automation/sweep", False))
    @patch.object(updater, "run", return_value="")
    def test_weekly_upgrades_all_pins_without_empty_pr(self, run, branch, pins):
        updater.main()
        calls = [c.args for c in run.call_args_list]
        self.assertIn(
            (
                "uv",
                "lock",
                "--upgrade-package",
                "prefect-aws",
                "--upgrade-package",
                "prefect-redis",
            ),
            calls,
        )
        self.assertFalse(any(c[:2] == ("git", "push") for c in calls))

    def test_real_git_orphan_branch_recovery_preserves_commits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, local = root / "remote.git", root / "local"
            subprocess.run(
                ["git", "init", "--bare", str(remote)], check=True, capture_output=True
            )
            subprocess.run(
                ["git", "clone", str(remote), str(local)],
                check=True,
                capture_output=True,
            )
            old = Path.cwd()
            os.chdir(local)
            try:
                updater.run("git", "config", "user.name", "Test")
                updater.run("git", "config", "user.email", "test@example.invalid")
                updater.run("git", "checkout", "-b", "main")
                Path("uv.lock").write_text("old lock\n")
                updater.run("git", "add", "uv.lock")
                updater.run("git", "commit", "-m", "base")
                updater.run("git", "push", "origin", "main")
                updater.run("git", "checkout", "-b", "automation/test")
                Path("uv.lock").write_text("updated lock\n")
                updater.run("git", "commit", "-am", "upgrade")
                original = updater.run("git", "rev-parse", "HEAD")
                updater.run("git", "push", "origin", "automation/test")
                updater.run("git", "checkout", "main")
                actual_run = updater.run
                with patch.object(
                    updater,
                    "run",
                    side_effect=lambda *args: (
                        "[]" if args[0] == "gh" else actual_run(*args)
                    ),
                ):
                    branch, is_open = updater.prepare_branch("automation/test")
                self.assertFalse(is_open)
                self.assertEqual(branch, "automation/test")
                self.assertEqual(updater.run("git", "rev-parse", "HEAD"), original)
                self.assertEqual(Path("uv.lock").read_text(), "updated lock\n")
            finally:
                os.chdir(old)

    def test_publication_dependency_and_weekly_triggers(self):
        # A failed/skipped publication prevents the dependent job by GitHub's
        # default success() condition; there is deliberately no always() override.
        release = yaml.load(
            (ROOT / ".github/workflows/integration-package-release.yaml").read_text(),
            Loader=yaml.BaseLoader,
        )
        job = release["jobs"]["update-integration-lock"]
        self.assertIn("publish-pypi-dists", job["needs"])
        self.assertNotIn("if", job)
        workflow = yaml.load(
            (ROOT / ".github/workflows/update-uv-lock-integrations.yaml").read_text(),
            Loader=yaml.BaseLoader,
        )
        self.assertNotIn("push", workflow["on"])
        self.assertEqual(
            set(workflow["on"]), {"workflow_call", "schedule", "workflow_dispatch"}
        )
        self.assertEqual(workflow["on"]["schedule"][0]["cron"], "0 15 * * 1")


if __name__ == "__main__":
    unittest.main()
