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

# Consumer releases cross the SkillGuard/FlowGuard repository boundary.  Keep
# this policy separate from the author-side ``canonical_json_bytes`` helper:
# the latter is the current SkillGuard record wire format (pretty JSON plus a
# newline), while consumer-release.json has one deliberately different,
# externally shared wire contract.  There must be one implementation of that
# contract in the SkillGuard producer and verifier, and no call site should
# silently select the author-record format.
CONSUMER_RELEASE_WIRE_POLICY_ID = "consumer.skill_distribution.wire.current"
CONSUMER_RELEASE_WIRE_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def wire_hash(payload: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def consumer_release_canonical_json_bytes(payload: object) -> bytes:
    """Return FlowGuard-compatible consumer-release identity bytes.

    The bytes intentionally omit the final newline.  Hashes are computed over
    these bytes; the serialized manifest adds exactly one LF only after both
    ``release_id`` and ``manifest_hash`` have been derived.
    """

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def consumer_release_wire_hash_bytes(payload: bytes) -> str:
    """Hash consumer-release bytes as lowercase ``sha256:<64 hex>``."""

    return "sha256:" + hashlib.sha256(payload).hexdigest()


def consumer_release_wire_hash(payload: object) -> str:
    """Hash one consumer-release JSON value under the shared wire policy."""

    return consumer_release_wire_hash_bytes(consumer_release_canonical_json_bytes(payload))


def is_consumer_release_wire_hash(value: object) -> bool:
    """Return true only for the current consumer-release wire identity."""

    return (
        isinstance(value, str)
        and CONSUMER_RELEASE_WIRE_HASH_PATTERN.fullmatch(value) is not None
    )


def is_wire_hash(value: object) -> bool:
    """Return true only for the one current persistent content-address form."""

    return isinstance(value, str) and WIRE_HASH_PATTERN.fullmatch(value) is not None


__all__ = [
    "WIRE_IDENTITY_POLICY_ID",
    "WIRE_HASH_PATTERN",
    "CONSUMER_RELEASE_WIRE_POLICY_ID",
    "CONSUMER_RELEASE_WIRE_HASH_PATTERN",
    "canonical_json_bytes",
    "consumer_release_canonical_json_bytes",
    "consumer_release_wire_hash",
    "consumer_release_wire_hash_bytes",
    "is_consumer_release_wire_hash",
    "is_wire_hash",
    "wire_hash",
]
