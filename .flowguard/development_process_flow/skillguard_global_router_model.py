"""FlowGuard development-process model for SkillGuard global router work."""

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


def global_router_plan() -> DevelopmentProcessPlan:
    artifacts = (
        ProcessArtifact("openspec.add-skillguard-global-router", PROCESS_ARTIFACT_REQUIREMENT, "1"),
        ProcessArtifact(
            "model.global-router-lifecycle",
            PROCESS_ARTIFACT_MODEL,
            "1",
            upstream_artifact_ids=("openspec.add-skillguard-global-router",),
        ),
        ProcessArtifact(
            "code.global-router-commands",
            PROCESS_ARTIFACT_CODE,
            "1",
            upstream_artifact_ids=("openspec.add-skillguard-global-router", "model.global-router-lifecycle"),
        ),
        ProcessArtifact(
            "skill.skillguard-global-router",
            PROCESS_ARTIFACT_REQUIREMENT,
            "1",
            upstream_artifact_ids=("openspec.add-skillguard-global-router", "code.global-router-commands"),
        ),
        ProcessArtifact(
            "tests.global-router-fixtures",
            PROCESS_ARTIFACT_TEST,
            "1",
            upstream_artifact_ids=("code.global-router-commands", "skill.skillguard-global-router"),
        ),
        ProcessArtifact(
            "docs.global-router-boundary",
            PROCESS_ARTIFACT_REQUIREMENT,
            "1",
            upstream_artifact_ids=("code.global-router-commands", "skill.skillguard-global-router"),
        ),
    )
    evidence = (
        ProcessEvidence(
            "openspec-global-router-valid",
            evidence_kind="openspec",
            producer_route="development_process_flow",
            status=PROCESS_EVIDENCE_PASSED,
            covers_artifacts=("openspec.add-skillguard-global-router",),
            covered_versions={"openspec.add-skillguard-global-router": "1"},
            validation_requirement_ids=("openspec-valid-current",),
            produced_by_action_id="validate-openspec",
            command="openspec validate add-skillguard-global-router",
            proof_artifact=proof_artifact(
                "artifact:openspec-valid",
                "../openspec/changes/add-skillguard-global-router/verification-contract.yaml",
                "openspec-valid-current",
            ),
        ),
        ProcessEvidence(
            "global-router-command-surface",
            evidence_kind="command-surface",
            producer_route="development_process_flow",
            status=PROCESS_EVIDENCE_PASSED,
            covers_artifacts=("code.global-router-commands",),
            covered_versions={"code.global-router-commands": "1"},
            validation_requirement_ids=("commands-current",),
            produced_by_action_id="run-command-surface",
            command="python .agents/skills/skillguard/scripts/skillguard.py commands",
            proof_artifact=proof_artifact(
                "artifact:commands",
                ".agents/skills/skillguard/fixtures/evidence_outputs/command_surface_current.json",
                "commands-current",
            ),
        ),
        ProcessEvidence(
            "global-router-fixtures-pass",
            evidence_kind="fixture",
            producer_route="test_mesh_maintenance",
            status=PROCESS_EVIDENCE_PASSED,
            covers_artifacts=("code.global-router-commands", "tests.global-router-fixtures"),
            verifier_artifacts=("tests.global-router-fixtures",),
            covered_versions={"code.global-router-commands": "1", "tests.global-router-fixtures": "1"},
            validation_requirement_ids=("fixtures-current",),
            produced_by_action_id="run-global-router-fixtures",
            command="python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/global_router/fixture-manifest.json",
            proof_artifact=proof_artifact(
                "artifact:global-fixtures",
                ".agents/skills/skillguard/fixtures/evidence_outputs/fixture_test_global_router_current.json",
                "fixtures-current",
            ),
        ),
        ProcessEvidence(
            "global-router-tests-pass",
            evidence_kind="unit",
            producer_route="test_mesh_maintenance",
            status=PROCESS_EVIDENCE_PASSED,
            covers_artifacts=(
                "code.global-router-commands",
                "skill.skillguard-global-router",
                "tests.global-router-fixtures",
                "docs.global-router-boundary",
            ),
            verifier_artifacts=("tests.global-router-fixtures",),
            covered_versions={
                "code.global-router-commands": "1",
                "skill.skillguard-global-router": "1",
                "tests.global-router-fixtures": "1",
                "docs.global-router-boundary": "1",
            },
            validation_requirement_ids=("tests-current",),
            produced_by_action_id="run-standard-library-tests",
            command="python tests/test_skillguard_local.py --json-output .agents/skills/skillguard/fixtures/evidence_outputs/standard_library_tests_current.json",
            proof_artifact=proof_artifact(
                "artifact:standard-tests",
                ".agents/skills/skillguard/fixtures/evidence_outputs/standard_library_tests_current.json",
                "tests-current",
            ),
        ),
    )
    return DevelopmentProcessPlan(
        "skillguard-global-router",
        require_proof_artifacts=True,
        artifacts=artifacts,
        actions=(
            ProcessAction("validate-openspec", produced_evidence_ids=("openspec-global-router-valid",)),
            ProcessAction("model-global-router-lifecycle", writes_artifacts=("model.global-router-lifecycle",)),
            ProcessAction("edit-global-router-code", writes_artifacts=("code.global-router-commands",)),
            ProcessAction("add-router-skill", writes_artifacts=("skill.skillguard-global-router",)),
            ProcessAction("add-global-router-fixtures", writes_artifacts=("tests.global-router-fixtures",)),
            ProcessAction("update-global-router-docs", writes_artifacts=("docs.global-router-boundary",)),
            ProcessAction("run-command-surface", produced_evidence_ids=("global-router-command-surface",)),
            ProcessAction("run-global-router-fixtures", produced_evidence_ids=("global-router-fixtures-pass",)),
            ProcessAction("run-standard-library-tests", produced_evidence_ids=("global-router-tests-pass",)),
            ProcessAction(
                "claim-done",
                action_type="claim_done",
                required_validation_ids=(
                    "openspec-valid-current",
                    "commands-current",
                    "fixtures-current",
                    "tests-current",
                ),
            ),
        ),
        evidence=evidence,
        validation_requirements=(
            ValidationRequirement(
                "openspec-valid-current",
                required_artifact_ids=("openspec.add-skillguard-global-router",),
                required_evidence_kinds=("openspec",),
                evidence_ids=("openspec-global-router-valid",),
            ),
            ValidationRequirement(
                "commands-current",
                required_artifact_ids=("code.global-router-commands",),
                required_evidence_kinds=("command-surface",),
                evidence_ids=("global-router-command-surface",),
            ),
            ValidationRequirement(
                "fixtures-current",
                required_artifact_ids=("code.global-router-commands", "tests.global-router-fixtures"),
                required_evidence_kinds=("fixture",),
                evidence_ids=("global-router-fixtures-pass",),
                v_model_pair=True,
            ),
            ValidationRequirement(
                "tests-current",
                required_artifact_ids=(
                    "code.global-router-commands",
                    "skill.skillguard-global-router",
                    "tests.global-router-fixtures",
                    "docs.global-router-boundary",
                ),
                required_evidence_kinds=("unit",),
                evidence_ids=("global-router-tests-pass",),
                v_model_pair=True,
            ),
        ),
        freshness_rules=(
            FreshnessRule(
                "openspec-invalidates-model-code-skill-tests-docs",
                upstream_artifact_id="openspec.add-skillguard-global-router",
                invalidates_artifact_ids=(
                    "model.global-router-lifecycle",
                    "code.global-router-commands",
                    "skill.skillguard-global-router",
                    "tests.global-router-fixtures",
                    "docs.global-router-boundary",
                ),
            ),
            FreshnessRule(
                "global-router-code-invalidates-skill-tests-docs",
                upstream_artifact_id="code.global-router-commands",
                invalidates_artifact_ids=(
                    "skill.skillguard-global-router",
                    "tests.global-router-fixtures",
                    "docs.global-router-boundary",
                ),
            ),
            FreshnessRule(
                "model-invalidates-global-router-code",
                upstream_artifact_id="model.global-router-lifecycle",
                invalidates_artifact_ids=("code.global-router-commands",),
            ),
            FreshnessRule(
                "router-skill-invalidates-tests-docs",
                upstream_artifact_id="skill.skillguard-global-router",
                invalidates_artifact_ids=("tests.global-router-fixtures", "docs.global-router-boundary"),
            ),
        ),
    )


def main() -> int:
    report = review_development_process_flow(global_router_plan())
    print(report.format_text(max_findings=20))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
