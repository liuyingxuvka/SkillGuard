"""Pure pre-write validation for SkillGuard author-maintenance execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


AUTHOR_REPOSITORY_ROLE = "skill_maintainer_source"


@dataclass(frozen=True)
class AuthorContextError(ValueError):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class AuthorMaintenanceContext:
    repository_role: str
    maintenance_unit_id: str
    member_skill_id: str
    author_repository_root: Path
    skill_root: Path
    target_root: Path
    run_state_root: Path
    owner_evidence_root: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "repository_role": self.repository_role,
            "maintenance_unit_id": self.maintenance_unit_id,
            "member_skill_id": self.member_skill_id,
            "author_repository_root": self.author_repository_root.as_posix(),
            "skill_root": self.skill_root.as_posix(),
            "target_root": self.target_root.as_posix(),
            "run_state_root": self.run_state_root.as_posix(),
            "owner_evidence_root": self.owner_evidence_root.as_posix(),
        }


def _require_under(path: Path, root: Path, code: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise AuthorContextError(code, f"{path} is outside {root}") from exc


def validate_author_maintenance_context(
    *,
    contract: Mapping[str, Any],
    skill_root: Path,
    target_root: Path,
    author_repository_root: Path,
    run_state_root: Path | None,
    owner_evidence_root: Path | None,
) -> AuthorMaintenanceContext:
    """Validate author eligibility without creating or changing any path."""

    repository_root = author_repository_root.resolve()
    resolved_skill_root = skill_root.resolve()
    resolved_target_root = target_root.resolve()
    if not repository_root.is_dir():
        raise AuthorContextError(
            "author_repository_root_missing",
            str(repository_root),
        )
    _require_under(
        resolved_skill_root,
        repository_root,
        "skill_root_outside_author_repository",
    )
    _require_under(
        resolved_target_root,
        repository_root,
        "target_root_outside_author_repository",
    )

    repository_role = str(contract.get("repository_role", ""))
    if repository_role != AUTHOR_REPOSITORY_ROLE:
        raise AuthorContextError(
            "author_repository_role_required",
            f"expected {AUTHOR_REPOSITORY_ROLE}, got {repository_role or '<missing>'}",
        )
    maintenance_unit_id = str(contract.get("maintenance_unit_id", ""))
    member_skill_id = str(contract.get("skill_id", ""))
    member_skill_ids = contract.get("member_skill_ids", [])
    if not maintenance_unit_id:
        raise AuthorContextError(
            "maintenance_unit_id_required",
            "the compiled author contract must name one maintenance unit",
        )
    if (
        not member_skill_id
        or not isinstance(member_skill_ids, list)
        or member_skill_id not in member_skill_ids
    ):
        raise AuthorContextError(
            "member_skill_identity_invalid",
            "the contract skill must be a declared member of its maintenance unit",
        )
    if run_state_root is None:
        raise AuthorContextError(
            "author_run_state_root_required",
            "author supervision requires an explicit run-state root",
        )
    if owner_evidence_root is None:
        raise AuthorContextError(
            "author_owner_evidence_root_required",
            "author supervision requires an explicit owner-evidence root",
        )
    resolved_run_state_root = run_state_root.resolve()
    resolved_owner_evidence_root = owner_evidence_root.resolve()
    if resolved_run_state_root == resolved_target_root:
        raise AuthorContextError(
            "author_run_state_must_not_equal_target",
            "run state cannot fall back to the maintained target root",
        )
    if resolved_owner_evidence_root == resolved_target_root:
        raise AuthorContextError(
            "author_owner_evidence_must_not_equal_target",
            "owner evidence cannot fall back to the maintained target root",
        )

    return AuthorMaintenanceContext(
        repository_role=repository_role,
        maintenance_unit_id=maintenance_unit_id,
        member_skill_id=member_skill_id,
        author_repository_root=repository_root,
        skill_root=resolved_skill_root,
        target_root=resolved_target_root,
        run_state_root=resolved_run_state_root,
        owner_evidence_root=resolved_owner_evidence_root,
    )
