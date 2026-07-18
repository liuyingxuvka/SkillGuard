from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.contract_compiler import canonical_hash  # noqa: E402
from skillguard_v2.portfolio import (  # noqa: E402
    audit_portfolio,
    _production_revalidation_binding_shape_findings,
    _load_portfolio_production_revalidation_bindings,
    _verify_shared_portfolio_installation_context,
    replay_portfolio_production_revalidation_binding,
)
from skillguard_v2.portfolio_runner import (  # noqa: E402
    _consume_installed_parity_currentness,
    assemble_portfolio_attempt,
    capture_portfolio_production_revalidation_binding,
)
from skillguard_v2.portfolio_records import (  # noqa: E402
    PortfolioRecordError,
    write_hash_bound_json,
)


HASH = "A" * 64
WIRE_HASH = "sha256:" + "a" * 64
REF = f"record:production/example.json@{HASH}"


def _binding() -> dict[str, object]:
    binding: dict[str, object] = {
        "schema_version": "skillguard.portfolio_production_revalidation_binding.v1",
        "member_skill_id": "member-skill",
        "member_skill_path": ".",
        "source_fingerprint": HASH,
        "member_contract_hash": HASH,
        "member_manifest_hash": HASH,
        "run_root_token": "runs/member",
        "target_root_token": "targets/member",
        "run_id": "run:member-production",
        "target_skill_id": "member-skill",
        "depth_profile_hash": HASH,
        "native_owner_id": "owner:member",
        "native_route_id": "route:member-production",
        "native_check_id": "check:member-terminal",
        "evidence_domain": "scheduled_production",
        "depth_receipt": {
            "ref": REF,
            "receipt_id": "depth:member",
            "receipt_hash": HASH,
            "status": "EXECUTION_DEPTH_PASS",
            "evidence_domain": "scheduled_production",
        },
        "enforced_closure": {
            "ref": REF,
            "receipt_id": "closure:member",
            "receipt_hash": HASH,
            "profile": "enforced",
            "status": "closed",
            "consumed_receipt_ids": ["depth:member", "terminal:member"],
        },
        "native_terminal": {
            "ref": REF,
            "receipt_id": "terminal:member",
            "receipt_hash": HASH,
            "closure_profile": "enforced",
            "closure_disposition": "terminal_completion",
            "evidence_domain": "scheduled_production",
            "conditional": True,
            "native_route_id": "route:member-production",
            "branch_id": "member-noop",
        },
        "installation_identity": {
            "scheduler_or_trigger_id": "schedule:member",
            "scheduled_execution_id": "scheduled-execution:member",
            "installation_receipt_id": "installation:member",
            "installation_receipt_hash": HASH,
            "installation_receipt_root_ref": {
                "path_token": "active_skill_root",
                "relative_path": ".sg-runtime/installation",
            },
            "installed_runtime_fingerprint": HASH,
            "transaction_id": "install-0123456789abcdef0123456789abcdef",
            "stage_verification_hash": HASH,
            "post_activation_smoke_hash": HASH,
            "post_activation_member_comparisons_hash": HASH,
            "current_installed_smoke_hash": HASH,
            "current_installed_smoke_command_fingerprint": HASH,
            "current_installed_smoke_environment_fingerprint": HASH,
            "rollback_disposition": "not_required",
        },
        "captured_at": "2026-07-13T00:00:00Z",
        "claim_boundary": "fixture shape only",
    }
    binding["binding_hash"] = canonical_hash(binding)
    return binding


