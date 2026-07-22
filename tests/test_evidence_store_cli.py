from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
SKILLGUARD = SCRIPT_ROOT / "skillguard.py"


def _snapshot(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _run(*args: str, expected_exit: int = 0) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, str(SKILLGUARD), *args],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != expected_exit:
        raise AssertionError(
            f"unexpected exit {completed.returncode}; stderr={completed.stderr}; "
            f"stdout={completed.stdout}"
        )
    return json.loads(completed.stdout)


class EvidenceStoreCliTests(unittest.TestCase):
    def test_commands_expose_current_lifecycle_schemas(self) -> None:
        payload = _run("commands")
        commands = {row["name"]: row for row in payload["commands"]}
        self.assertEqual(
            "skillguard.evidence_audit.current",
            commands["evidence-audit"]["output_schema"],
        )
        self.assertEqual(
            "skillguard.evidence_gc_plan.current",
            commands["evidence-gc-plan"]["output_schema"],
        )
        self.assertEqual(
            "skillguard.evidence_gc_apply_receipt.current",
            commands["evidence-gc-apply"]["output_schema"],
        )
        self.assertEqual(
            "skillguard.evidence_gc_purge_receipt.current",
            commands["evidence-gc-purge"]["output_schema"],
        )

    def test_audit_plan_apply_and_purge_cli_preserve_mutation_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            root = workspace / "owner"
            root.mkdir()
            orphan = root / "orphan.bin"
            orphan.write_bytes(b"orphan")
            before = _snapshot(root)

            audit = _run("evidence-audit", "--owner-evidence-root", str(root))
            plan = _run("evidence-gc-plan", "--owner-evidence-root", str(root))

            self.assertEqual("passed", audit["status"])
            self.assertEqual("ready", plan["status"])
            self.assertEqual(before, _snapshot(root))
            plan_path = workspace / "plan.json"
            plan_path.write_text(
                json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            quarantine = root / "lifecycle/quarantine"
            applied = _run(
                "evidence-gc-apply",
                "--owner-evidence-root",
                str(root),
                "--plan",
                str(plan_path),
                "--quarantine-root",
                str(quarantine),
            )
            self.assertFalse(orphan.exists())
            apply_path = workspace / "apply.json"
            apply_path.write_text(
                json.dumps(applied, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            purged = _run(
                "evidence-gc-purge",
                "--owner-evidence-root",
                str(root),
                "--apply-receipt",
                str(apply_path),
                "--quarantine-root",
                str(quarantine),
                "--confirm-plan-hash",
                plan["plan_hash"],
                "--grace-seconds",
                "0",
            )
            self.assertEqual("purged", purged["status"])
            self.assertFalse(
                (root / applied["items"][0]["quarantine_relative_path"]).exists()
            )


if __name__ == "__main__":
    unittest.main()
