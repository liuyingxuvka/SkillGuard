"""Stable source-model entrypoint for the validation-composition TestMesh.

The executable implementation stays in ``validation_composition_model`` so
the child model, mesh adapters, and unified runner remain separately readable.
"""

from validation_composition_model import *  # noqa: F401,F403
from validation_composition_model import MODEL_ID as _MODEL_ID


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = _MODEL_ID
