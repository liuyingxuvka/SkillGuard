from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skillguard" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.consumer_distribution import (  # noqa: E402
    build_consumer_distribution,
)
from skillguard_v2.contract_compiler import compile_skill_contract  # noqa: E402


def test_current_projection_is_clean_and_contains_runtime_dependencies(tmp_path: Path) -> None:
    repository_root = SCRIPT_ROOT.parents[3]
    compiled = compile_skill_contract(repository_root, write=False)
    assert compiled.ok, compiled.to_dict()

    destination = tmp_path / "consumer" / "skillguard"
    report = build_consumer_distribution(
        repository_root / ".agents" / "skills" / "skillguard",
        destination,
        compiled.compiled_contract,
    )

    assert report["status"] == "passed", report
    paths = {row["path"] for row in report["manifest"]["files"]}
    assert "scripts/skillguard_v2/compact_state.py" in paths
    assert ".skillguard" not in paths
    assert all("receipt" not in path and "router" not in path for path in paths)
    assert not any(
        path.endswith(("/run_store.py", "/content_projection.py", "/runtime_authority.py"))
        or "/kb/" in f"/{path.lower()}/"
        for path in paths
    )
