# Reference 03: Skill Map And Suite Map Standard

This reference defines the standard for a skill map or suite map: a public document or structured record that explains how one or more Codex skills are grouped, related, routed, validated, and maintained.

A skill map is descriptive and checkable. It does not prove that every listed skill is implemented, accepted, or release-ready.

## Scope

Use a skill map when a repository needs to explain the maintained files, references, schemas, templates, self-check records, evidence records, and validation boundaries for a target skill. Use a suite map when a repository maintains more than one skill, or when a single repository needs to explain relationships among skill-like workflows.

The standard is generic. It applies to arbitrary Codex skills and suites. It must not require any particular named skill family, private runtime topology, local machine path, or unpublished coordination system.

## Suite Identity

A suite map should name the suite and state why the skills are grouped.

Required information:

- suite name;
- short purpose;
- repository or maintained target location;
- owner or maintainer role;
- version or compatibility baseline when available;
- public claim boundary for what the map proves.

Pass criteria: the suite identity is clear and public-safe.

Fail criteria: the identity is missing, ambiguous, private, or claims readiness beyond current evidence.

Block criteria: the suite root or ownership decision is unavailable.

## Included-Skill Inventory

A suite map should list every included skill as an explicit item.

Each skill entry should include:

- skill name;
- skill entry path;
- short purpose;
- status;
- evidence location;
- current blocker or residual risk if present;
- whether the skill is required, optional, experimental, deprecated, or external.

Pass criteria: included skills are named with enough information to inspect them independently.

Fail criteria: a suite summary hides missing, stale, blocked, failed, or unreviewed child skills.

Block criteria: a child skill cannot be identified or inspected safely.

## File And Asset Mapping

A skill map should identify the concrete files and asset families that support each target skill.

Expected mapping categories include:

- skill entrypoint files such as `SKILL.md`;
- public README and root governance files;
- package and version metadata;
- reference standards;
- schemas;
- templates;
- self-check records or local maintenance records;
- scripts, fixtures, tests, examples, or suite runners when they exist;
- explicit absence rows when scripts, fixtures, tests, examples, suite runners, package publication files, or code-contract checks do not exist.

Pass criteria: every mapped category is either tied to a current path and evidence reference or explicitly marked absent, skipped, not applicable, or blocked.

Fail criteria: the map implies that missing scripts, fixtures, tests, suite automation, package publication, or code-contract checks exist or passed.

Block criteria: a required mapped file cannot be inspected or ownership prevents safe mapping.

## Declared Relationships

A suite map should describe meaningful relationships among skills.

Relationship types may include:

- parent-to-child workflow;
- prerequisite;
- optional follow-up;
- shared reference material;
- shared schema or fixture family;
- common status vocabulary;
- release grouping;
- mutual exclusion or non-overlap boundary.

Relationships should be directional when direction matters. They should be explained as operational guidance, not as a private execution trace.

Pass criteria: relationships are explicit, inspectable, and do not imply hidden success.

Fail criteria: relationship claims are vague, circular, contradicted by child evidence, or used to hide missing child checks.

Block criteria: the relationship is required for the suite claim but cannot be determined from current materials.

## Routing Hints

Routing hints explain when a user or agent should choose one skill over another.

Useful routing hints include:

- trigger phrases or task shapes;
- non-trigger examples;
- required input materials;
- handoff conditions;
- conflict resolution rules;
- blocked-when-no-route conditions.

Routing hints should remain recommendations for skill selection. Future model activation remains outside the map's proof.

Pass criteria: routing hints clarify use and non-use boundaries for the included skills.

Fail criteria: routing hints are too broad, overlap without a conflict rule, or imply future activation certainty.

Block criteria: multiple skills claim the same task with no safe default or documented resolution.

## Evidence Expectations

A suite map should state which evidence is required for a suite-level claim.

Evidence may include:

