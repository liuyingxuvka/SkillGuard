"""Evidence-class policy derived from a compiled step binding.

The contract tells an executor what kind of authority a step needs.  A model
check can support a judged or witnessed step, but it cannot silently replace
the judgment or runtime witness that the step promises.
"""

from __future__ import annotations

from typing import Any, Mapping


ACTION_EVIDENCE_CLASS = {
    "judged": "judged",
    "witness": "witnessed",
    "ui_launch": "witnessed",
    "ui_interaction": "witnessed",
    "tool_action": "witnessed",
    "api_action": "witnessed",
}


def required_evidence_class(step: Mapping[str, Any]) -> str:
    """Return the primary receipt class required to verify ``step``."""

    binding = step.get("binding", {})
    if not isinstance(binding, Mapping):
        return "hard"
    action = binding.get("action", {})
    if not isinstance(action, Mapping):
        return "hard"
    explicit = str(action.get("evidence_class", "")).strip()
    if explicit:
        if explicit not in {"hard", "witnessed", "judged"}:
            raise ValueError(f"unsupported explicit evidence class: {explicit}")
        return explicit
    return ACTION_EVIDENCE_CLASS.get(str(action.get("kind", "")).strip(), "hard")
