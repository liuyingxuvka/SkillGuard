from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.privacy import (  # noqa: E402
    audit_public_export,
    git_public_candidates,
    public_path_token,
)


class PrivacyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.workspace = Path(self.temp.name)
        self.policy = self.workspace / "policy.json"
        self.policy.write_text(
            json.dumps(
                {
                    "blocked_extensions": [".db", ".log"],
                    "blocked_names": [".env"],
                    "runtime_path_prefixes": [".skillguard/runs/"],
                    "allowed_binary_extensions": [".png"],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _relative(self, path: Path) -> str:
        return path.relative_to(ROOT).as_posix()

    def test_safe_text_passes_and_paths_are_tokenized(self) -> None:
        safe = self.workspace / "safe.txt"
        safe.write_text("portable example\n", encoding="utf-8")
        report = audit_public_export(ROOT, self.policy, candidate_paths=[self._relative(safe)])
        self.assertEqual("passed", report["status"])
        self.assertEqual(f"repository_root/{self._relative(safe)}", public_path_token(safe, ROOT))

    def test_secret_and_machine_path_findings_do_not_echo_sensitive_content(self) -> None:
        private_root = self.workspace / "private-home"
        private_root.mkdir()
        value = "github_pat_" + ("A" * 28)
        leak = self.workspace / "leak.txt"
        leak.write_text(f"token={value}\npath={private_root}\n", encoding="utf-8")
        report = audit_public_export(
            ROOT,
            self.policy,
            candidate_paths=[self._relative(leak)],
            sensitive_roots=[private_root],
        )
        self.assertEqual("blocked", report["status"])
        serialized = json.dumps(report)
        self.assertNotIn(value, serialized)
        self.assertNotIn(str(private_root), serialized)
        self.assertIn("github_token", serialized)
        self.assertIn("machine_specific_absolute_path", serialized)

    def test_generic_windows_and_posix_machine_paths_are_blocked(self) -> None:
        leak = self.workspace / "generic-paths.txt"
        windows_path = "D:" + chr(92) + "private-work" + chr(92) + "report.json"
        posix_path = "/" + "home/private-user/report.json"
        leak.write_text(
            f"windows={windows_path}\nposix={posix_path}\n",
            encoding="utf-8",
        )
        report = audit_public_export(
            ROOT,
            self.policy,
            candidate_paths=[self._relative(leak)],
        )
        self.assertEqual("blocked", report["status"])
        findings = [
            row
            for row in report["findings"]
            if row["code"] == "machine_specific_absolute_path"
        ]
        self.assertEqual([1, 2], [row["line"] for row in findings])

    def test_runtime_state_and_private_extensions_block(self) -> None:
        runtime = ROOT / ".skillguard" / "runs" / "privacy-fixture.log"
        runtime.parent.mkdir(parents=True, exist_ok=True)
        runtime.write_text("fixture\n", encoding="utf-8")
        self.addCleanup(runtime.unlink)
        report = audit_public_export(ROOT, self.policy, candidate_paths=[runtime.relative_to(ROOT).as_posix()])
        self.assertEqual("blocked", report["status"])
        self.assertTrue(any(row["code"] == "runtime_state_in_public_export" for row in report["findings"]))
        self.assertTrue(any(row["code"] == "blocked_private_file_type" for row in report["findings"]))

    def test_shared_policy_blocks_reserved_runtime_candidate(self) -> None:
        runtime = self.workspace / ".sg-runtime" / "case" / "receipt.json"
        runtime.parent.mkdir(parents=True)
        runtime.write_text("{}\n", encoding="utf-8")
        report = audit_public_export(
            ROOT,
            self.policy,
            candidate_paths=[self._relative(runtime)],
        )
        self.assertEqual("blocked", report["status"])
        self.assertTrue(
            any(
                row["code"] == "runtime_state_in_public_export"
                for row in report["findings"]
            )
        )

    def test_public_image_requires_a_current_hash_bound_visual_review(self) -> None:
        image = self.workspace / "preview.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        report = audit_public_export(ROOT, self.policy, candidate_paths=[self._relative(image)])
        self.assertEqual("blocked", report["status"])
        self.assertTrue(any(row["code"] == "visual_privacy_review_missing" for row in report["findings"]))

    def test_unreadable_candidate_blocks_without_crashing(self) -> None:
        candidate = self.workspace / "locked.txt"
        candidate.write_text("locked\n", encoding="utf-8")
        original = Path.read_bytes

        def read_bytes(path: Path) -> bytes:
            if path.resolve() == candidate.resolve():
                raise PermissionError("fixture locked")
            return original(path)

        with mock.patch.object(Path, "read_bytes", read_bytes):
            report = audit_public_export(
                ROOT,
                self.policy,
                candidate_paths=[self._relative(candidate)],
            )
        self.assertEqual("blocked", report["status"])
        self.assertTrue(
            any(row["code"] == "candidate_unreadable" for row in report["findings"])
        )

    def test_deleted_tracked_path_is_not_a_current_public_candidate(self) -> None:
        with mock.patch(
            "skillguard_v2.privacy._git",
            return_value="deleted-former-runtime.json\n",
        ):
            self.assertEqual([], git_public_candidates(self.workspace))


if __name__ == "__main__":
    unittest.main()
