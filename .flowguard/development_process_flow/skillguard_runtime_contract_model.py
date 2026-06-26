"""FlowGuard model for the SkillGuard runtime-contract upgrade."""

from __future__ import annotations

from flowguard import (
    PROCESS_ARTIFACT_CODE,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_EVIDENCE_PASSED,
    DevelopmentProcessPlan,
    FreshnessRule,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ProofArtifactRef,
    ValidationRequirement,
    review_development_process_flow,
)


def proof_artifact(artifact_id: str, result_path: str, *covered: str) -> ProofArtifactRef:
    return ProofArtifactRef(
        artifact_id,
        result_status=PROCESS_EVIDENCE_PASSED,
        exit_code=0,
        result_path=result_path,
        artifact_fingerprints={result_path: "sha256:current"},
        covered_obligation_ids=covered,
    )


def runtime_contract_plan() -> DevelopmentProcessPlan:
    artifacts = (
        ProcessArtifact("openspec.upgrade-skillguard-foreman", PROCESS_ARTIFACT_REQUIREMENT, "2"),
        ProcessArtifact(
            "model.runtime-contract-lifecycle",
            PROCESS_ARTIFACT_MODEL,
            "2",
            upstream_artifact_ids=("openspec.upgrade-skillguard-foreman",),
        ),
        ProcessArtifact(
            "code.checker-engine-runtime-contract",
            PROCESS_ARTIFACT_CODE,
            "2",
            upstream_artifact_ids=("openspec.upgrade-skillguard-foreman", "model.runtime-contract-lifecycle"),
        ),
        ProcessArtifact(
            "tests.runtime-contract-fixtures",
            PROCESS_ARTIFACT_TEST,
            "2",
            upstream_artifact_ids=("openspec.upgrade-skillguard-foreman", "code.checker-engine-runtime-contract"),
        ),
        ProcessArtifact(
            "docs.runtime-contract-public-boundary",
            PROCESS_ARTIFACT_REQUIREMENT,
            "2",
            upstream_artifact_ids=("openspec.upgrade-skillguard-foreman", "code.checker-engine-runtime-contract"),
        ),
    )
    evidence = (
        ProcessEvidence(
            "syntax-py-compile",
            evidence_kind="syntax",
            producer_route="development_process_flow",
            status=PROCESS_EVIDENCE_PASSED,
            covers_artifacts=("code.checker-engine-runtime-contract",),
            covered_versions={"code.checker-engine-runtime-contract": "2"},
            validation_requirement_ids=("syntax-current",),
            produced_by_action_id="run-syntax-check",
            command="python -m py_compile .agents/skills/skillguard/scripts/checker_engine.py",
            proof_artifact=proof_artifact("artifact:syntax", ".flowguard/runtime_contract_py_compile.json", "syntax-current"),
        ),
        ProcessEvidence(
            "runtime-contract-fixtures-pass",
            evidence_kind="fixture",
            producer_route="test_mesh_maintenance",
            status=PROCESS_EVIDENCE_PASSED,
            covers_artifacts=("code.checker-engine-runtime-contract", "tests.runtime-contract-fixtures"),
            verifier_artifacts=("tests.runtime-contract-fixtures",),
            covered_versions={"code.checker-engine-runtime-contract": "2", "tests.runtime-contract-fixtures": "2"},
            validation_requirement_ids=("runtime-fixtures-current",),
            produced_by_action_id="run-runtime-fixtures",
            command="python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/runtime_contract/fixture-manifest.json",
            proof_artifact=proof_artifact(
                "artifact:runtime-fixtures",
                ".agents/skills/skillguard/fixtures/evidence_outputs/fixture_test_runtime_contract_current.json",
                "runtime-fixtures-current",
            ),
        ),
        ProcessEvidence(
            "standard-library-tests-pass",
            evidence_kind="unit",
            producer_route="test_mesh_maintenance",
            status=PROCESS_EVIDENCE_PASSED,
            covers_artifacts=(
                "code.checker-engine-runtime-contract",
                "tests.runtime-contract-fixtures",
                "docs.runtime-contract-public-boundary",
            ),
            verifier_artifacts=("tests.runtime-contract-fixtures",),
            covered_versions={
                "code.checker-engine-runtime-contract": "2",
                "tests.runtime-contract-fixtures": "2",
                "docs.runtime-contract-public-boundary": "2",
            },
            validation_requirement_ids=("standard-library-tests-current",),
            produced_by_action_id="run-standard-library-tests",
            command="python tests/test_skillguard_local.py --json-output .agents/skills/skillguard/fixtures/evidence_outputs/standard_library_tests_current.json",
            proof_artifact=proof_artifact(
                "artifact:standard-library-tests",
                ".agents/skills/skillguard/fixtures/evidence_outputs/standard_library_tests_current.json",
                "standard-library-tests-current",
            ),
        ),
        ProcessEvidence(
            "self-check-pass",
            evidence_kind="self-check",
            producer_route="development_process_flow",
            status=PROCESS_EVIDENCE_PASSED,
            covers_artifacts=("docs.runtime-contract-public-boundary", "code.checker-engine-runtime-contract"),
            covered_versions={"docs.runtime-contract-public-boundary": "2", "code.checker-engine-runtime-contract": "2"},
            validation_requirement_ids=("self-check-current",),
            produced_by_action_id="run-self-check",
            command="python .agents/skills/skillguard/scripts/skillguard.py self-check --target .agents/skills/skillguard",
            proof_artifact=proof_artifact(
                "artifact:self-check",
                ".agents/skills/skillguard/fixtures/evidence_outputs/self_check_current.json",
                "self-check-current",
            ),
        ),
    )
    return DevelopmentProcessPlan(
        "skillguard-runtime-contract-upgrade",
        require_proof_artifacts=True,
        artifacts=artifacts,
        actions=(
            ProcessAction("update-openspec-contract", writes_artifacts=("openspec.upgrade-skillguard-foreman",)),
            ProcessAction("model-runtime-contract-lifecycle", writes_artifacts=("model.runtime-contract-lifecycle",)),
            ProcessAction("edit-runtime-contract-code", writes_artifacts=("code.checker-engine-runtime-contract",)),
            ProcessAction("add-runtime-contract-fixtures", writes_artifacts=("tests.runtime-contract-fixtures",)),
            ProcessAction("update-public-docs", writes_artifacts=("docs.runtime-contract-public-boundary",)),
            ProcessAction("run-syntax-check", produced_evidence_ids=("syntax-py-compile",)),
            ProcessAction("run-runtime-fixtures", produced_evidence_ids=("runtime-contract-fixtures-pass",)),
            ProcessAction("run-standard-library-tests", produced_evidence_ids=("standard-library-tests-pass",)),
            ProcessAction("run-self-check", produced_evidence_ids=("self-check-pass",)),
            ProcessAction(
                "claim-done",
                action_type="claim_done",
                required_validation_ids=(
                    "syntax-current",
                    "runtime-fixtures-current",
                    "standard-library-tests-current",
                    "self-check-current",
                ),
            ),
        ),
        evidence=evidence,
        validation_requirements=(
            ValidationRequirement(
                "syntax-current",
                required_artifact_ids=("code.checker-engine-runtime-contract",),
                required_evidence_kinds=("syntax",),
                evidence_ids=("syntax-py-compile",),
            ),
            ValidationRequirement(
                "runtime-fixtures-current",
                required_artifact_ids=("code.checker-engine-runtime-contract", "tests.runtime-contract-fixtures"),
                required_evidence_kinds=("fixture",),
                evidence_ids=("runtime-contract-fixtures-pass",),
                v_model_pair=True,
            ),
            ValidationRequirement(
                "standard-library-tests-current",
                required_artifact_ids=(
                    "code.checker-engine-runtime-contract",
                    "tests.runtime-contract-fixtures",
                    "docs.runtime-contract-public-boundary",
                ),
                required_evidence_kinds=("unit",),
                evidence_ids=("standard-library-tests-pass",),
                v_model_pair=True,
            ),
            ValidationRequirement(
                "self-check-current",
                required_artifact_ids=("docs.runtime-contract-public-boundary", "code.checker-engine-runtime-contract"),
                required_evidence_kinds=("self-check",),
                evidence_ids=("self-check-pass",),
            ),
        ),
        freshness_rules=(
            FreshnessRule(
                "openspec-invalidates-runtime-model-code-tests-docs",
                upstream_artifact_id="openspec.upgrade-skillguard-foreman",
                invalidates_artifact_ids=(
                    "model.runtime-contract-lifecycle",
                    "code.checker-engine-runtime-contract",
                    "tests.runtime-contract-fixtures",
                    "docs.runtime-contract-public-boundary",
                ),
            ),
            FreshnessRule(
                "model-invalidates-runtime-code",
                upstream_artifact_id="model.runtime-contract-lifecycle",
                invalidates_artifact_ids=("code.checker-engine-runtime-contract",),
            ),
            FreshnessRule(
                "code-invalidates-runtime-tests-docs",
                upstream_artifact_id="code.checker-engine-runtime-contract",
                invalidates_artifact_ids=("tests.runtime-contract-fixtures", "docs.runtime-contract-public-boundary"),
            ),
        ),
    )


def main() -> int:
    report = review_development_process_flow(runtime_contract_plan())
    print(report.format_text(max_findings=20))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
