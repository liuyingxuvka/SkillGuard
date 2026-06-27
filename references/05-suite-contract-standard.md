# Reference 05: Suite Contract Standard

This reference defines the standard for a suite contract. A suite contract is the public agreement that explains what a collection of skills contains, how skills relate to each other, how evidence is shared, which compatibility boundaries matter, and how suite-level status is reported.

A suite contract extends a suite map. The map explains the current grouping; the contract defines the obligations that make suite-level claims acceptable.

## Scope

Use this standard when a repository or maintained target claims a collection of skills works together.

The standard is generic. It applies to arbitrary Codex skill suites and must not require a specific named skill family, private runtime topology, or local coordination system.

The standard does not certify that a suite is implemented, validated, published, externally integrated, backed by tests, backed by CLI checks, backed by suite automation, or backed by code-contract checks unless those claims are explicitly in scope and directly checked.

## Suite Purpose

The suite contract should state why the suite exists.

Required information:

- suite name;
- problem or maintenance domain;
- included-skill boundary;
- excluded-skill boundary;
- public claim boundary.

Pass criteria: the suite purpose is clear and bounded.

Fail criteria: the suite purpose is vague, private, or broader than included-skill evidence supports.

Block criteria: the purpose or boundary cannot be determined.

## Included-Skill Inventory

The suite contract should require an inventory of included skills.

Each item should include:

- skill name;
- skill path;
- role in the suite;
- version or compatibility field when applicable;
- current status;
- evidence source;
- owner or maintainer role;
- blockers and residual risks.

Pass criteria: every included skill can be inspected independently.

Fail criteria: child skills are unnamed, hidden behind parent status, or missing evidence.

Block criteria: required child inventory cannot be collected.

## Inter-Skill Routing

The suite contract should state how tasks route among skills.

Routing information may include:

- primary use cases;
- non-use cases;
- handoff conditions;
- conflict resolution;
- blocked-when-no-route behavior;
- blocked conditions;
- examples that remain generic and public-safe.

Pass criteria: routing rules clarify which skill should handle which task without guaranteeing future model activation.

Fail criteria: routing rules overlap, contradict child contracts, or imply guaranteed activation.

Block criteria: two or more required skills claim the same task and no resolution rule exists.

## Dependency Declarations

The suite contract should declare dependencies among skills and shared artifacts.

Dependency types may include:

- prerequisite skill;
- optional follow-up skill;
- shared reference;
- shared schema;
- shared fixture family;
- shared command;
- shared status vocabulary;
- external credential or service dependency.

Dependencies should include required, optional, experimental, deprecated, or external labels where useful.

Pass criteria: dependencies are explicit and do not hide missing child evidence.

Fail criteria: dependencies are implicit, circular, stale, or contradicted by child contracts.

Block criteria: a required dependency cannot be resolved or inspected.

## Shared Evidence Rules

The suite contract should define how evidence can be shared across skills.

Shared evidence is acceptable only when:

- the evidence names the files or records it covers;
- the covered files are unchanged or freshness has been rechecked;
- child-specific checks are not replaced by unrelated parent evidence;
- skipped checks remain visible;
- judgment records are not presented as deterministic proof.

Pass criteria: shared evidence is tied to current child files and suite claims.

Fail criteria: shared evidence is stale, overbroad, detached from child files, or used to hide failed child checks.

Block criteria: required evidence cannot be traced to current files.

## Compatibility And Version Boundaries

The suite contract should define compatibility expectations.

Useful compatibility fields include:

- suite version;
- child skill version;
- minimum supported metadata version;
- supported schema version;
- fixture compatibility;
- known incompatible combinations;
- migration status;
- deprecation status.

Pass criteria: compatibility claims are bounded and tied to current metadata.

Fail criteria: version claims diverge, compatibility is untested but asserted, or deprecated items are presented as accepted without a boundary.

Block criteria: required version or compatibility information is missing.

## Suite Validation

Suite validation should check both structure and evidence.

Expected validation layers:

- suite contract parses or can be read;
- included skills exist;
- child skill contracts satisfy their own required gates;
- declared dependencies resolve;
- routing conflicts are identified;
- shared evidence is fresh;
- compatibility boundaries are checked;
- privacy and public-safety scans pass;
- suite-level status does not exceed child evidence.

Pass criteria: required suite validation layers pass for the stated scope.

Fail criteria: a required validation layer fails.

Block criteria: a required validation layer cannot run because files, tools, credentials, owner decisions, or safe-edit boundaries are missing.

Skipped validation layers must be listed with reasons.

## Maintenance Ownership

The suite contract should define who maintains the suite and child relationships.

Ownership information should cover:

- suite contract owner;
- child skill owner;
- dependency owner;
- evidence owner;
- version and compatibility owner;
- release decision owner when release is in scope.

Pass criteria: ownership is public-safe and sufficient to resolve maintenance questions.

Fail criteria: ownership is missing, private, or contradicted by child records.

Block criteria: an owner decision is required but unavailable.

## Status Reporting

Suite status must be no stronger than current child evidence.

Recommended report fields:

- suite target;
- included skills;
- decision: `pass`, `fail`, or `block`;
- child statuses;
- suite evidence;
- dependency findings;
- compatibility findings;
- routing findings;
- privacy findings;
- skipped checks;
- residual risk;
- claim boundary.

Pass criteria: the suite report exposes child evidence and supports the stated decision.

Fail criteria: the report hides child failures, treats skipped checks as passing, or claims suite acceptance while required children are missing, stale, blocked, failed, or unreviewed.

Block criteria: required child evidence, dependency information, compatibility evidence, or owner decisions are missing.

## Public-Safety Requirements

The suite contract and suite map must be safe for public repositories.

They should not contain:

- credentials, tokens, private keys, or environment secrets;
- private local paths or usernames;
- private task payloads or transcripts;
- internal coordination records;
- required dependency on a private named workflow;
- unvalidated claims of hosted releases, package publication, git commits, external service integration, or completed validation suites.

Pass criteria: public-safety scan is clean for the stated scope.

Fail criteria: unsafe public content is present.

Block criteria: unsafe content cannot be removed without an owner decision.

## Non-Claims

Accepting a suite contract does not by itself prove that:

- every child skill is accepted;
- every route will be chosen correctly by a future model;
- every dependency is installed;
- every schema, fixture, script, test, CLI check, suite automation runner, code-contract check, or command-line tool exists;
- package publication is complete;
- git commits or hosted release pages exist;
- external services are configured;
- AI judgment is guaranteed correct.

Those claims require current evidence and explicit scope.

## Minimum Review Checklist

Before accepting a suite contract, verify:

- suite purpose is bounded;
- included-skill inventory is complete for the stated scope;
- inter-skill routing is explicit;
- dependencies are declared;
- shared evidence rules preserve child evidence;
- compatibility and version boundaries are clear;
- suite validation layers are stated;
- maintenance ownership is public-safe;
- status reporting exposes child states;
- public-safety and no-overclaim scans are clean.
