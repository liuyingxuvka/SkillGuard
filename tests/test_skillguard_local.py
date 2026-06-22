"""Standard-library smoke checks for the local SkillGuard command surface."""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLGUARD = REPO_ROOT / ".agents" / "skills" / "skillguard" / "scripts" / "skillguard.py"
EXAMPLES = REPO_ROOT / "examples" / "README.md"

PRIVATE_OR_SECRET_PATTERNS = (
    re.compile(r"(?i)([A-Z]:[\\/][^\\s`\"']+|/Users/|\\\\[^\\s`\"']+)"),
    re.compile(r"\b(?:packet|lease|result)-\d{4,}\b"),
    re.compile(r"BEGIN (?:RSA |OPENSSH |DSA |EC |PGP )?PRIVATE\s+KEY"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]"),
)

UNSAFE_CLAIM_PATTERNS = (
    re.compile(r"(?i)\bfixture\s+coverage\s+(?:passed|complete|validated|proven)\b"),
    re.compile(r"(?i)\b(?:full|complete|end-to-end)\s+suite\s+automation\b"),
    re.compile(r"(?i)\bpackage\s+publication\s+(?:complete|ready|done|validated|proven)\b"),
    re.compile(r"(?i)\brelease\s+readiness\s+(?:complete|ready|validated|proven)\b"),
    re.compile(r"(?i)\bcode-contract\s+validation\s+(?:passed|complete|validated|proven)\b"),
    re.compile(r"(?i)\btests\s+passed\b"),
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def run_skillguard(*args: str, expected_exit: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(SKILLGUARD), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != expected_exit:
        raise AssertionError(
            f"skillguard.py {' '.join(args)} exited {completed.returncode}, expected {expected_exit}\n"
            f"stderr={completed.stderr}\nstdout={completed.stdout}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"command did not produce parseable JSON: {exc}\n{completed.stdout}") from exc


class SkillGuardLocalExamplesTest(unittest.TestCase):
    maxDiff = None

    def assert_clean_pass(self, report: dict[str, Any]) -> None:
        self.assertEqual(report.get("decision"), "pass")
        self.assertEqual(report.get("failures"), [])
        self.assertEqual(report.get("blockers"), [])
        self.assertIn("claim_boundary", report)

    def test_single_skill_example_command(self) -> None:
        report = run_skillguard("check-skill", "--target", ".agents/skills/skillguard/fixtures/good_single_skill")
        self.assert_clean_pass(report)
        self.assertEqual(report.get("target_path"), ".agents/skills/skillguard/fixtures/good_single_skill")

    def test_suite_example_command(self) -> None:
        report = run_skillguard(
            "check-suite",
            "--suite-root",
            ".agents/skills/skillguard/fixtures/good_suite/suite",
            "--suite-map",
            ".agents/skills/skillguard/fixtures/good_suite/suite/suite-map.json",
            "--suite-contract",
            ".agents/skills/skillguard/fixtures/good_suite/suite/suite-contract.json",
            "--member-root",
            ".agents/skills",
        )
        self.assert_clean_pass(report)
        self.assertEqual(report.get("target_path"), ".agents/skills/skillguard/fixtures/good_suite/suite")

    def test_fixture_manifest_examples(self) -> None:
        positive = run_skillguard("fixture-test", "--manifest", ".agents/skills/skillguard/fixtures/fixture-manifest.json")
        self.assert_clean_pass(positive)
        self.assertEqual(positive.get("fixture_class_counts", {}).get("expected_pass"), 3)

        bad_static = run_skillguard("fixture-test", "--manifest", ".agents/skills/skillguard/fixtures/bad_static/fixture-manifest.json")
        self.assert_clean_pass(bad_static)
        self.assertEqual(bad_static.get("fixture_class_counts", {}).get("expected_fail"), 3)

        bad_suite = run_skillguard("fixture-test", "--manifest", ".agents/skills/skillguard/fixtures/bad_suite_stale/fixture-manifest.json")
        self.assert_clean_pass(bad_suite)
        self.assertEqual(bad_suite.get("fixture_class_counts", {}).get("expected_fail"), 4)

    def test_self_check_example_command(self) -> None:
        report = run_skillguard("self-check", "--target", ".agents/skills/skillguard")
        self.assert_clean_pass(report)

    def test_example_document_is_public_safe_and_current(self) -> None:
        self.assertTrue(EXAMPLES.is_file(), f"missing {rel(EXAMPLES)}")
        text = EXAMPLES.read_text(encoding="utf-8")
        for required in ("check-skill", "check-suite", "fixture-test", "self-check", "standard-library"):
            self.assertIn(required, text)
        for pattern in PRIVATE_OR_SECRET_PATTERNS:
            self.assertIsNone(pattern.search(text), pattern.pattern)
        for pattern in UNSAFE_CLAIM_PATTERNS:
            self.assertIsNone(pattern.search(text), pattern.pattern)


def result_payload(result: unittest.TestResult, elapsed_seconds: float) -> dict[str, Any]:
    failure_items = [
        {"test": str(test), "details": details}
        for test, details in list(result.failures) + list(result.errors)
    ]
    decision = "pass" if result.wasSuccessful() else "fail"
    return {
        "schema_version": "skillguard.standard_library_test_result.v1",
        "checked_at": utc_timestamp(),
        "command": "python tests/test_skillguard_local.py",
        "decision": decision,
        "test_count": result.testsRun,
        "failure_count": len(result.failures),
        "error_count": len(result.errors),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "checks": [
            {
                "check_id": "standard-library-local-examples",
                "name": "Local examples and checker command smoke checks",
                "required": True,
                "status": decision,
                "summary": "Ran standard-library unittest checks for single-skill, suite, fixture manifests, self-check, and public-safe example wording.",
            }
        ],
        "evidence": [
            {
                "evidence_id": "standard-library-unittest",
                "kind": "command_output",
                "fresh": True,
                "summary": f"Ran {result.testsRun} unittest checks using the local Python interpreter.",
                "source_path": "tests/test_skillguard_local.py",
            },
            {
                "evidence_id": "examples-readme",
                "kind": "file_inspection",
                "fresh": True,
                "summary": "Checked examples/README.md for local command names and public-safe wording.",
                "source_path": "examples/README.md",
            },
        ],
        "failures": failure_items,
        "blockers": [],
        "skipped_checks": [],
        "residual_risk": [
            "These are local standard-library smoke checks, not packaged CLI, network, release, suite automation, or code-contract checks."
        ],
        "claim_boundary": (
            "This test result covers only the local examples and explicit SkillGuard command invocations run by this script. "
            "It does not prove broad fixture coverage, packaged CLI installation, suite automation, package publication, "
            "release readiness, code-contract validation, external services, or future AI behavior."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local standard-library SkillGuard checks.")
    parser.add_argument("--json-output", help="Optional JSON report output path under the repository root.")
    args = parser.parse_args(argv)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SkillGuardLocalExamplesTest)
    stream = io.StringIO()
    started = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter() - started
    sys.stdout.write(stream.getvalue())

    payload = result_payload(result, elapsed)
    if args.json_output:
        output = (REPO_ROOT / args.json_output).resolve()
        output.relative_to(REPO_ROOT.resolve())
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
