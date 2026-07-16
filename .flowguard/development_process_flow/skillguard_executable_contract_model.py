"""Repository delegate to SkillGuard's portable executable-contract model.

The implementation has exactly one semantic owner:
``.agents/skills/skillguard/.skillguard/flowguard_contract_model.py``.
This repository path remains as the stable FlowGuard development entrypoint
and re-exports that owner instead of carrying a second model copy.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PORTABLE_MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / ".agents"
    / "skills"
    / "skillguard"
    / ".skillguard"
    / "flowguard_contract_model.py"
)
_MODULE_NAME = "skillguard_portable_executable_contract_model"
_SPEC = importlib.util.spec_from_file_location(_MODULE_NAME, PORTABLE_MODEL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"cannot load portable SkillGuard model: {PORTABLE_MODEL_PATH}")
_PORTABLE_MODEL = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_NAME] = _PORTABLE_MODEL
_SPEC.loader.exec_module(_PORTABLE_MODEL)

# Keep one stable repository entrypoint while all model behavior remains in the
# portable owner. Private helpers are intentionally re-exported because current
# model tests exercise the complete development entrypoint.
for _name, _value in vars(_PORTABLE_MODEL).items():
    if _name not in {"__name__", "__loader__", "__package__", "__spec__", "__file__", "__cached__"}:
        globals()[_name] = _value


if __name__ == "__main__":
    raise SystemExit(_PORTABLE_MODEL.main())
