"""Repository delegate to SkillGuard's portable template-lifecycle model."""

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
    / "template_lifecycle_model.py"
)
_MODULE_NAME = "skillguard_portable_template_lifecycle_model"
_SPEC = importlib.util.spec_from_file_location(_MODULE_NAME, PORTABLE_MODEL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(
        f"cannot load portable SkillGuard template model: {PORTABLE_MODEL_PATH}"
    )
_PORTABLE_MODEL = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_NAME] = _PORTABLE_MODEL
_SPEC.loader.exec_module(_PORTABLE_MODEL)

for _name, _value in vars(_PORTABLE_MODEL).items():
    if _name not in {
        "__name__",
        "__loader__",
        "__package__",
        "__spec__",
        "__file__",
        "__cached__",
    }:
        globals()[_name] = _value


if __name__ == "__main__":
    raise SystemExit(main())
