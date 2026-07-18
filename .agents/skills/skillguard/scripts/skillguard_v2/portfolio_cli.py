"""CLI handlers for the private SkillGuard portfolio runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from skillguard_utils import emit_json

from .contract_compiler import canonical_hash, canonical_json_bytes
from .portfolio import (
    apply_guard_change,
    atomic_write_json,
    audit_portfolio,
    build_current_portfolio_registry,
    current_guard,
    graduate_portfolio_target,
    portfolio_registry_lock,
    PortfolioRegistryLockError,
)
from .portfolio_records import reference_existing_file
from .run_store import utc_now
from .portfolio_runner import (
    PortfolioRunnerError,
    assemble_portfolio_attempt,
    capture_portfolio_production_revalidation_binding,
    execute_portfolio_attempt,
    prepare_portfolio_attempt,
)
from .portfolio_impact_receipt import (
    build_portfolio_impact_receipt,
    verify_portfolio_impact_receipt,
    write_portfolio_impact_receipt,
)
from .installation_receipt import (
    build_installation_verification_receipt,
    current_installation_snapshot,
    resolve_codex_home_root,
    verify_installation_verification_receipt,
    write_installation_verification_receipt,
)


def _workspace_path(path_text: str, workspace_root: Path) -> Path:
    root = workspace_root.resolve()
    path = Path(path_text)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path must stay under workspace root: {path_text}") from exc
    return path


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_content_impact_plan(path: Path) -> Mapping[str, Any]:
    payload = _load(path)
    if not isinstance(payload, Mapping):
        raise ValueError("content impact plan input must be an object")
    if payload.get("schema_version") == "skillguard.content_impact_plan.current":
        return payload
    plan = payload.get("content_impact_plan")
    if not isinstance(plan, Mapping):
        raise ValueError("content impact plan input has no current plan")
    return plan


def _output(payload: Mapping[str, Any], output_text: str, workspace_root: Path) -> None:
    if not output_text or output_text == "-":
        emit_json(payload)
        return
    atomic_write_json(_workspace_path(output_text, workspace_root), payload)


PATH_ROLE_PROJECTION_SCHEMA = "skillguard.path_role_projection.v1"
PATH_ROLE_PROJECTION_ARTIFACT = "skillguard_path_role_projection"


def _path_identity_hash(role: str, resolved_path: Path) -> str:
    return canonical_hash(
        {
            "role": role,
            "resolved_path": os.path.normcase(str(resolved_path)),
        }
    )


def _path_role_projection(
    *,
    role: str,
    path_token: str,
    authority: str,
    declared_path: Path | None,
) -> dict[str, Any]:
    declared = declared_path is not None
    resolved = False
    exists = False
    is_directory = False
    identity_verified = False
    identity_hash = ""
    if declared_path is not None:
        try:
            resolved_path = declared_path.resolve()
        except OSError:
            state = "declared"
        else:
            resolved = True
            exists = resolved_path.exists()
            is_directory = resolved_path.is_dir()
            identity_verified = exists and is_directory
            if identity_verified:
                identity_hash = _path_identity_hash(role, resolved_path)
            state = "verified" if identity_verified else "missing" if not exists else "resolved"
    else:
        state = "missing"
    return {
        "role": role,
        "path_token": path_token,
        "authority": authority,
        "state": state,
        "status": {
            "declared": declared,
            "resolved": resolved,
            "verified": identity_verified,
            "missing": not exists,
        },
        "exists": exists,
        "is_directory": is_directory,
        "identity_verified": identity_verified,
        "available": identity_verified,
        "identity_hash": identity_hash,
    }


def _target_path_projection(
    *,
    workspace_root: Path,
    target_repository_root: Path,
    installed_target_root: Path | None,
) -> dict[str, Any]:
    return {
        "schema_version": PATH_ROLE_PROJECTION_SCHEMA,
        "artifact_type": PATH_ROLE_PROJECTION_ARTIFACT,
        "privacy": "persisted_token_or_hashed_identity_only",
        "roles": {
            "canonical_local_source": _path_role_projection(
                role="canonical_local_source",
                path_token="target_repository_root",
                authority="canonical_local_source",
                declared_path=target_repository_root,
            ),
            "working_root": _path_role_projection(
                role="working_root",
                path_token="workspace_root",
                authority="private_working_context",
                declared_path=workspace_root,
            ),
            "installed_root": _path_role_projection(
                role="installed_root",
                path_token="installed_target_root",
                authority="installed_copy_non_authoritative",
                declared_path=installed_target_root,
            ),
        },
        "claim_boundary": (
            "Persisted path roles contain portable tokens and opaque identity hashes only. "
            "The installed copy never replaces the canonical local source."
        ),
    }


def _is_same_or_nested(first: Path, second: Path) -> bool:
    try:
        first.resolve().relative_to(second.resolve())
    except ValueError:
        return False
    return True


def _validated_target_path_projection(
    *,
    workspace_root: Path,
    target_repository_root: Path,
    installed_target_root: Path | None,
) -> dict[str, Any]:
    canonical = target_repository_root.resolve()
    if not canonical.exists() or not canonical.is_dir():
        raise ValueError("canonical target repository root must exist and be a directory")
    working = workspace_root.resolve()
    if not working.exists() or not working.is_dir():
        raise ValueError("working root must exist and be a directory")
    if _is_same_or_nested(working, canonical) or _is_same_or_nested(canonical, working):
        raise ValueError(
            "working mutation root and canonical target repository root must be separate, non-nested paths"
        )
    if installed_target_root is not None:
        installed = installed_target_root.resolve()
        if _is_same_or_nested(canonical, installed) or _is_same_or_nested(installed, canonical):
            raise ValueError(
                "canonical target repository root and installed target root must be separate, non-nested paths"
            )
        if _is_same_or_nested(working, installed) or _is_same_or_nested(installed, working):
            raise ValueError(
                "working mutation root and installed target root must be separate, non-nested paths"
            )
    return _target_path_projection(
        workspace_root=working,
        target_repository_root=canonical,
        installed_target_root=installed_target_root,
    )


def _home_redacted_display_path(path: Path) -> str:
    resolved = path.resolve()
    home = Path.home().resolve()
    try:
        relative = resolved.relative_to(home)
    except ValueError:
        return str(resolved)
    if relative == Path("."):
        return "<HOME>"
    return f"<HOME>/{relative.as_posix()}"


def _emit_runtime_target_path_display(
    *,
    workspace_root: Path,
    target_repository_root: Path,
    installed_target_root: Path | None,
    projection: Mapping[str, Any] | None = None,
) -> None:
    path_projection = dict(
        projection
        or _target_path_projection(
            workspace_root=workspace_root,
            target_repository_root=target_repository_root,
            installed_target_root=installed_target_root,
        )
    )
    projected_roles = path_projection["roles"]
    runtime_paths = {
        "canonical_local_source": target_repository_root,
        "working_root": workspace_root,
        "installed_root": installed_target_root,
    }
    rows = []
    for role in ("canonical_local_source", "working_root", "installed_root"):
        row = dict(projected_roles[role])
        runtime_path = runtime_paths[role]
        row["resolved_display_path"] = (
            _home_redacted_display_path(runtime_path) if runtime_path is not None else ""
        )
        row["display_redaction"] = "home_redacted"
        rows.append(row)
    event = {
        "schema_version": "skillguard.runtime_path_display.v1",
        "artifact_type": "skillguard_runtime_path_display",
        "event_type": "target_path_display",
        "display_redaction": "home_redacted",
        "privacy": "runtime_display_only_not_for_persisted_public_artifacts",
        "paths": rows,
        "claim_boundary": (
            "Resolved display paths are runtime-only. Canonical local source is authoritative; "
            "working and installed roots are not source authority."
        ),
    }
    sys.stderr.write(json.dumps(event, sort_keys=True) + "\n")
    sys.stderr.flush()


def _record_ref(path: Path, workspace_root: Path) -> str:
    root = workspace_root.resolve()
    resolved = path.resolve()
    relative = resolved.relative_to(root)
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest().upper()
    return f"record:{relative.as_posix()}@{digest}"


def _registry_lock_path(registry_path: Path) -> Path:
    return registry_path.with_name(f".{registry_path.name}.skillguard.lock").resolve()


class PortfolioRegistryCASMismatch(RuntimeError):
    """Raised when the registry changes after a mutation was prepared."""


def _transaction_journal_path(registry_path: Path, transaction_id: str) -> Path:
    token = hashlib.sha256(transaction_id.encode("utf-8")).hexdigest()[:24]
    return (
        registry_path.parent
        / ".skillguard"
        / "portfolio-transactions"
        / f"{token}.json"
    ).resolve()


def _commit_registry_mutation(
    *,
    workspace: Path,
    registry_path: Path,
    base_registry: Mapping[str, Any],
    updated_registry: Mapping[str, Any],
    request: Mapping[str, Any],
    mutation_kind: str,
    artifact_path: Path | None = None,
    artifact_payload: Mapping[str, Any] | None = None,
    artifact_semantic_hash: str = "",
) -> dict[str, Any]:
    transaction_id = str(request["transaction_id"])
    journal_path = _transaction_journal_path(registry_path, transaction_id)
    artifact_rows: list[dict[str, str]] = []
    if artifact_path is not None and artifact_payload is not None:
        artifact_rows.append(
            {
                "path": artifact_path.resolve().relative_to(workspace).as_posix(),
                "semantic_hash": artifact_semantic_hash,
                "file_hash": hashlib.sha256(
                    canonical_json_bytes(artifact_payload)
                ).hexdigest().upper(),
            }
        )
    transaction = updated_registry.get("transaction_history", [])[-1]
    journal: dict[str, Any] = {
        "schema_version": "skillguard.portfolio_registry_transaction_journal.v1",
        "transaction_id": transaction_id,
        "mutation_kind": mutation_kind,
        "status": "prepared",
        "registry_path": registry_path.relative_to(workspace).as_posix(),
        "base_registry_revision": int(base_registry["revision"]),
        "base_registry_hash": str(base_registry["registry_hash"]),
        "intended_registry_revision": int(updated_registry["revision"]),
        "intended_registry_hash": str(updated_registry["registry_hash"]),
        "request_hash": canonical_hash(request),
        "artifacts": artifact_rows,
        "prepared_at": str(transaction["committed_at"]),
        "claim_boundary": "Prepared means child artifacts may exist but the registry must not be treated as committed until CAS succeeds.",
    }
    if journal_path.exists():
        existing = _load(journal_path)
        comparable_fields = (
            "schema_version",
            "transaction_id",
            "mutation_kind",
            "base_registry_revision",
            "base_registry_hash",
            "intended_registry_revision",
            "intended_registry_hash",
            "request_hash",
            "artifacts",
        )
        if not isinstance(existing, Mapping) or any(
            existing.get(field) != journal.get(field) for field in comparable_fields
        ):
            raise PortfolioRegistryCASMismatch(
                "transaction journal exists with a different base or intended mutation"
            )
    else:
        atomic_write_json(journal_path, journal)

    if artifact_path is not None and artifact_payload is not None:
        atomic_write_json(artifact_path, artifact_payload)

    current = _load(registry_path)
    if (
        not isinstance(current, Mapping)
        or current.get("revision") != base_registry.get("revision")
        or current.get("registry_hash") != base_registry.get("registry_hash")
    ):
        raise PortfolioRegistryCASMismatch(
            "registry revision or hash changed after transaction preparation"
        )
    atomic_write_json(registry_path, updated_registry)
    journal["status"] = "committed"
    journal["committed_registry_hash"] = str(updated_registry["registry_hash"])
    journal["claim_boundary"] = (
        "Committed proves the child-first write and registry compare-and-swap completed for this exact transaction."
    )
    atomic_write_json(journal_path, journal)
    return {
        "journal_file": journal_path.relative_to(workspace).as_posix(),
        "transaction_id": transaction_id,
        "registry_revision": int(updated_registry["revision"]),
    }


def _assert_distinct_path_roles(workspace_root: Path, **roles: str | None) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for role, path_text in roles.items():
        if not path_text or path_text == "-":
            continue
        resolved[role] = _workspace_path(path_text, workspace_root)
    by_path: dict[Path, list[str]] = {}
    for role, path in resolved.items():
        by_path.setdefault(path, []).append(role)
    collisions = [sorted(names) for names in by_path.values() if len(names) > 1]
    role_items = sorted(resolved.items())
    for index, (left_role, left_path) in enumerate(role_items):
        if not left_path.exists():
            continue
        for right_role, right_path in role_items[index + 1 :]:
            if not right_path.exists() or left_path == right_path:
                continue
            try:
                same_file = os.path.samefile(left_path, right_path)
            except OSError:
                same_file = False
            if same_file:
                collisions.append(sorted((left_role, right_role)))
    registry_path = resolved.get("registry")
    if registry_path is not None:
        lock_path = _registry_lock_path(registry_path)
        for role, path in resolved.items():
            if role != "registry" and path == lock_path:
                collisions.append(sorted((role, "registry_lock")))
    if collisions:
        raise ValueError(
            "portfolio path roles must be distinct: "
            + "; ".join("=".join(names) for names in sorted(collisions))
        )
    return resolved


def _assert_mutation_paths_outside_roots(
    paths: Mapping[str, Path],
    *,
    mutable_roles: tuple[str, ...],
    protected_roots: tuple[Path, ...],
) -> None:
    collisions: list[str] = []
    roots = tuple(root.resolve() for root in protected_roots)
    for role in mutable_roles:
        path = paths.get(role)
        if path is None:
            continue
        for root in roots:
            try:
                path.resolve().relative_to(root)
            except ValueError:
                continue
            collisions.append(f"{role}@{root.name or root.anchor}")
    if collisions:
        raise ValueError(
            "portfolio mutation outputs must stay outside target/runtime roots: "
            + ",".join(sorted(collisions))
        )


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", default="-")


def _target_repository_root_map(
    values: Sequence[str], workspace: Path
) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        skill_id, separator, path_value = str(value).partition("=")
        if not separator or not skill_id.strip() or not path_value.strip():
            raise ValueError(
                "target repository roots must use SKILL_ID=PATH"
            )
        skill_id = skill_id.strip()
        if skill_id in roots:
            raise ValueError(f"duplicate target repository root: {skill_id}")
        root = _workspace_path(path_value.strip(), workspace)
        if not root.is_dir():
            raise ValueError(f"target repository root is not a directory: {skill_id}")
        roots[skill_id] = root
    return roots


def build_current_portfolio_registry_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="skillguard.py build-current-portfolio-registry",
        description=(
            "Directly replace portfolio authority from one hash-valid reviewed "
            "current scope without consuming a prior registry."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--scope", required=True)
    parser.add_argument("--registry-id", required=True)
    parser.add_argument(
        "--runtime-root",
        help="SkillGuard repository, installed skill, scripts, or skillguard_v2 package root",
    )
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    paths = _assert_distinct_path_roles(
        workspace,
        scope=args.scope,
        output=args.output,
    )
    scope_path = paths["scope"]

    def build_registry() -> dict[str, Any]:
        scope = _load(scope_path)
        if not isinstance(scope, Mapping):
            raise ValueError("portfolio current scope must be an object")
        guard = (
            current_guard(Path(args.runtime_root).resolve())
            if args.runtime_root
            else current_guard()
        )
        return build_current_portfolio_registry(
            scope,
            registry_id=args.registry_id,
            scope_manifest_ref=reference_existing_file(scope_path, workspace),
            active_guard=guard,
            evidence_root=workspace,
            issued_at=utc_now(),
        )

    output_path = paths.get("output")
    if output_path is None:
        _output(build_registry(), args.output, workspace)
        return 0

    # Direct replacement has no prior-registry input, but it still mutates the
    # sole registry authority.  Use the same writer lock as impact, reuse, and
    # graduation so a live mutation can never be silently overwritten.
    with portfolio_registry_lock(output_path):
        atomic_write_json(output_path, build_registry())
    return 0


def audit_portfolio_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py audit-portfolio")
    _common(parser)
    parser.add_argument(
        "--runtime-root",
        help="SkillGuard repository, installed skill, scripts, or skillguard_v2 package root",
    )
    parser.add_argument("--candidate", default="")
    parser.add_argument(
        "--target-repository-root",
        action="append",
        default=[],
        metavar="SKILL_ID=PATH",
        help=(
            "Repeat for every current target whose production receipts must be "
            "replayed against its canonical repository."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("candidate-preflight", "candidate-graduation", "all-current"),
        default="all-current",
    )
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    paths = _assert_distinct_path_roles(
        workspace,
        registry=args.registry,
        output=args.output,
    )
    registry = _load(paths["registry"])
    guard = current_guard(Path(args.runtime_root).resolve()) if args.runtime_root else current_guard()
    target_repository_roots = _target_repository_root_map(
        args.target_repository_root, workspace
    )
    report = audit_portfolio(
        registry,
        actual_guard=guard,
        candidate_skill_id=args.candidate,
        evidence_root=workspace,
        target_repository_roots=target_repository_roots,
        mode=args.mode,
    )
    _output(report, args.output, workspace)
    return 0 if report["status"] == "current" else 1


def mark_portfolio_impact_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py mark-portfolio-impact")
    _common(parser)
    parser.add_argument("--change", required=True)
    parser.add_argument("--impact-plan", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--receipt-root")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    paths = _assert_distinct_path_roles(
        workspace,
        registry=args.registry,
        change=args.change,
        impact_plan=args.impact_plan,
        output=args.output,
    )
    registry_path = paths["registry"]
    change = _load(paths["change"])
    content_impact_plan = _load_content_impact_plan(paths["impact_plan"])
    try:
        if args.write:
            with portfolio_registry_lock(registry_path) as lock:
                base_registry = _load(registry_path)
                report, updated = apply_guard_change(
                    base_registry,
                    change,
                    content_impact_plan=content_impact_plan,
                    evidence_root=workspace,
                )
                if updated is not None and report.get("status") != "already_committed":
                    transaction = _commit_registry_mutation(
                        workspace=workspace,
                        registry_path=registry_path,
                        base_registry=base_registry,
                        updated_registry=updated,
                        request=change,
                        mutation_kind="guard_change",
                    )
                    report["transaction"] = transaction
                    report["registry_written"] = True
                elif updated is not None:
                    report["registry_written"] = False
                    report["transaction_reused"] = True
                else:
                    report["registry_written"] = False
                report["registry_lock_recovered"] = lock["lock_recovered"]
        else:
            report, updated = apply_guard_change(
                _load(registry_path),
                change,
                content_impact_plan=content_impact_plan,
                evidence_root=workspace,
            )
            report["registry_written"] = False
    except (PortfolioRegistryLockError, PortfolioRegistryCASMismatch) as exc:
        code = (
            "portfolio_registry_cas_mismatch"
            if isinstance(exc, PortfolioRegistryCASMismatch)
            else "portfolio_registry_writer_conflict"
        )
        report = {
            "artifact_type": "skillguard_portfolio_impact_result",
            "status": "blocked",
            "blockers": [{"code": code, "detail": str(exc)}],
            "registry_written": False,
        }
        updated = None
    if args.receipt_root:
        if not args.write or updated is None or report.get("status") not in {
            "updated",
            "already_committed",
        }:
            report.setdefault("blockers", []).append(
                {
                    "code": "portfolio_impact_receipt_requires_committed_registry",
                    "detail": "--receipt-root requires --write and a committed impact result",
                }
            )
            updated = None
        else:
            receipt = build_portfolio_impact_receipt(
                change=change,
                registry=updated,
                registry_path=registry_path,
                workspace_root=workspace,
                impact_result=report,
            )
            written = write_portfolio_impact_receipt(
                _workspace_path(args.receipt_root, workspace), receipt
            )
            report["impact_receipt"] = {
                "receipt_id": receipt["receipt_id"],
                "receipt_hash": receipt["receipt_hash"],
                "head_hash": written["head"]["head_hash"],
            }
    _output(report, args.output, workspace)
    return 0 if updated is not None else 1


def verify_portfolio_impact_receipt_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="skillguard.py verify-portfolio-impact-receipt"
    )
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--require-change-id", required=True)
    parser.add_argument("--require-status", default="revalidation_required")
    parser.add_argument("--require-target", action="append", default=[])
    parser.add_argument("--require-exact-target-set", action="store_true")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    report = verify_portfolio_impact_receipt(
        _workspace_path(args.receipt_root, workspace),
        workspace_root=workspace,
        require_change_id=args.require_change_id,
        require_status=args.require_status,
        require_target_ids=args.require_target,
        require_exact_target_set=args.require_exact_target_set,
    )
    _output(report, args.output, workspace)
    return 0 if report["status"] == "passed" else 1


def capture_installation_receipt_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py capture-installation-receipt")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--canonical-skill-root", default=".agents/skills/skillguard")
    parser.add_argument("--codex-home")
    parser.add_argument(
        "--receipt-root",
        help=(
            "Receipt root under the repository, or the exact active SkillGuard "
            "installation receipt root. Defaults to "
            "<CODEX_HOME>/skills/skillguard/.sg-runtime/installation."
        ),
    )
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    repository = Path(args.repository_root).resolve(strict=True)
    canonical = _workspace_path(args.canonical_skill_root, repository)
    codex_home = resolve_codex_home_root(
        Path(args.codex_home) if args.codex_home else None
    )
    active_receipt_root = (
        codex_home / "skills" / "skillguard" / ".sg-runtime" / "installation"
    ).resolve()
    if args.receipt_root:
        declared_receipt_root = Path(args.receipt_root)
        receipt_root = (
            declared_receipt_root.resolve()
            if declared_receipt_root.is_absolute()
            else _workspace_path(args.receipt_root, repository)
        )
        try:
            receipt_root.relative_to(repository)
        except ValueError:
            if receipt_root != active_receipt_root:
                raise ValueError(
                    "absolute --receipt-root must be the exact active SkillGuard "
                    "installation receipt root"
                )
    else:
        receipt_root = active_receipt_root
    snapshot = current_installation_snapshot(
        canonical,
        codex_home=codex_home,
    )
    receipt = build_installation_verification_receipt(snapshot)
    written = write_installation_verification_receipt(receipt_root, receipt)
    report = {
        "artifact_type": "skillguard_installation_receipt_capture",
        "status": "passed",
        "receipt_id": receipt["receipt_id"],
        "receipt_hash": receipt["receipt_hash"],
        "head_hash": written["head"]["head_hash"],
    }
    _output(report, args.output, repository)
    return 0


def verify_installation_receipt_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py verify-installation-receipt")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--canonical-skill-root", default=".agents/skills/skillguard")
    parser.add_argument("--codex-home")
    parser.add_argument(
        "--receipt-root",
        help=(
            "Receipt root under the repository, or the exact active SkillGuard "
            "installation receipt root. Defaults to "
            "<CODEX_HOME>/skills/skillguard/.sg-runtime/installation."
        ),
    )
    parser.add_argument("--require-current-installed-parity", action="store_true")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    repository = Path(args.repository_root).resolve(strict=True)
    codex_home = resolve_codex_home_root(
        Path(args.codex_home) if args.codex_home else None
    )
    active_receipt_root = (
        codex_home / "skills" / "skillguard" / ".sg-runtime" / "installation"
    ).resolve()
    if args.receipt_root:
        declared_receipt_root = Path(args.receipt_root)
        receipt_root = (
            declared_receipt_root.resolve()
            if declared_receipt_root.is_absolute()
            else _workspace_path(args.receipt_root, repository)
        )
        try:
            receipt_root.relative_to(repository)
        except ValueError:
            if receipt_root != active_receipt_root:
                raise ValueError(
                    "absolute --receipt-root must be the exact active SkillGuard "
                    "installation receipt root"
                )
    else:
        receipt_root = active_receipt_root
    report = verify_installation_verification_receipt(
        receipt_root,
        canonical_skill_root=_workspace_path(args.canonical_skill_root, repository),
        codex_home=codex_home,
    )
    if not args.require_current_installed_parity:
        report.setdefault("blockers", []).append(
            "installation_verification_current_parity_requirement_missing"
        )
        report["status"] = "blocked"
    _output(report, args.output, repository)
    return 0 if report["status"] == "passed" else 1


def graduate_portfolio_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py graduate-portfolio")
    _common(parser)
    parser.add_argument("--evidence", required=True)
    parser.add_argument(
        "--runtime-root",
        help="SkillGuard repository, installed skill, scripts, or skillguard_v2 package root",
    )
    parser.add_argument("--receipt-output")
    parser.add_argument(
        "--target-repository-root",
        required=True,
        help="Canonical local repository root for verifier-derived target identity",
    )
    parser.add_argument(
        "--installed-target-root",
        help="Optional installed copy for status, hashed identity, and redacted display; never canonical source authority",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    paths = _assert_distinct_path_roles(
        workspace,
        registry=args.registry,
        evidence=args.evidence,
        receipt_output=args.receipt_output,
        output=args.output,
    )
    target_repository_root = Path(args.target_repository_root).resolve()
    protected_roots = [target_repository_root]
    if args.runtime_root:
        protected_roots.append(Path(args.runtime_root).resolve())
    installed_target_root = (
        Path(args.installed_target_root).resolve()
        if args.installed_target_root
        else None
    )
    target_path_projection = _validated_target_path_projection(
        workspace_root=workspace,
        target_repository_root=target_repository_root,
        installed_target_root=installed_target_root,
    )
    if installed_target_root is not None:
        protected_roots.append(installed_target_root)
    _assert_mutation_paths_outside_roots(
        paths,
        mutable_roles=("registry", "receipt_output", "output"),
        protected_roots=tuple(protected_roots),
    )
    _emit_runtime_target_path_display(
        workspace_root=workspace,
        target_repository_root=target_repository_root,
        installed_target_root=installed_target_root,
        projection=target_path_projection,
    )
    registry_path = paths["registry"]
    guard = current_guard(Path(args.runtime_root).resolve()) if args.runtime_root else current_guard()
    evidence = _load(paths["evidence"])
    if args.write and not args.receipt_output:
        raise ValueError("--receipt-output is required with --write")
    try:
        if args.write:
            receipt_path = paths["receipt_output"]
            with portfolio_registry_lock(registry_path) as lock:
                base_registry = _load(registry_path)
                report, updated, receipt = graduate_portfolio_target(
                    base_registry,
                    evidence,
                    actual_guard=guard,
                    evidence_root=workspace,
                    target_repository_root=target_repository_root,
                    installed_target_root=installed_target_root,
                )
                if (
                    updated is not None
                    and receipt is not None
                    and report.get("status") != "already_committed"
                ):
                    transaction = _commit_registry_mutation(
                        workspace=workspace,
                        registry_path=registry_path,
                        base_registry=base_registry,
                        updated_registry=updated,
                        request=evidence,
                        mutation_kind="graduation",
                        artifact_path=receipt_path,
                        artifact_payload=receipt,
                        artifact_semantic_hash=str(receipt["receipt_hash"]),
                    )
                    report["transaction"] = transaction
                    report["registry_written"] = True
                    report["receipt_written"] = True
                elif updated is not None and receipt is not None:
                    if not receipt_path.exists():
                        atomic_write_json(receipt_path, receipt)
                    report["registry_written"] = False
                    report["receipt_written"] = receipt_path.exists()
                    report["transaction_reused"] = True
                else:
                    report["registry_written"] = False
                    report["receipt_written"] = False
                report["registry_lock_recovered"] = lock["lock_recovered"]
        else:
            report, updated, receipt = graduate_portfolio_target(
                _load(registry_path),
                evidence,
                actual_guard=guard,
                evidence_root=workspace,
                target_repository_root=target_repository_root,
                installed_target_root=installed_target_root,
            )
            report["registry_written"] = False
            report["receipt_written"] = False
    except (PortfolioRegistryLockError, PortfolioRegistryCASMismatch) as exc:
        code = (
            "portfolio_registry_cas_mismatch"
            if isinstance(exc, PortfolioRegistryCASMismatch)
            else "portfolio_registry_writer_conflict"
        )
        report = {
            "artifact_type": "skillguard_portfolio_graduation_result",
            "status": "blocked",
            "blockers": [{"code": code, "detail": str(exc)}],
            "registry_written": False,
            "receipt_written": False,
        }
        updated = None
        receipt = None
    report["target_path_projection"] = target_path_projection
    _output(report, args.output, workspace)
    return 0 if receipt is not None else 1


def _load_job_matrix(path: Path) -> list[Mapping[str, Any]]:
    payload = _load(path)
    if not isinstance(payload, list) or not all(
        isinstance(row, Mapping) for row in payload
    ):
        raise ValueError("--job-matrix must name a JSON array of job objects")
    return payload


def _portfolio_runner_failure(
    *,
    command: str,
    error: PortfolioRunnerError,
    target_path_projection: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "skillguard.portfolio_runner_cli_result.v1",
        "artifact_type": "skillguard_portfolio_runner_cli_result",
        "command": command,
        "status": "blocked",
        "error_code": error.code,
        "detail": error.detail,
        "registry_written": False,
        "published": False,
        "target_path_projection": dict(target_path_projection),
        "claim_boundary": (
            "The production portfolio runner rejected this phase. No registry "
            "mutation or publication was attempted by this command."
        ),
    }


def _runner_target_projection(
    *,
    workspace: Path,
    target_repository_root: Path,
    installed_target_root: Path | None,
) -> dict[str, Any]:
    projection = _validated_target_path_projection(
        workspace_root=workspace,
        target_repository_root=target_repository_root,
        installed_target_root=installed_target_root,
    )
    _emit_runtime_target_path_display(
        workspace_root=workspace,
        target_repository_root=target_repository_root,
        installed_target_root=installed_target_root,
        projection=projection,
    )
    return projection


def prepare_portfolio_run_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py prepare-portfolio-run")
    _common(parser)
    parser.add_argument(
        "--target-repository-root",
        required=True,
        help="Canonical local repository root for the selected portfolio target",
    )
    parser.add_argument("--skill-id", required=True)
    parser.add_argument(
        "--job-matrix",
        required=True,
        help="Workspace-local JSON array containing the complete representative job set",
    )
    parser.add_argument(
        "--installed-target-root",
        help="Optional non-authoritative installed copy used only for content parity",
    )
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    paths = _assert_distinct_path_roles(
        workspace,
        registry=args.registry,
        job_matrix=args.job_matrix,
        output=args.output,
    )
    target_repository_root = Path(args.target_repository_root).resolve()
    installed_target_root = (
        Path(args.installed_target_root).resolve()
        if args.installed_target_root
        else None
    )
    projection = _runner_target_projection(
        workspace=workspace,
        target_repository_root=target_repository_root,
        installed_target_root=installed_target_root,
    )
    protected_roots = [target_repository_root]
    if installed_target_root is not None:
        protected_roots.append(installed_target_root)
    _assert_mutation_paths_outside_roots(
        paths,
        mutable_roles=("output",),
        protected_roots=tuple(protected_roots),
    )
    try:
        result = prepare_portfolio_attempt(
            registry=_load(paths["registry"]),
            repository_root=target_repository_root,
            workspace_root=workspace,
            skill_id=args.skill_id,
            job_matrix=_load_job_matrix(paths["job_matrix"]),
            installed_target_root=installed_target_root,
        )
    except PortfolioRunnerError as exc:
        result = _portfolio_runner_failure(
            command="prepare-portfolio-run",
            error=exc,
            target_path_projection=projection,
        )
        _output(result, args.output, workspace)
        return 1
    payload = dict(result)
    payload["target_path_projection"] = projection
    payload["registry_written"] = False
    payload["published"] = False
    _output(payload, args.output, workspace)
    return 0


def execute_portfolio_run_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py execute-portfolio-run")
    _common(parser)
    parser.add_argument(
        "--target-repository-root",
        required=True,
        help="Canonical local repository root bound by the preparation receipt",
    )
    parser.add_argument("--preparation-ref", required=True)
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    paths = _assert_distinct_path_roles(
        workspace,
        registry=args.registry,
        output=args.output,
    )
    target_repository_root = Path(args.target_repository_root).resolve()
    projection = _runner_target_projection(
        workspace=workspace,
        target_repository_root=target_repository_root,
        installed_target_root=None,
    )
    _assert_mutation_paths_outside_roots(
        paths,
        mutable_roles=("output",),
        protected_roots=(target_repository_root,),
    )
    try:
        result = execute_portfolio_attempt(
            preparation_ref=args.preparation_ref,
            registry=_load(paths["registry"]),
            repository_root=target_repository_root,
            workspace_root=workspace,
        )
    except PortfolioRunnerError as exc:
        result = _portfolio_runner_failure(
            command="execute-portfolio-run",
            error=exc,
            target_path_projection=projection,
        )
        _output(result, args.output, workspace)
        return 1
    payload = dict(result)
    payload["target_path_projection"] = projection
    payload["registry_written"] = False
    payload["published"] = False
    _output(payload, args.output, workspace)
    return 0


def capture_portfolio_production_revalidation_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="skillguard.py capture-portfolio-production-revalidation"
    )
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--output", default="-")
    parser.add_argument("--target-repository-root", required=True)
    parser.add_argument("--member-skill-id", required=True)
    parser.add_argument("--member-skill-path", required=True)
    parser.add_argument(
        "--run-root",
        required=True,
        help="Workspace-local exact scheduled-production current run root",
    )
    parser.add_argument(
        "--target-root",
        required=True,
        help="Workspace-local target data/shadow root bound by the depth receipt",
    )
    parser.add_argument(
        "--owner-evidence-root",
        help=(
            "Workspace-local immutable owner evidence root used by the scheduled "
            "production checks; defaults to the target repository's standard root"
        ),
    )
    parser.add_argument("--closure-receipt-id", required=True)
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    repository_root = Path(args.target_repository_root).resolve()
    paths = _assert_distinct_path_roles(
        workspace,
        output=args.output,
        run_root=args.run_root,
        target_root=args.target_root,
    )
    _assert_mutation_paths_outside_roots(
        paths,
        mutable_roles=("output",),
        protected_roots=(repository_root,),
    )
    try:
        result = capture_portfolio_production_revalidation_binding(
            member_skill_id=args.member_skill_id,
            member_skill_path=args.member_skill_path,
            repository_root=repository_root,
            run_root=paths["run_root"],
            target_root=paths["target_root"],
            workspace_root=workspace,
            closure_receipt_id=args.closure_receipt_id,
            owner_evidence_root=(
                _workspace_path(args.owner_evidence_root, workspace)
                if args.owner_evidence_root
                else None
            ),
        )
    except PortfolioRunnerError as exc:
        result = {
            "artifact_type": "skillguard_portfolio_production_revalidation_capture",
            "status": "blocked",
            "blockers": [{"code": exc.code, "detail": exc.detail}],
            "claim_boundary": "No production binding was authorized.",
        }
        _output(result, args.output, workspace)
        return 1
    _output(result, args.output, workspace)
    return 0


def assemble_portfolio_run_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py assemble-portfolio-run")
    _common(parser)
    parser.add_argument(
        "--target-repository-root",
        required=True,
        help="Canonical local repository root bound by the preparation receipt",
    )
    parser.add_argument("--preparation-ref", required=True)
    parser.add_argument("--execution-ref", required=True)
    parser.add_argument(
        "--production-revalidation-ref",
        action="append",
        required=True,
        help=(
            "Repeat once for every target member; each ref must name a captured "
            "scheduled-production/enforced/terminal-completion binding"
        ),
    )
    parser.add_argument(
        "--installed-target-root",
        help=(
            "Non-authoritative installed copy re-scanned for final content parity; "
            "required by the runner when the prepared target is a suite"
        ),
    )
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    paths = _assert_distinct_path_roles(
        workspace,
        registry=args.registry,
        output=args.output,
    )
    target_repository_root = Path(args.target_repository_root).resolve()
    installed_target_root = (
        Path(args.installed_target_root).resolve()
        if args.installed_target_root
        else None
    )
    projection = _runner_target_projection(
        workspace=workspace,
        target_repository_root=target_repository_root,
        installed_target_root=installed_target_root,
    )
    _assert_mutation_paths_outside_roots(
        paths,
        mutable_roles=("output",),
        protected_roots=tuple(
            root
            for root in (target_repository_root, installed_target_root)
            if root is not None
        ),
    )
    try:
        result = assemble_portfolio_attempt(
            preparation_ref=args.preparation_ref,
            execution_ref=args.execution_ref,
            registry=_load(paths["registry"]),
            repository_root=target_repository_root,
            workspace_root=workspace,
            installed_target_root=installed_target_root,
            production_revalidation_refs=args.production_revalidation_ref,
        )
    except PortfolioRunnerError as exc:
        result = _portfolio_runner_failure(
            command="assemble-portfolio-run",
            error=exc,
            target_path_projection=projection,
        )
        _output(result, args.output, workspace)
        return 1
    payload = dict(result)
    payload["target_path_projection"] = projection
    payload["registry_written"] = False
    payload["published"] = False
    _output(payload, args.output, workspace)
    return 0


PORTFOLIO_COMMANDS: dict[str, Callable[[list[str]], int]] = {
    "assemble-portfolio-run": assemble_portfolio_run_command,
    "audit-portfolio": audit_portfolio_command,
    "build-current-portfolio-registry": (
        build_current_portfolio_registry_command
    ),
    "capture-portfolio-production-revalidation": (
        capture_portfolio_production_revalidation_command
    ),
    "execute-portfolio-run": execute_portfolio_run_command,
    "mark-portfolio-impact": mark_portfolio_impact_command,
    "verify-portfolio-impact-receipt": verify_portfolio_impact_receipt_command,
    "capture-installation-receipt": capture_installation_receipt_command,
    "verify-installation-receipt": verify_installation_receipt_command,
    "graduate-portfolio": graduate_portfolio_command,
    "prepare-portfolio-run": prepare_portfolio_run_command,
}
