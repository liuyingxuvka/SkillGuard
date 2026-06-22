# Reference 07: Structured AI Judgments

This reference defines how SkillGuard uses AI judgment. AI judgment can help evaluate semantics, clarity, activation boundaries, overclaim risk, and residual risk, but it must remain bounded by current evidence and hard gates.

AI judgment complements deterministic checks. It does not replace them.

## Scope

Use this standard when a SkillGuard task asks an AI reviewer to inspect a skill, reference, checker result, fixture policy, suite map, or public release claim.

AI judgment is appropriate for interpretive questions such as:

- whether an activation boundary is too broad;
- whether a do-not-use boundary is clear;
- whether evidence supports a claim boundary;
- whether public wording overclaims;
- whether residual risk is material;
- whether suite summaries hide child evidence problems.

AI judgment is not appropriate as a substitute for reading required files, parsing metadata, running required deterministic checks, or collecting required direct evidence.

## Allowed Judgment Inputs

AI judgment should use current and authorized inputs.

Allowed inputs may include:

- current file contents;
- current file listings;
- parser or command output;
- hashes or line counts;
- existing status records;
- fixture results;
- checker output;
- user-provided requirements;
- public repository documentation;
- prior reports only when freshness is known.

Inputs should be named in the judgment record. If a required input is missing, the judgment should report a blocker or skipped check instead of inventing evidence.

## Required Output Fields

A structured AI judgment should include:

- target;
- scope;
- input evidence reviewed;
- decision or recommendation;
- findings;
- confidence;
- uncertainty;
- blockers;
- skipped checks;
- residual risk;
- claim boundary;
- reviewer identity or process label;
- review timestamp when available.

Pass criteria: output fields are complete enough for a reviewer to audit the reasoning.

Fail criteria: the judgment gives a verdict without evidence, hides uncertainty, or omits blockers.

Block criteria: required inputs are missing and the reviewer cannot make an evidence-backed judgment.

## Confidence And Uncertainty

Confidence should describe how strongly the evidence supports the judgment, not how authoritative the model feels.

Useful confidence language:

- high confidence because direct evidence is complete and consistent;
- medium confidence because evidence is current but interpretation is judgment-heavy;
- low confidence because evidence is partial, ambiguous, or dependent on future work;
- blocked because required evidence is missing.

Uncertainty should be explicit. Do not convert uncertainty into a pass when a hard gate depends on it.

## Blocker Handling

AI judgment must preserve blockers.

A blocker should remain a blocker when:

- required evidence is missing;
- required files cannot be inspected;
- a required parser or checker is unavailable;
- public-safety risk is present;
- activation scope cannot be determined;
- ownership or release decisions are missing;
- hard gates cannot be checked.

AI reviewers should recommend a resolution, but they must not hide blockers in narrative prose.

## Residual-Risk Disposition

Residual risk should be separated from failed or missing checks.

AI judgment may identify residual risk after required checks pass or are properly scoped out. It should not reclassify a failed hard gate as residual risk.

Examples of residual risk:

- future model activation is not guaranteed;
- future external service availability may change;
- semantic review may miss a subtle ambiguity;
- downstream implementation remains outside the current scope.

## Overclaim Prevention

AI judgment should actively look for overclaims.

Common overclaims:

- claiming complete skill implementation when only references exist;
- claiming commands pass when they were not run;
- claiming fixtures exist when only policy exists;
- claiming tests, CLI checks, suite automation, package publication, code-contract checks, git commits, hosted releases, or external integrations are complete without current evidence;
- claiming AI correctness or guaranteed future activation.

The judgment should quote or identify the risky claim and state the narrower claim that current evidence supports.

## Hard-Gate Limits

AI judgment cannot waive hard gates unless the workflow defines an explicit waiver path with authority, reason, and downstream visibility.

Without such a waiver path, the AI reviewer must treat failed or unchecked hard gates as failures, blockers, or skipped checks.

Hard gates include required files, frontmatter validity, required sections, privacy scans, evidence freshness, parent-child evidence alignment, and public claim boundaries.

## Auditability

Structured AI judgment should be auditable.

An auditor should be able to see:

- what files or records were reviewed;
- what evidence supported each finding;
- which checks were deterministic and which were judgment-based;
- which assumptions were made;
- which limitations remain;
- what would change the decision.

Judgment without auditability should not be used as acceptance evidence for a hard gate.

## Deterministic Check Boundary

Deterministic checks answer direct questions with current file, parser, or command evidence. AI judgment should not pretend to have run those checks.

If a report says a parser ran, a command passed, or a fixture matched, the report must have current output or a clear reference to current output.

When deterministic evidence is missing, the AI reviewer should say it is missing.

## No Correctness Guarantee

AI judgment does not guarantee correctness.

It can support an evidence-backed decision, identify likely issues, explain uncertainty, and recommend blockers or fixes. It cannot guarantee that future model behavior, future skill activation, semantic interpretation, external services, package publication, or release safety will always be correct.

## Non-Claims

This policy does not claim that AI reviewers are always right, that deterministic checks can be skipped, that hard gates are optional, that checker, fixture, test, CLI, suite-automation, package-publication, or code-contract artifacts are present, or that publication has been completed.

Those claims require separate current evidence and explicit scope.
