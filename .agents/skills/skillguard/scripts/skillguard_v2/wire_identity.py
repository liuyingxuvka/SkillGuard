"""Canonical wire identities shared by current SkillGuard projections.

This module is deliberately small and behavior-only.  Components that depend
on persistent identity semantics can bind this file without inheriting an
entire compiler or CLI implementation as an invalidation input.
"""

from __future__ import annotations

import hashlib
import json
import re


WIRE_IDENTITY_POLICY_ID = "skillguard.wire_identity.sha256.current"
WIRE_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def wire_hash(payload: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def is_wire_hash(value: object) -> bool:
    """Return true only for the one current persistent content-address form."""

    return isinstance(value, str) and WIRE_HASH_PATTERN.fullmatch(value) is not None


__all__ = [
    "WIRE_IDENTITY_POLICY_ID",
    "WIRE_HASH_PATTERN",
    "canonical_json_bytes",
    "is_wire_hash",
    "wire_hash",
]
