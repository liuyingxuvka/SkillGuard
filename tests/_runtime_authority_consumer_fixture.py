from __future__ import annotations

import json
import shutil
from pathlib import Path

from checker_engine import (  # type: ignore
    compile_generated_current_contract,
    generated_current_contract_sources,
)
from skillguard_v2.runtime_authority import (
    canonical_payload_hash,
)


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_AUTHORITY_SOURCE = (
    ROOT
    / ".agents"
    / "skills"
    / "skillguard"
    / "scripts"
    / "skillguard_v2"
    / "runtime_authority.py"
)
OLD_WORK_CONTRACT_PATH = ".skillguard/work-contract.json"
OLD_CHECK_MANIFEST_PATH = ".skillguard/check_manifest.json"
OLD_RUN_RECORD_SCHEMA = "skillguard.run_record.v1"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _base_skill(skill_root: Path, skill_id: str) -> None:
    skill_root.mkdir(parents=True, exist_ok=True)
    (skill_root / "SKILL.md").write_text(
        (
            "---\n"
            f"name: {skill_id}\n"
            "description: Runtime authority consumer fixture.\n"
            "---\n"
            "# Fixture\n"
        ),
        encoding="utf-8",
    )


def write_old_pair_rejection(skill_root: Path, skill_id: str) -> None:
    """Create an exact negative fixture; this is never a supported authority."""

    _base_skill(skill_root, skill_id)
    write_json(
        skill_root / OLD_WORK_CONTRACT_PATH,
        {"schema_version": "skillguard.work_contract.v1", "skill_id": skill_id},
    )
    write_json(
        skill_root / OLD_CHECK_MANIFEST_PATH,
        {
            "schema_version": "skillguard.check_manifest.v1",
            "target_skill": skill_id,
            "checks": [],
        },
    )


def make_current_skill(
    skill_root: Path,
    skill_id: str,
    *,
    with_current_run: bool = True,
    revision: str = "",
) -> None:
    """Create one isolated current-authority fixture without audit history."""

    _base_skill(skill_root, skill_id)
    if revision:
        with (skill_root / "SKILL.md").open("a", encoding="utf-8") as stream:
            stream.write(f"\n{revision}\n")
    run_checks = skill_root / "scripts" / "run_checks.py"
    run_checks.parent.mkdir(parents=True, exist_ok=True)
    run_checks.write_text(
        "from __future__ import annotations\nraise SystemExit(0)\n",
        encoding="utf-8",
    )
    install_stub_runtime(skill_root)
    model_source, binding = generated_current_contract_sources(skill_id)
    runtime_paths = (
        "scripts/skillguard.py",
        "scripts/skillguard_v2/__init__.py",
        "scripts/skillguard_v2/runtime_authority.py",
        "scripts/skillguard_v2/contract_schema.py",
        "scripts/skillguard_v2/capability_contract.py",
        "scripts/skillguard_v2/runtime_fingerprint.py",
    )
    binding["implementation_paths"] = [
        *binding["implementation_paths"],
        *runtime_paths,
    ]
    files = {
        ".skillguard/flowguard_contract_model.py": model_source,
        ".skillguard/contract-source.json": (
            json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ),
        "SKILL.md": (skill_root / "SKILL.md").read_text(encoding="utf-8"),
        "scripts/run_checks.py": run_checks.read_text(encoding="utf-8"),
        **{
            relative: (skill_root / relative).read_text(encoding="utf-8")
            for relative in runtime_paths
        },
    }
    compile_generated_current_contract(files)
    for relative, content in files.items():
        path = skill_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
    if with_current_run:
        write_json(
            skill_root / ".skillguard" / "runs" / "run-current" / "run.json",
            {"schema_version": "skillguard.run.v2", "run_id": "run-current"},
        )


def make_old_pair_rejection_skill(skill_root: Path, skill_id: str) -> None:
    write_old_pair_rejection(skill_root, skill_id)


def make_old_lifecycle_rejection_skill(skill_root: Path, skill_id: str) -> None:
    make_current_skill(skill_root, skill_id)
    source_path = skill_root / ".skillguard" / "contract-source.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["v1_runtime_authority"] = {"status": "retired"}
    write_json(source_path, source)


def add_old_flat_run_rejection(
    skill_root: Path,
    name: str = "old-flat-run-rejection.json",
) -> Path:
    path = skill_root / ".skillguard" / "runs" / name
    write_json(
        path,
        {"schema_version": OLD_RUN_RECORD_SCHEMA, "run_id": path.stem},
    )
    return path


def install_stub_runtime(skillguard_root: Path) -> None:
    scripts = skillguard_root / "scripts"
    package = scripts / "skillguard_v2"
    package.mkdir(parents=True, exist_ok=True)
    (scripts / "skillguard.py").write_text(
        "from __future__ import annotations\nraise SystemExit(0)\n",
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    source_package = RUNTIME_AUTHORITY_SOURCE.parent
    for name in (
        "runtime_authority.py",
        "contract_schema.py",
        "capability_contract.py",
    ):
        shutil.copy2(source_package / name, package / name)
    (package / "runtime_fingerprint.py").write_text(
        (
            "from __future__ import annotations\n"
            "def guard_runtime_fingerprint():\n"
            "    return {'runtime_id': 'skillguard-current', 'file_count': 1, 'source_hash': 'A' * 64}\n"
            "def guard_active_installation_runtime_fingerprint():\n"
            "    return guard_runtime_fingerprint()\n"
        ),
        encoding="utf-8",
    )


def make_target_identity(skill_id: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "skillguard.target_identity_scan_receipt.v1",
        "skill_id": skill_id,
        "target_kind": "single_skill",
        "skill_root_token": ".",
        "skill_paths": ["."],
        "member_identities": [
            {"member_skill_id": skill_id, "skill_path": "."}
        ],
    }
    payload["receipt_hash"] = canonical_payload_hash(payload)
    return payload
