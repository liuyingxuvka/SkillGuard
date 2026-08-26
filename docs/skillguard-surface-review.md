# SkillGuard current implementation-surface review

This document is the human review record for the direct-current reverse
surface inventory. It is provenance for the current inventory; it is not a
second contract authority and it cannot make an inventory pass by itself.

## Review boundary

The source observer is run against `.agents/skills/skillguard` with the current
command and route registries. On 2026-08-21, after the functional-closure and
reverse-component checks were added, it found 1,956 source observations across
the current production tree, including 53 deterministic private-member
component groups. The frozen discovery fingerprint for this authority is
recorded in `.skillguard/surface-inventory.json`; it must be regenerated after
any source or route-registry change. The component groups are review units,
not a claim that every private helper is an independent public capability.
The source line/span is only a location anchor; it is never a contract row or
an independent intent requirement.
The two generated authority files (`.skillguard/compiled-contract.json` and
`.skillguard/check-manifest.json`) are intentionally excluded from this source
denominator: the compiler owns their exact currentness as derived outputs, so
including them would create a self-referential compile/inventory cycle. The
inventory must be regenerated and manually reviewed whenever this fingerprint
changes. No historical inventory row is inherited when its source identity
changes.

The target-owned `.skillguard/functional-closure.json` is a governed evidence
artifact rather than a generated compiler output. It stays in the reverse
denominator and is bound to the current native closure checks; its routine
fixture record does not license a functional, release, installation, or
consumer-independence claim by itself.

## What counts as a row

The scanner emits a row for a current command, route, script, top-level API or
export, configuration/artifact, template, installer, UI-like action, or a
derived effect/fault/recovery/provider observation. It does not emit one row
per source line, branch, local variable, or private helper.

`review_granularity=surface` means the observed thing is independently
addressable and must be reviewed as its own externally meaningful surface.
`review_granularity=component` means several derived observations belong to
one owning implementation component and may be reviewed together. Grouping is
deterministic and visible; it is not an automatic pass and it cannot hide an
unresolved owner, intent, test, or evidence gap. A component group is closed
only after its member observations all bind to the same explicitly declared
current proof boundary.
For this current SkillGuard authority, private members are classified as
`internal_proven` only where the enclosing governed source owner explicitly
covers the component. The current proof is this review record plus the owner
receipt, never a source-name inference.

## Disposition rules

* Commands, routes, scripts, installers, templates, configuration/artifacts
  that are part of `.skillguard` authority, and all effect/provider/UI/fault/
  recovery observations are governed. A grouped component still needs one
  explicit current intent/owner/check/evidence boundary for the group; the
  grouping never turns a missing member into a pass.
* Public-looking Python symbols that are not an entry script, registered
  command/route, exported symbol, installer, effect, provider, UI, fault, or
  recovery surface are `internal_proven` only when they are covered by their
  enclosing governed implementation owner. The disposition is explicit so a
  future source change cannot silently disappear from the denominator.
* Symbols under `.skillguard` model files and `scripts/skillguard_v2` are
  governed even when they are helper-shaped: they participate directly in the
  contract/runtime/model implementation.
* A live source surface is never marked `retired_proven` or
  `not_applicable_proven`. Those dispositions are reserved for an explicitly
  removed or inapplicable observed category and are rejected for a still-live
  discovery row.

## Adequacy envelope

The current contract binds every governed row to these separate native checks:

* `check:self:surface-inventory` — exact source/intent/owner denominator;
* `check:self:target-native-deepening-closure` — model/depth adequacy;
* `check:self:failed-lock-recovery` — failure and recovery behavior; and
* `check:self:assurance-diagnostics` — observable evidence and diagnostics.

These IDs are required evidence projections, not a claim that one smoke test
proves every row. The source-side structural reverse denominator is current,
but the only persisted functional-closure evidence is still routine/fixture
depth. The final execution receipt must prove that each owner ran under the
same frozen current source identity, and a missing or stale owner keeps
depth/graduation blocked.

## Historical specifications and intent

Older specs, model contributions, and inventories are retained only as
provenance. They are reviewed against the current source and either accepted
as a new current intent contribution, superseded, rejected, deferred, or
explicitly unresolved. A changed identity requires direct manual rewrite under
the current schema; no compatibility reader, alias, fallback, or automatic
inheritance is permitted.
