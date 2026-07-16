"""Portable repository adoption for SkillGuard-maintained skill projects."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_schema import DEPTH_INTEGRATION_MODES, PROJECT_ADOPTION_SCHEMA
from .validation_execution_policy import (
    VALIDATION_EXECUTION_POLICY_ID,
    VALIDATION_EXECUTION_POLICY_LINES,
)


SKILLGUARD_REPOSITORY = "https://github.com/liuyingxuvka/SkillGuard"
BEGIN_MARKER = "<!-- BEGIN MANAGED SKILLGUARD PROJECT RULES -->"
END_MARKER = "<!-- END MANAGED SKILLGUARD PROJECT RULES -->"
MANIFEST_RELATIVE_PATH = Path(".skillguard") / "project.json"
PROJECT_MANIFEST_FIELDS = {
    "schema_version",
    "project_id",
    "skillguard_repository",
    "skillguard_version",
    "project_prompt_path",
    "managed_skills",
    "maintenance_default",
    "claim_boundary",
    "managed_block_hash",
    "manifest_hash",
}
PROJECT_MANAGED_SKILL_FIELDS = {
    "skill_path",
    "skill_id",
    "integration_mode",
    "native_owner_id",
    "native_route_status",
    "native_route_evidence_path",
}


class ProjectAdoptionError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _hash(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest().upper()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _normalize_skill_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    project_id: str,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows):
        skill_path = Path(str(raw.get("skill_path", ""))).as_posix().strip("/")
        integration_mode = str(raw.get("integration_mode", ""))
        native_owner_id = str(raw.get("native_owner_id", "")).strip()
        if not skill_path or skill_path.startswith("../") or ":" in skill_path:
            raise ProjectAdoptionError("managed_skill_path_invalid", f"row {index}: {skill_path}")
        if skill_path in seen:
            raise ProjectAdoptionError("managed_skill_duplicate", skill_path)
        if integration_mode not in DEPTH_INTEGRATION_MODES:
            raise ProjectAdoptionError("managed_skill_integration_mode_invalid", integration_mode)
        if not native_owner_id:
            raise ProjectAdoptionError("managed_skill_native_owner_missing", skill_path)
        route_status = "present"
        is_root_skill = skill_path == "."
        skill_id = project_id if is_root_skill else Path(skill_path).name
        native_route_evidence_path = "SKILL.md" if is_root_skill else f"{skill_path}/SKILL.md"
        normalized.append(
            {
                "skill_path": skill_path,
                "skill_id": skill_id,
                "integration_mode": integration_mode,
                "native_owner_id": native_owner_id,
                "native_route_status": route_status,
                "native_route_evidence_path": native_route_evidence_path,
            }
        )
        seen.add(skill_path)
    if not normalized:
        raise ProjectAdoptionError("managed_skills_missing", "at least one managed skill is required")
    return sorted(normalized, key=lambda row: row["skill_path"].casefold())


def build_project_manifest(
    project_root: Path,
    managed_skills: Sequence[Mapping[str, Any]],
    *,
    skillguard_version: str,
) -> dict[str, Any]:
    rows = _normalize_skill_rows(managed_skills, project_id=project_root.resolve().name)
    for row in rows:
        evidence_path = project_root / row["native_route_evidence_path"]
        if not evidence_path.is_file():
            raise ProjectAdoptionError(
                "native_route_evidence_missing",
                row["native_route_evidence_path"],
            )
    manifest: dict[str, Any] = {
        "schema_version": PROJECT_ADOPTION_SCHEMA,
        "project_id": project_root.resolve().name,
        "skillguard_repository": SKILLGUARD_REPOSITORY,
        "skillguard_version": skillguard_version or "unknown",
        "project_prompt_path": "AGENTS.md",
        "managed_skills": rows,
        "maintenance_default": "skillguard-required-for-nontrivial-skill-work",
        "claim_boundary": (
            "Project adoption makes SkillGuard maintenance instructions portable and auditable. "
            "It does not prove that target-owned domain routes or depth checks have run."
        ),
    }
    block = render_project_block(manifest)
    manifest["managed_block_hash"] = _text_hash(block)
    manifest["manifest_hash"] = _hash(manifest)
    return manifest


def render_project_block(manifest: Mapping[str, Any]) -> str:
    rows = manifest.get("managed_skills", [])
    skill_lines = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        skill_lines.append(
            f"- `{str(row.get('skill_path', ''))}` — native owner="
            f"`{str(row.get('native_owner_id', ''))}`, route evidence="
            f"`{str(row.get('native_route_evidence_path', ''))}`; the target skill keeps domain-route, "
            "judgment, action, and native-check authority."
        )
    body = [
        BEGIN_MARKER,
        "## SkillGuard project maintenance",
        "",
        "This repository contains skills maintained with SkillGuard. For non-trivial skill maintenance, "
        "validation, installation, synchronization, or release work, use SkillGuard by default.",
        "",
        f"Canonical SkillGuard repository: {SKILLGUARD_REPOSITORY}",
        "",
        "Managed skills:",
        *skill_lines,
        "",
        "Required maintenance handoff:",
        "",
        "1. Read the target skill's `SKILL.md` and its native route/check contracts before editing.",
        "2. Use SkillGuard to inventory, run every target-declared check, reconcile exact receipts, and close non-trivial skill changes.",
        "3. Preserve the target's sole current native route and exact declared checks; SkillGuard never supplies a target-domain route.",
        "4. Never let SkillGuard replace target-owned domain judgment, simulation, search, modeling, actions, or checks.",
        "5. Do not claim complete use from contract presence alone; require a current declared-check execution receipt.",
        "6. If SkillGuard is unavailable or this block/manifest is missing, stale, duplicated, or invalid, "
        "report the maintenance result as blocked instead of silently bypassing it.",
        "",
        "Validation execution ownership:",
        "",
        f"- policy_id: `{VALIDATION_EXECUTION_POLICY_ID}`",
        *VALIDATION_EXECUTION_POLICY_LINES,
        "",
        "Portable audit command: `python <installed-skillguard>/scripts/skillguard.py project-audit --root .`",
        "",
        "This managed block is a routing and maintenance contract. It is not runtime, test, release, or future-behavior proof.",
        END_MARKER,
    ]
    return "\n".join(body) + "\n"


def _extract_managed_block(text: str) -> tuple[str | None, list[str]]:
    findings: list[str] = []
    begin_count = text.count(BEGIN_MARKER)
    end_count = text.count(END_MARKER)
    if begin_count != 1:
        findings.append(f"managed_begin_marker_count:{begin_count}")
    if end_count != 1:
        findings.append(f"managed_end_marker_count:{end_count}")
    if findings:
        return None, findings
    begin = text.index(BEGIN_MARKER)
    end = text.index(END_MARKER, begin) + len(END_MARKER)
    if end < len(text) and text[end : end + 1] == "\n":
        end += 1
    return text[begin:end], findings


def _replace_block(text: str, block: str) -> str:
    begin_count = text.count(BEGIN_MARKER)
    end_count = text.count(END_MARKER)
    if begin_count == 0 and end_count == 0:
        separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
        return f"{text}{separator}{block}"
    if begin_count != 1 or end_count != 1:
        raise ProjectAdoptionError(
            "managed_block_marker_invalid",
            f"begin={begin_count} end={end_count}",
        )
    begin = text.index(BEGIN_MARKER)
    end = text.index(END_MARKER, begin) + len(END_MARKER)
    if end < len(text) and text[end : end + 1] == "\n":
        end += 1
    return f"{text[:begin]}{block}{text[end:]}"


def _atomic_compare_and_write(path: Path, data: bytes, expected: bytes | None) -> bool:
    current = path.read_bytes() if path.is_file() else None
    if current != expected:
        raise ProjectAdoptionError("peer_write_detected", path.as_posix())
    if current == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)
    return True


def _read_manifest(project_root: Path) -> Mapping[str, Any] | None:
    path = project_root / MANIFEST_RELATIVE_PATH
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectAdoptionError("project_manifest_unreadable", type(exc).__name__) from exc
    if not isinstance(payload, Mapping):
        raise ProjectAdoptionError("project_manifest_not_object", path.as_posix())
    return payload


def _require_current_project_manifest(
    project_root: Path,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if manifest is None:
        raise ProjectAdoptionError("project_manifest_missing", "run project-adopt with explicit current managed skills")
    if set(manifest) != PROJECT_MANIFEST_FIELDS:
        raise ProjectAdoptionError(
            "project_manifest_shape_not_current",
            "project manifest fields must exactly match the sole current schema",
        )
    if manifest.get("schema_version") != PROJECT_ADOPTION_SCHEMA:
        raise ProjectAdoptionError("project_manifest_schema_mismatch", "former project manifest shapes are rejection-only")
    if manifest.get("project_id") != project_root.resolve().name:
        raise ProjectAdoptionError("project_manifest_project_mismatch", str(manifest.get("project_id", "")))
    if manifest.get("skillguard_repository") != SKILLGUARD_REPOSITORY:
        raise ProjectAdoptionError("skillguard_repository_mismatch", str(manifest.get("skillguard_repository", "")))
    if manifest.get("project_prompt_path") != "AGENTS.md":
        raise ProjectAdoptionError("project_prompt_path_mismatch", str(manifest.get("project_prompt_path", "")))
    rows = manifest.get("managed_skills")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise ProjectAdoptionError("managed_skills_not_canonical", "managed_skills must be a list of current rows")
    if any(set(row) != PROJECT_MANAGED_SKILL_FIELDS for row in rows):
        raise ProjectAdoptionError("managed_skills_not_canonical", "managed skill rows must use only current fields")
    normalized = _normalize_skill_rows(rows, project_id=project_root.resolve().name)
    if normalized != rows:
        raise ProjectAdoptionError("managed_skills_not_canonical", "managed skill rows are not canonically normalized")
    unsigned = dict(manifest)
    stored_manifest_hash = str(unsigned.pop("manifest_hash", ""))
    if not stored_manifest_hash or stored_manifest_hash != _hash(unsigned):
        raise ProjectAdoptionError("project_manifest_hash_mismatch", "manifest hash does not match current canonical content")
    expected_block_hash = _text_hash(render_project_block(manifest))
    if manifest.get("managed_block_hash") != expected_block_hash:
        raise ProjectAdoptionError("managed_block_hash_mismatch", "managed block hash is not current")
    expected = build_project_manifest(
        project_root,
        normalized,
        skillguard_version=str(manifest.get("skillguard_version") or "unknown"),
    )
    if dict(manifest) != expected:
        raise ProjectAdoptionError(
            "project_manifest_not_current",
            "project manifest does not equal the sole current canonical shape",
        )
    return expected


def audit_project_adoption(project_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    findings: list[str] = []
    authority_rows: list[dict[str, Any]] = []
    manifest_path = project_root / MANIFEST_RELATIVE_PATH
    agents_path = project_root / "AGENTS.md"
    try:
        manifest = _read_manifest(project_root)
    except ProjectAdoptionError as exc:
        manifest = None
        findings.append(exc.code)
    if manifest is None:
        findings.append("project_manifest_missing")
    else:
        try:
            _require_current_project_manifest(project_root, manifest)
        except ProjectAdoptionError as exc:
            findings.append(exc.code)
        if manifest.get("schema_version") != PROJECT_ADOPTION_SCHEMA:
            findings.append("project_manifest_schema_mismatch")
        if manifest.get("skillguard_repository") != SKILLGUARD_REPOSITORY:
            findings.append("skillguard_repository_mismatch")
        unsigned = dict(manifest)
        stored_manifest_hash = str(unsigned.pop("manifest_hash", ""))
        if not stored_manifest_hash or stored_manifest_hash != _hash(unsigned):
            findings.append("project_manifest_hash_mismatch")
        try:
            normalized = _normalize_skill_rows(
                [row for row in manifest.get("managed_skills", []) if isinstance(row, Mapping)],
                project_id=project_root.name,
            )
        except ProjectAdoptionError as exc:
            normalized = []
            findings.append(exc.code)
        if normalized and normalized != manifest.get("managed_skills"):
            findings.append("managed_skills_not_canonical")
        for row in normalized:
            skill_root = project_root / row["skill_path"]
            try:
                skill_root.resolve().relative_to(project_root)
            except ValueError:
                findings.append(f"managed_skill_outside_project:{row['skill_path']}")
                continue
            if not (skill_root / "SKILL.md").is_file():
                findings.append(f"managed_skill_entrypoint_missing:{row['skill_path']}")
            from .runtime_authority import (
                AUTHORITY_CURRENT,
                resolve_runtime_authority,
            )

            authority = resolve_runtime_authority(skill_root)
            authority_rows.append(
                {
                    "skill_id": row["skill_id"],
                    "skill_path": row["skill_path"],
                    "authority": authority.authority,
                    "ok": authority.ok,
                    "blockers": list(authority.blockers),
                }
            )
            if not authority.ok or authority.authority != AUTHORITY_CURRENT:
                findings.append(
                    f"runtime_authority_blocked:{row['skill_path']}:{','.join(authority.blockers)}"
                )
            evidence_path = project_root / row["native_route_evidence_path"]
            if not evidence_path.is_file():
                findings.append(
                    f"native_route_evidence_missing:{row['native_route_evidence_path']}"
                )
    if not agents_path.is_file():
        findings.append("agents_prompt_missing")
        block = None
    else:
        block, marker_findings = _extract_managed_block(agents_path.read_text(encoding="utf-8"))
        findings.extend(marker_findings)
    if manifest is not None and block is not None:
        expected_block = render_project_block(manifest)
        if block != expected_block:
            findings.append("managed_block_stale")
        if manifest.get("managed_block_hash") != _text_hash(block):
            findings.append("managed_block_hash_mismatch")
        if SKILLGUARD_REPOSITORY not in block:
            findings.append("skillguard_repository_link_missing")
    findings = sorted(dict.fromkeys(findings))
    return {
        "schema_version": "skillguard.project_audit_result.v1",
        "project_id": project_root.name,
        "status": "pass" if not findings else "blocked",
        "ok": not findings,
        "findings": findings,
        "manifest_path": MANIFEST_RELATIVE_PATH.as_posix(),
        "project_prompt_path": "AGENTS.md",
        "skillguard_repository": SKILLGUARD_REPOSITORY,
        "runtime_authorities": authority_rows,
        "claim_boundary": (
            "A pass proves current portable project-maintenance instructions and manifest integrity only; "
            "it does not prove target skill execution depth or release readiness."
        ),
    }


def adopt_project(
    project_root: Path,
    managed_skills: Sequence[Mapping[str, Any]],
    *,
    skillguard_version: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    if not project_root.is_dir():
        raise ProjectAdoptionError("project_root_missing", project_root.as_posix())
    agents_path = project_root / "AGENTS.md"
    manifest_path = project_root / MANIFEST_RELATIVE_PATH
    old_agents = agents_path.read_bytes() if agents_path.is_file() else None
    old_manifest = manifest_path.read_bytes() if manifest_path.is_file() else None
    if manifest_path.is_file():
        current = audit_project_adoption(project_root)
        if current["ok"]:
            return {**current, "action": "project-adopt", "changed": False, "status": "pass"}
        # Reapply the sole current shape from explicit caller-owned inputs.  The
        # non-current manifest is never interpreted, converted, or used as a
        # source of managed-skill rows.
    manifest = build_project_manifest(
        project_root,
        managed_skills,
        skillguard_version=skillguard_version,
    )
    block = render_project_block(manifest)
    old_text = old_agents.decode("utf-8") if old_agents is not None else ""
    new_text = _replace_block(old_text, block)
    changed = old_agents != new_text.encode("utf-8") or old_manifest != _canonical_bytes(manifest)
    if not dry_run:
        _atomic_compare_and_write(agents_path, new_text.encode("utf-8"), old_agents)
        _atomic_compare_and_write(manifest_path, _canonical_bytes(manifest), old_manifest)
        audit = audit_project_adoption(project_root)
        if not audit["ok"]:
            raise ProjectAdoptionError("project_adoption_postwrite_audit_failed", ",".join(audit["findings"]))
    else:
        audit = {
            "ok": True,
            "status": "planned",
            "findings": [],
            "claim_boundary": "Dry run only; no project files were changed or proven current.",
        }
    return {
        **audit,
        "action": "project-adopt",
        "changed": changed,
        "dry_run": dry_run,
        "managed_skills": manifest["managed_skills"],
        "skillguard_repository": SKILLGUARD_REPOSITORY,
    }


def _parser(command: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"skillguard.py {command}")
    parser.add_argument("--root", required=True)
    if command != "project-audit":
        parser.add_argument(
            "--managed-skill",
            action="append",
            default=[],
            metavar="PATH|NATIVE_OWNER",
        )
        parser.add_argument("--skillguard-version")
        parser.add_argument("--dry-run", action="store_true")
    return parser


def _parse_managed_skill(value: str) -> dict[str, str]:
    parts = value.split("|")
    if len(parts) != 2:
        raise ProjectAdoptionError(
            "managed_skill_argument_invalid",
            "expected PATH|NATIVE_OWNER",
        )
    return {
        "skill_path": parts[0],
        "integration_mode": "native-integrated",
        "native_owner_id": parts[1],
    }


def _emit(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def project_audit_command(argv: list[str]) -> int:
    args = _parser("project-audit").parse_args(argv)
    report = audit_project_adoption(Path(args.root))
    _emit(report)
    return 0 if report["ok"] else 1


def project_adopt_command(argv: list[str]) -> int:
    args = _parser("project-adopt").parse_args(argv)
    root = Path(args.root).resolve()
    rows = [_parse_managed_skill(value) for value in args.managed_skill]
    skillguard_version = str(args.skillguard_version) if args.skillguard_version else "unknown"
    report = adopt_project(
        root,
        rows,
        skillguard_version=skillguard_version,
        dry_run=args.dry_run,
    )
    _emit(report)
    return 0 if report.get("ok") else 1