class PortfolioProductionRevalidationTests(unittest.TestCase):
    def test_installed_parity_close_replays_owner_receipt_without_reissuing(self) -> None:
        binding = {
            "ref": REF,
            "receipt_id": WIRE_HASH,
            "receipt_hash": "sha256:" + "b" * 64,
        }
        receipt = {
            "status": "current",
            "receipt_id": binding["receipt_id"],
            "receipt_hash": binding["receipt_hash"],
            "blockers": [],
        }
        preparation = {
            "target_kind": "single_skill",
            "installed_parity_receipt": binding,
            "guard_runtime": {
                "portfolio_projection_hash": WIRE_HASH,
            },
        }
        with patch(
            "skillguard_v2.portfolio_runner._load_json_ref",
            return_value=receipt,
        ), patch(
            "skillguard_v2.portfolio_runner.replay_installed_content_parity_currentness",
            return_value=[],
        ) as replay, patch(
            "skillguard_v2.portfolio_runner.write_hash_bound_json"
        ) as writer:
            result = _consume_installed_parity_currentness(
                receipt=preparation,
                identity={"skill_id": "member-skill"},
                repository_root=Path("repository"),
                installed_target_root=Path("installed"),
                workspace_root=Path("workspace"),
            )
        self.assertEqual(binding, result)
        self.assertEqual(1, replay.call_count)
        writer.assert_not_called()

    def test_source_only_capability_evidence_has_no_production_authority(self) -> None:
        normalized, findings, context = _load_portfolio_production_revalidation_bindings(
            [],
            target_identity={"member_identities": []},
            target_repository_root=Path("."),
            evidence_root=Path("."),
        )
        self.assertEqual([], normalized)
        self.assertIsNone(context)
        self.assertEqual(
            ["graduation_production_revalidation_bindings_missing"],
            [finding["code"] for finding in findings],
        )

    def test_complete_typed_binding_shape_is_admitted_for_replay(self) -> None:
        self.assertEqual(
            [],
            _production_revalidation_binding_shape_findings(
                _binding(), expected_member_skill_id="member-skill"
            ),
        )

    def test_nonconditional_terminal_may_have_no_branch_but_conditional_must_name_one(self) -> None:
        nonconditional = _binding()
        nonconditional["native_terminal"].update(
            {"conditional": False, "branch_id": ""}
        )
        nonconditional["binding_hash"] = canonical_hash(
            {
                key: value
                for key, value in nonconditional.items()
                if key != "binding_hash"
            }
        )
        self.assertEqual(
            [],
            _production_revalidation_binding_shape_findings(
                nonconditional, expected_member_skill_id="member-skill"
            ),
        )

        conditional = _binding()
        conditional["native_terminal"]["branch_id"] = ""
        conditional["binding_hash"] = canonical_hash(
            {
                key: value
                for key, value in conditional.items()
                if key != "binding_hash"
            }
        )
        self.assertIn(
            "portfolio_production_conditional_branch_missing",
            {
                finding["code"]
                for finding in _production_revalidation_binding_shape_findings(
                    conditional, expected_member_skill_id="member-skill"
                )
            },
        )

    def test_known_bad_domains_member_and_nonterminal_closure_block_specifically(self) -> None:
        cases = {
            "fixture_as_production": (
                lambda row: row.update({"evidence_domain": "fixture_validation"}),
                "portfolio_production_fixture_as_production",
            ),
            "capability_as_production": (
                lambda row: row.update({"evidence_domain": "capability_validation"}),
                "portfolio_production_capability_as_production",
            ),
            "wrong_member": (
                lambda row: row.update({"member_skill_id": "another-member"}),
                "portfolio_production_wrong_member",
            ),
            "non_enforced_closure": (
                lambda row: row["enforced_closure"].update({"profile": "optional"}),
                "portfolio_production_enforced_closure_required",
            ),
            "nonterminal_authorization": (
                lambda row: row["native_terminal"].update(
                    {
                        "closure_profile": "optional",
                        "closure_disposition": "non_terminal_authorization",
                    }
                ),
                "portfolio_production_nonterminal_closure_cannot_promote",
            ),
            "nonterminal_validation": (
                lambda row: row["native_terminal"].update(
                    {
                        "closure_profile": "optional",
                        "closure_disposition": "non_terminal_validation",
                    }
                ),
                "portfolio_production_terminal_completion_required",
            ),
        }
        for name, (mutate, expected) in cases.items():
            with self.subTest(name=name):
                row = copy.deepcopy(_binding())
                mutate(row)
                row["binding_hash"] = canonical_hash(
                    {key: value for key, value in row.items() if key != "binding_hash"}
                )
                codes = {
                    finding["code"]
                    for finding in _production_revalidation_binding_shape_findings(
                        row, expected_member_skill_id="member-skill"
                    )
                }
                self.assertIn(expected, codes)

    def test_parent_or_foreign_member_binding_cannot_prove_expected_member(self) -> None:
        for supplied_member in ("suite-parent", "member-two"):
            with self.subTest(supplied_member=supplied_member):
                binding = _binding()
                binding["member_skill_id"] = supplied_member
                binding["target_skill_id"] = supplied_member
                binding["binding_hash"] = canonical_hash(
                    {
                        key: value
                        for key, value in binding.items()
                        if key != "binding_hash"
                    }
                )
                findings = replay_portfolio_production_revalidation_binding(
                    binding,
                    expected_member_skill_id="member-one",
                    expected_member_skill_path="member-one",
                    expected_source_fingerprint=HASH,
                    expected_member_contract_hash=HASH,
                    expected_member_manifest_hash=HASH,
                    member_repository_root=Path("repository/member-one"),
                    workspace_root=Path("workspace"),
                )
                self.assertIn(
                    "portfolio_production_wrong_member",
                    {finding["code"] for finding in findings},
                )

    def test_missing_terminal_or_installation_blocks_instead_of_using_capability_jobs(self) -> None:
        for field, expected in (
            ("native_terminal", "portfolio_production_native_terminal_missing"),
            (
                "installation_identity",
                "portfolio_production_installation_identity_missing",
            ),
        ):
            with self.subTest(field=field):
                row = _binding()
                row.pop(field)
                row["binding_hash"] = canonical_hash(
                    {key: value for key, value in row.items() if key != "binding_hash"}
                )
                codes = {
                    finding["code"]
                    for finding in _production_revalidation_binding_shape_findings(
                        row, expected_member_skill_id="member-skill"
                    )
                }
                self.assertIn(expected, codes)

    def test_suite_replays_one_shared_installation_context_once(self) -> None:
        calls: list[dict[str, object]] = []

        context = SimpleNamespace(
            receipt_hash=HASH,
            receipt={
                "transaction_id": "install-0123456789abcdef0123456789abcdef",
                "stage_verification_hash": HASH,
                "post_activation_smoke_hash": HASH,
                "post_activation_member_comparisons_hash": HASH,
                "current_installed_smoke_hash": HASH,
                "current_installed_smoke_command_fingerprint": HASH,
                "current_installed_smoke_environment_fingerprint": HASH,
                "rollback_disposition": "not_required",
            },
        )

        def verifier(identity):
            calls.append(dict(identity))
            return context

        second = copy.deepcopy(_binding())
        second["member_skill_id"] = "second-member"
        with patch(
            "skillguard_v2.installation_receipt.validate_verified_installation_context",
            side_effect=lambda value: value,
        ):
            observed_context = _verify_shared_portfolio_installation_context(
                [_binding(), second], verifier=verifier
            )
        self.assertEqual(1, len(calls))
        self.assertIs(context, observed_context)

    def test_suite_blocks_mixed_installation_identities_before_member_replay(self) -> None:
        second = copy.deepcopy(_binding())
        second["installation_identity"]["installation_receipt_hash"] = "B" * 64
        with self.assertRaises(PortfolioRecordError) as raised:
            _verify_shared_portfolio_installation_context([_binding(), second])
        self.assertEqual(
            "portfolio_production_multiple_installation_identities",
            raised.exception.code,
        )

    def test_later_currentness_rejects_current_smoke_identity_drift(self) -> None:
        context = SimpleNamespace(
            receipt_hash=HASH,
            receipt={
                "transaction_id": "install-0123456789abcdef0123456789abcdef",
                "stage_verification_hash": HASH,
                "post_activation_smoke_hash": HASH,
                "post_activation_member_comparisons_hash": HASH,
                "current_installed_smoke_hash": "B" * 64,
                "current_installed_smoke_command_fingerprint": HASH,
                "current_installed_smoke_environment_fingerprint": HASH,
                "rollback_disposition": "not_required",
            },
        )
        with patch(
            "skillguard_v2.installation_receipt.validate_verified_installation_context",
            return_value=context,
        ), patch(
            "skillguard_v2.installation_receipt.verify_scheduled_production_installation_identity",
            return_value={},
        ), self.assertRaises(PortfolioRecordError) as raised:
            _verify_shared_portfolio_installation_context(
                [_binding()], verified_installation_context=context
            )
        self.assertEqual(
            "portfolio_production_installation_current_installed_smoke_hash_mismatch",
            raised.exception.code,
        )

    def test_suite_requires_one_exact_production_binding_per_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            repository = workspace / "repository"
            (repository / "member-one").mkdir(parents=True)
            (repository / "member-two").mkdir(parents=True)
            binding = _binding()
            binding["member_skill_id"] = "member-one"
            binding["member_skill_path"] = "member-one"
            binding["target_skill_id"] = "member-one"
            binding["binding_hash"] = canonical_hash(
                {
                    key: value
                    for key, value in binding.items()
                    if key != "binding_hash"
                }
            )
            _path, binding_ref = write_hash_bound_json(
                "bindings/member-one.json", binding, workspace
            )
            identity = {
                "member_identities": [
                    {
                        "member_skill_id": member_id,
                        "skill_path": member_id,
                        "source_fingerprint": HASH,
                        "contract_hash": HASH,
                        "manifest_hash": HASH,
                    }
                    for member_id in ("member-one", "member-two")
                ]
            }
            with patch(
                "skillguard_v2.portfolio._verify_shared_portfolio_installation_context",
                return_value=object(),
            ), patch(
                "skillguard_v2.portfolio.replay_portfolio_production_revalidation_binding",
                return_value=[],
            ):
                normalized, findings, context = (
                    _load_portfolio_production_revalidation_bindings(
                        [binding_ref],
                        target_identity=identity,
                        target_repository_root=repository,
                        evidence_root=workspace,
                    )
                )
            self.assertEqual(["member-one"], [row["member_skill_id"] for row in normalized])
            self.assertIsNotNone(context)
            self.assertIn(
                "graduation_production_member_binding_missing",
                {row["code"] for row in findings if row["skill_id"] == "member-two"},
            )

    def test_audit_reuses_one_sealed_installation_context_holder(self) -> None:
        guard = {
            "runtime_id": "skillguard-v2",
            "file_count": 1,
            "source_hash": HASH,
            "portfolio_projection_hash": WIRE_HASH,
        }
        registry = {
            "active_guard": guard,
            "registry_id": "registry:one",
            "scope_manifest_id": "scope:one",
            "scope_manifest_hash": HASH,
            "entries": [
                {
                    "skill_id": "first",
                    "order": 1,
                    "lifecycle": "active_owned",
                    "capability_inventory_status": "current",
                },
                {
                    "skill_id": "second",
                    "order": 2,
                    "lifecycle": "active_owned",
                    "capability_inventory_status": "current",
                },
            ],
            "guard_change_history": [],
        }
        sentinel = object()
        holder_ids: list[int] = []

        def current(_entry, _guard, *_args, **kwargs):
            holder = kwargs["installation_context_holder"]
            holder_ids.append(id(holder))
            if not holder:
                holder.append(sentinel)
            self.assertIs(sentinel, holder[0])
            return True

        with patch(
            "skillguard_v2.portfolio.validate_registry", return_value=[]
        ), patch(
            "skillguard_v2.portfolio.entry_is_current", side_effect=current
        ):
            report = audit_portfolio(
                registry,
                actual_guard=guard,
                target_repository_roots={
                    "first": Path("first"),
                    "second": Path("second"),
                },
            )
        self.assertEqual("current", report["status"])
        self.assertEqual(1, len(set(holder_ids)))

    def test_assembly_injects_exact_loaded_context_into_graduation(self) -> None:
        guard = {
            "runtime_id": "skillguard-v2",
            "file_count": 1,
            "source_hash": HASH,
            "portfolio_projection_hash": WIRE_HASH,
        }
        preparation = {
            "preparation_id": "preparation:one",
            "receipt_id": "preparation:one",
            "receipt_hash": HASH,
            "guard_runtime": guard,
            "registry_id": "registry:one",
            "registry_revision": 1,
            "registry_hash": HASH,
            "skill_id": "member-skill",
            "target_kind": "single_skill",
            "skill_paths": ["."],
            "job_plan_ref": REF,
            "job_plan_hash": HASH,
            "job_specs": [],
            "target_identity_receipt": {"ref": REF, "receipt_id": "identity:one", "receipt_hash": HASH},
        }
        identity = {
            "source_fingerprint": HASH,
            "contract_hash": HASH,
            "version": "1.0.0",
        }
        full_receipt = {
            "receipt_id": "portfolio-run-one",
            "receipt_hash": HASH,
            "completed_at": "2026-07-13T00:00:00Z",
        }
        context = object()
        observed: dict[str, object] = {}

        def graduate(*_args, **kwargs):
            observed["context"] = kwargs["verified_installation_context"]
            observed["has_foreign_roots"] = (
                "portfolio_target_repository_roots" in kwargs
            )
            return {"status": "current"}, {}, {
                "receipt_id": "graduation:one",
                "receipt_hash": HASH,
            }

        registry = {
            "registry_id": "registry:one",
            "revision": 1,
            "registry_hash": HASH,
            "scope_manifest_id": "scope:one",
            "scope_manifest_hash": HASH,
        }
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            repository = workspace / "repository"
            repository.mkdir()
            with patch(
                "skillguard_v2.portfolio_runner._preparation_current",
                return_value=preparation,
            ), patch(
                "skillguard_v2.portfolio_runner._load_json_ref", return_value={}
            ), patch(
                "skillguard_v2.portfolio_runner.current_guard", return_value=guard
            ), patch(
                "skillguard_v2.portfolio_runner._identity_current", return_value=identity
            ), patch(
                "skillguard_v2.portfolio_runner._load_portfolio_production_revalidation_bindings",
                return_value=([{"member_skill_id": "member-skill", "binding_ref": REF, "binding_hash": HASH}], [], context),
            ) as load_bindings, patch(
                "skillguard_v2.portfolio_runner._validate_execution_result", return_value=[]
            ), patch(
                "skillguard_v2.portfolio_runner._consume_installed_parity_currentness", return_value={}
            ), patch(
                "skillguard_v2.portfolio_runner.assemble_full_run_receipt",
                return_value=(full_receipt, []),
            ), patch(
                "skillguard_v2.portfolio_runner.graduate_portfolio_target",
                side_effect=graduate,
            ), patch(
                "skillguard_v2.portfolio_runner.write_hash_bound_json",
                side_effect=lambda relative, _payload, _root: (
                    workspace / str(relative),
                    REF,
                ),
            ):
                result = assemble_portfolio_attempt(
                    preparation_ref=REF,
                    execution_ref=REF,
                    registry=registry,
                    repository_root=repository,
                    workspace_root=workspace,
                    production_revalidation_refs=[REF],
                )
        self.assertEqual("assembled", result["status"])
        self.assertEqual(1, load_bindings.call_count)
        self.assertIs(context, observed["context"])
        self.assertFalse(observed["has_foreign_roots"])

    def test_capture_public_api_writes_only_verifier_derived_binding(self) -> None:
        identity = {
            "member_identities": [
                {
                    "member_skill_id": "member-skill",
                    "skill_path": ".",
                    "source_fingerprint": HASH,
                    "contract_hash": HASH,
                    "manifest_hash": HASH,
                }
            ]
        }
        binding = _binding()
        sealed_context = object()
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            repository = workspace / "repository"
            repository.mkdir()
            with patch(
                "skillguard_v2.portfolio_runner.current_guard", return_value={}
            ), patch(
                "skillguard_v2.portfolio_runner.derive_target_identity",
                return_value=(identity, []),
            ), patch(
                "skillguard_v2.portfolio_runner.validate_verified_installation_context",
                return_value=sealed_context,
            ) as validate_context, patch(
                "skillguard_v2.portfolio_runner.build_portfolio_production_revalidation_binding",
                return_value=binding,
            ) as build_binding, patch(
                "skillguard_v2.portfolio_runner.write_hash_bound_json",
                return_value=(workspace / "binding.json", REF),
            ):
                result = capture_portfolio_production_revalidation_binding(
                    member_skill_id="member-skill",
                    member_skill_path=".",
                    repository_root=repository,
                    run_root=workspace / "run",
                    target_root=workspace / "target",
                    workspace_root=workspace,
                    closure_receipt_id="closure:member",
                    verified_installation_context=sealed_context,
                )
        self.assertEqual("captured", result["status"])
        self.assertEqual(binding["binding_hash"], result["binding_hash"])
        validate_context.assert_called_once_with(sealed_context)
        self.assertIs(
            sealed_context,
            build_binding.call_args.kwargs["verified_installation_context"],
        )


if __name__ == "__main__":
    unittest.main()
