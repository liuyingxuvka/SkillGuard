from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
TEST_JOB_NAMES = (
    "v2-focused",
    "clean-installed-layout",
    "full-current-suite",
)
TAG_EXCLUSION = (
    "if: ${{ github.event_name != 'push' || "
    "!startsWith(github.ref, 'refs/tags/') }}"
)


def _job_block(workflow: str, job_name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(job_name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        workflow,
    )
    assert match is not None, f"missing workflow job: {job_name}"
    return match.group(0)


def test_branch_regression_jobs_are_not_scheduled_for_tag_pushes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for job_name in TEST_JOB_NAMES:
        assert TAG_EXCLUSION in _job_block(workflow, job_name)


def test_tag_job_is_receipt_only_and_binds_version_to_commit() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    tag_job = _job_block(workflow, "tag-release-identity")
    assert (
        "if: ${{ github.event_name == 'push' && "
        "startsWith(github.ref, 'refs/tags/') }}"
    ) in tag_job
    assert 'test "${GITHUB_REF_NAME}" = "v${version}"' in tag_job
    assert 'git rev-list -n 1 "${GITHUB_REF_NAME}"' in tag_job
    assert "pytest" not in tag_job
    assert "flowguard" not in tag_job.lower()


def test_ci_uses_current_flowguard_release() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert workflow.count("FlowGuard.git@v0.58.4") == 3
    assert "FlowGuard.git@v0.56.0" not in workflow