- current child skill hashes or versions;
- child status reports;
- deterministic check outputs;
- structured judgment records;
- fixture results;
- suite-level validation results;
- freshness timestamps;
- skipped checks with reasons.

Suite evidence must remain tied to child evidence. A parent summary is stale when child files change or child evidence expires.

Pass criteria: suite evidence identifies the child evidence it depends on.

Fail criteria: suite evidence is missing, stale, unverifiable, or detached from child files.

Block criteria: required child evidence is unavailable and the suite claim depends on it.

## Parent And Child Status Rollup

A suite or parent map may summarize child status only after child evidence remains visible.

Rollup rules:

- A missing required child keeps the parent from being accepted.
- A blocked child blocks the affected parent scope.
- Stale child evidence makes the parent evidence stale for dependent claims.
- Skipped child checks must be named and cannot be counted as passing.
- A child that needs review keeps the parent at `needs-review` or an equivalent visible blocker for that claim.
- A parent `checked` or `accepted` label applies only to the exact scope supported by current child evidence.

Pass criteria: parent status is no stronger than the child evidence and skipped checks it cites.

Fail criteria: parent status hides missing, blocked, stale, skipped, failed, or unreviewed child evidence.

Block criteria: required child status or freshness cannot be determined.

## Maintenance Ownership

A suite map should state who or what owns maintenance for the suite and for each child skill.

Ownership can be a person, team, repository role, or documented maintainer process. It should not be a private local runtime detail.

Pass criteria: maintainers can tell who updates suite membership, routing hints, evidence rules, and compatibility boundaries.

Fail criteria: ownership is missing or points to private workspace state.

Block criteria: ownership is required to resolve a conflict and no public-safe owner is available.

## Compatibility And Version Boundaries

When a suite map uses versions, it should describe compatibility boundaries without overstating them.

Useful fields include:

- suite version;
- child skill version;
- minimum supported schema or metadata version;
- known incompatible versions;
- migration status;
- accepted compatibility evidence.

Pass criteria: compatibility claims cite current child versions and evidence.

Fail criteria: compatibility is asserted without evidence or conflicts with child metadata.

Block criteria: a required version or compatibility decision is missing.

## Status Reporting

A suite map may use the shared status vocabulary from Reference 01.

Recommended suite statuses:

- `draft`: the map exists but child evidence is incomplete.
- `checked`: map structure and child references were checked.
- `needs-review`: relationship or routing judgment is required.
- `blocked`: a required child, relationship, credential, or decision is missing.
- `stale`: child evidence changed or expired.
- `accepted`: the suite map has current structure, child evidence, and required judgments for the stated scope.

Pass criteria: suite status is no stronger than the child evidence it cites.

Fail criteria: suite status hides child failures or treats skipped checks as passing.

Block criteria: required child status is unavailable.

## Non-Claims

A suite map does not by itself prove that:

- every listed skill is implemented;
- every listed skill passed its own standard;
- routing will always be selected correctly by a future model;
- the map does not prove implementation scripts, schemas, fixtures, command-line tools, package publication, git commits, hosted releases, or external integrations exist;
- the map does not prove AI judgment is guaranteed correct.

Those claims require their own current evidence.

## Privacy And Public Boundary

Skill maps and suite maps are public-facing maintenance artifacts unless explicitly marked otherwise. They should not include credentials, secrets, tokens, API keys, private keys, private task payloads, internal coordination records, private transcripts, local absolute paths, user-specific filesystem details, or private runtime identifiers.

Public maps should use repository-relative paths and portable role names. Private workspace state is not evidence for a public map.

## Minimum Review Checklist

Before accepting a suite map, verify:

- suite identity is clear;
- included skills are listed;
- relationships are explicit;
- routing hints include use and non-use boundaries;
- evidence expectations are tied to child evidence;
- ownership is public-safe;
- compatibility and version claims are bounded;
- status reporting does not overclaim;
- no private or credential material is present.
