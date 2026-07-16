# Reference 08: Checker-Change Fixture Policy

This reference defines how SkillGuard should handle fixture obligations when checker logic changes.

Checker-change fixture policy exists to prevent validation drift. A checker update should not silently weaken standards, remove coverage, or make stale fixtures look current.

## Scope

Use this policy when a SkillGuard checker, validation rule, schema rule, routing rule, status rule, privacy scan, evidence-freshness rule, or fixture interpreter changes.

This policy is generic. It does not require a specific private runtime, local test harness, or named skill family.

This policy does not claim that checker code, schemas, fixtures, tests, CLI checks, suite automation, package publication, code-contract checks, or a validation suite already exist. It defines what future checker and fixture changes must demonstrate.

## Checker-Change Triggers

A checker change should trigger fixture review when it affects:

- accepted inputs;
- rejected inputs;
- status meanings;
- hard gates;
- evidence freshness;
- closure boundaries;
- privacy or public-safety scans;
- activation-boundary checks;
- suite or child evidence aggregation;
- parser behavior;
- report fields;
- current schema/version identity and noncurrent rejection.

Pass criteria: every behavior-changing checker update names the fixture impact.

Fail criteria: checker behavior changes without reviewing fixtures.

Block criteria: fixture impact cannot be determined and the checker change affects a required gate.

## Fixture Versioning

Fixtures should identify the checker or policy version they are meant to cover.

Useful fields:

- fixture id;
- target rule;
- checker version or policy version;
- expected decision;
- expected findings;
- freshness date or source date when relevant;
- current identity notes;
- known limitations.

Pass criteria: fixture expectations are versioned or otherwise tied to a clear checker policy state.

Fail criteria: fixtures have ambiguous expectations or silently inherit changed behavior.

Block criteria: the required current identity or noncurrent-rejection decision is missing.

## Positive Fixtures

Positive fixtures show examples that should pass.

A useful positive fixture should include:

- a minimal valid target;
- required files or records;
- expected status;
- evidence fields;
- claim boundary;
- absence of privacy findings;
- no unsupported completion claims.

Positive fixtures should be narrow. They should not pass merely because the checker ignores missing required fields.

Pass criteria: positive fixtures prove accepted behavior still works.

Fail criteria: positive fixtures pass even when required evidence is absent.

Block criteria: no positive fixture exists for a required accepted behavior.

## Negative Fixtures

Negative fixtures show examples that should fail or block.

Required negative-fixture categories may include:

- missing required file;
- malformed frontmatter;
- stale evidence;
- report-only closure where direct evidence is required;
- skipped required check treated as passing;
- privacy exposure;
- hard gate downgraded to warning;
- parent overclaim hiding child failure;
- unvalidated implementation or publication claim;
- overly broad activation boundary.

Pass criteria: negative fixtures catch known unsafe or invalid behavior.

Fail criteria: negative fixtures pass unexpectedly.

Block criteria: no negative fixture exists for a high-risk rule change.

## Regression Scenarios

Regression scenarios preserve known lessons and prior fixes.

Regression fixtures should be added when:

- a checker bug is fixed;
- a reviewer finds a missed overclaim;
- a stale-evidence case was accepted incorrectly;
- a privacy scan missed unsafe material;
- a hard gate was treated as optional;
- a suite summary hid a child failure;
- a fixture itself was found stale or ambiguous.

Pass criteria: known misses are converted into reproducible regression scenarios when feasible.

Fail criteria: known misses are fixed only in prose and can recur silently.

Block criteria: the regression input cannot be stored safely because it contains private or credential material.

## Stale Fixture Handling

A fixture becomes stale when its expected behavior no longer matches the checker policy, schema, status vocabulary, or artifact shape it claims to test.

Stale fixture handling should include:

- marking the fixture stale;
- explaining why it is stale;
- deciding whether to update, archive, or replace it;
- preserving regression intent when useful;
- preventing stale fixtures from being counted as current passing evidence.

Pass criteria: stale fixtures are identified and excluded from current pass claims.

Fail criteria: stale fixtures are treated as current evidence.

Block criteria: required fixture freshness cannot be determined.

## Current Identity Expectations

Checker changes must name the sole current schema, fixture, and report identities.

Current-identity questions:

- Are former fixtures kept only as explicit rejection inputs?
- Are former result records rejected rather than read or converted?
- Does the status vocabulary change?
- Does a schema version change?
- Do public report fields change?
- Does every affected fixture get rewritten directly to the current shape?

Pass criteria: the current identity is explicit and former shapes are rejected by exact negative fixtures.

Fail criteria: more than one live identity exists or a former shape can still execute.

Block criteria: the sole current identity or former-shape rejection cannot be assessed for a required public contract.

## Evidence Requirements

A checker-change review should collect current evidence.

Evidence may include:

- changed checker files;
- changed schema or policy files;
- fixture listing;
- fixture hashes;
- positive and negative fixture results;
- skipped fixture reasons;
- current identity notes;
- reviewer judgment for semantic fixture adequacy.

Fresh evidence is required when checker behavior changes, fixture expectations change, fixture content changes, schema or status vocabulary changes, or the closure boundary changes.

Pass criteria: evidence is current and tied to the checker change.

Fail criteria: fixture evidence is missing, stale, or unrelated.

Block criteria: required fixture evidence cannot be collected.

## Absent Fixture And Automation Boundary

Checker-change policy can be reviewed even when fixture files or automation do not exist, but the absence must stay visible.

When fixtures, tests, CLI checks, suite automation, package publication evidence, or code-contract checks are absent:

- report the category as absent, not applicable, skipped, or blocked according to the selected scope;
- do not treat the absent category as passing evidence;
- do not claim regression coverage, fixture coverage, command execution, suite automation, publication, or code-contract verification;
- require separate current evidence if the category is later added, changed, or brought into scope.

Pass criteria: absent artifacts are named and excluded from pass evidence.

Fail criteria: absent fixtures or automation are described as successful checks.

Block criteria: absent artifacts are required by the selected checker-change scope and no acceptable substitute evidence exists.

## Reviewer Obligations

Reviewers should verify that checker changes do not weaken SkillGuard standards.

Reviewer checklist:

- identify the behavior change;
- inspect positive fixture coverage;
- inspect negative fixture coverage;
- check regression scenarios;
- check stale fixture handling;
- check current identity notes and former-shape rejection;
- check public-safety scans for fixture content;
- verify skipped fixtures are named with reasons;
- verify no implementation, validation-suite, package, git, hosted release, or external integration claim is made without evidence.

Pass criteria: the reviewer can explain why fixture coverage is sufficient for the checker change.

Fail criteria: coverage is too thin, stale, private, or disconnected from changed behavior.

Block criteria: required review inputs are unavailable.

## Public-Safety Requirements

Fixtures and checker-change records must be public-safe when stored in a public repository.

They should not include:

- credentials or token patterns;
- private keys;
- private local paths or usernames;
- private task payloads or transcripts;
- private coordination details;
- unnecessary copies of user data.

Unsafe real material should be reduced, redacted, or replaced with synthetic examples before being committed.

## Non-Claims

This policy does not claim that checker code exists, that schemas exist, that fixture files exist, that tests, CLI checks, suite automation, package publication, code-contract checks, or fixture tests have run, that validation-suite completion has been proven, or that AI judgment is guaranteed correct.

Those claims require separate current evidence and explicit scope.
