from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_check_manifest, runtime_contract  # noqa: F401
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import RunStoreError, claim_run
from skillguard_v2.step_runtime import (
    StepRuntimeError,
    begin_step,
    record_loop_reentry,
    record_step,
    replay_run,
    resume_run,
)


class RunReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name)
        self.contract = runtime_contract()
        decision = select_routes(self.contract, {"function_ids": ["analyze"]})
        claim = claim_run(
            self.contract,
            {"function_ids": ["analyze"], "write_targets": ["src"], "request": "audit"},
            self.target,
            decision,
            check_manifest=runtime_check_manifest(self.contract),
        )
        self.assertTrue(claim.ok, claim.to_dict())
        self.run_root = claim.run_root

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_resume_rehydrates_only_from_snapshot_and_events(self) -> None:
        begin_step(self.run_root, "step:intake")
        record_step(self.run_root, "step:intake", {"artifact_id": "artifact:intake"})
        first = replay_run(self.run_root).to_dict()
        second = resume_run(self.run_root).to_dict()
        self.assertEqual(first, second)
        self.assertEqual("evidence_submitted", second["step_statuses"]["step:intake"])

    def test_tampered_event_payload_is_detected(self) -> None:
        events = self.run_root / "events.jsonl"
        rows = events.read_text(encoding="utf-8").splitlines()
        row = json.loads(rows[0])
        row["payload"]["claim_scope"] = "forged"
        rows[0] = json.dumps(row, sort_keys=True)
        events.write_text("\n".join(rows) + "\n", encoding="utf-8")
        with self.assertRaises(RunStoreError) as raised:
            replay_run(self.run_root)
        self.assertIn(raised.exception.code, {"event_hash_mismatch", "event_hash_chain_broken"})

    def test_event_sequence_gap_is_detected(self) -> None:
        begin_step(self.run_root, "step:intake")
        events = self.run_root / "events.jsonl"
        rows = events.read_text(encoding="utf-8").splitlines()
        row = json.loads(rows[1])
        row["sequence"] = 3
        rows[1] = json.dumps(row, sort_keys=True)
        events.write_text("\n".join(rows) + "\n", encoding="utf-8")
        with self.assertRaises(RunStoreError) as raised:
            replay_run(self.run_root)
        self.assertEqual("event_sequence_gap", raised.exception.code)

    def test_contract_snapshot_tampering_is_detected(self) -> None:
        path = self.run_root / "contract.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["claim_boundary"] = "forged"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(StepRuntimeError) as raised:
            replay_run(self.run_root)
        self.assertEqual("contract_snapshot_hash_mismatch", raised.exception.code)

    def test_loop_requires_strict_progress_and_has_finite_bound(self) -> None:
        record_loop_reentry(self.run_root, "route:analyze", "receipt:1")
        with self.assertRaises(StepRuntimeError) as unchanged:
            record_loop_reentry(self.run_root, "route:analyze", "receipt:1")
        self.assertEqual("loop_progress_unchanged", unchanged.exception.code)

        # A fresh run proves the independent finite-bound branch.
        other_target = self.target / "other"
        decision = select_routes(self.contract, {"function_ids": ["analyze"]})
        other = claim_run(
            self.contract,
            {"function_ids": ["analyze"], "write_targets": ["src"], "request": "other"},
            other_target,
            decision,
            check_manifest=runtime_check_manifest(self.contract),
        )
        record_loop_reentry(other.run_root, "route:analyze", "receipt:1")
        record_loop_reentry(other.run_root, "route:analyze", "receipt:2")
        with self.assertRaises(StepRuntimeError) as exceeded:
            record_loop_reentry(other.run_root, "route:analyze", "receipt:3")
        self.assertEqual("loop_reentry_bound_exceeded", exceeded.exception.code)
        self.assertEqual("blocked", replay_run(other.run_root).status)


if __name__ == "__main__":
    unittest.main()
