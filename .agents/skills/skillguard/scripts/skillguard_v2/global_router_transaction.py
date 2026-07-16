"""No-op preserving transaction for generated global-router artifacts.

The registry, prompt projection, and managed AGENTS block form one installed
projection.  A refresh either leaves all three at their prior bytes or commits
all changed members.  Byte-identical members are never rewritten, so an
equivalent refresh cannot manufacture freshness drift through mtimes.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Mapping


class GlobalRouterTransactionError(RuntimeError):
    """Raised after a failed commit has been rolled back."""


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as handle:
        handle.flush()
        os.fsync(handle.fileno())


def _write_staged(path: Path, payload: bytes, transaction_id: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(f".{path.name}.{transaction_id}.new")
    staged.write_bytes(payload)
    _fsync_file(staged)
    if staged.read_bytes() != payload:
        raise OSError(f"staged global-router bytes differ: {path.name}")
    return staged


def _restore(path: Path, original: bytes | None, transaction_id: str) -> None:
    if original is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    rollback = path.with_name(f".{path.name}.{transaction_id}.rollback")
    rollback.write_bytes(original)
    _fsync_file(rollback)
    os.replace(rollback, path)


def apply_global_router_transaction(
    artifacts: Mapping[Path, bytes],
) -> dict[str, object]:
    """Commit changed artifacts together and roll every committed path back.

    The returned transaction id is attempt metadata only.  It is deliberately
    absent from registry, prompt, and installation semantic identities.
    """

    normalized: dict[Path, bytes] = {}
    for path_value, payload in artifacts.items():
        path = Path(path_value).resolve()
        if path in normalized:
            raise ValueError("global_router_transaction_duplicate_path")
        if not isinstance(payload, bytes):
            raise TypeError("global_router_transaction_payload_must_be_bytes")
        normalized[path] = payload

    ordered = sorted(normalized, key=lambda value: value.as_posix().casefold())
    originals = {
        path: path.read_bytes() if path.is_file() else None for path in ordered
    }
    changed = [path for path in ordered if originals[path] != normalized[path]]
    unchanged = [path for path in ordered if path not in changed]
    transaction_id = secrets.token_hex(8)
    if not changed:
        return {
            "status": "unchanged",
            "transaction_id": transaction_id,
            "changed_paths": [],
            "unchanged_paths": [str(path) for path in unchanged],
        }

    staged: dict[Path, Path] = {}
    committed: list[Path] = []
    try:
        for path in changed:
            staged[path] = _write_staged(
                path, normalized[path], transaction_id
            )
        for path in changed:
            os.replace(staged[path], path)
            committed.append(path)
        for path in changed:
            if path.read_bytes() != normalized[path]:
                raise OSError(
                    f"committed global-router bytes differ: {path.name}"
                )
    except BaseException as exc:
        rollback_failures: list[str] = []
        for path in reversed(committed):
            try:
                _restore(path, originals[path], transaction_id)
            except BaseException as rollback_exc:
                rollback_failures.append(
                    f"{path.name}:{type(rollback_exc).__name__}"
                )
        for path in changed:
            candidate = staged.get(path)
            if candidate is not None:
                try:
                    candidate.unlink()
                except FileNotFoundError:
                    pass
        detail = f"global_router_transaction_failed:{type(exc).__name__}"
        if rollback_failures:
            detail += ":rollback_unconfirmed=" + ",".join(rollback_failures)
        raise GlobalRouterTransactionError(detail) from exc
    finally:
        for candidate in staged.values():
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass

    return {
        "status": "committed",
        "transaction_id": transaction_id,
        "changed_paths": [str(path) for path in changed],
        "unchanged_paths": [str(path) for path in unchanged],
    }


__all__ = [
    "GlobalRouterTransactionError",
    "apply_global_router_transaction",
]
