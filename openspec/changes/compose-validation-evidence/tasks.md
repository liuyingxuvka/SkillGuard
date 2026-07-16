## 1. Model and ownership

- [x] 1.1 Add a validation-composition FlowGuard child model whose function blocks classify artifacts, freeze inputs, resolve reuse, execute affected children, reattach parent evidence, and hand off between evidence domains as `Input x State -> Set(Output x State)`.
- [x] 1.2 Register validation reuse, runtime-artifact exclusion, report-self-watch, single-flight/read-only consumption, and frozen single-owner execution behavior commitments in the existing SkillGuard model and attach the child through ModelMesh without duplicating the execution-depth or retirement owners.
- [x] 1.3 Add FieldLifecycleMesh rows for inventory, policy, execution identity, reuse request/ticket, source result, target profile, proof kind, evidence-domain, and validation-execution ownership fields.
- [x] 1.4 Update DevelopmentProcessFlow ordering and run the executable validation-composition scenarios, contract/refinement checks, loop/stuck review, and parent/child mesh closure.

## 2. Shared portable-artifact policy

- [x] 2.1 Implement one versioned, context-aware artifact-classification module with typed portable, runtime, and unsafe decisions plus stable reason codes.
- [x] 2.2 Replace independent runtime/transient decisions in source/runtime fingerprints and contract compilation with the shared policy.
- [x] 2.3 Replace independent runtime/transient decisions in installation, installed parity, provenance, privacy, fixture handling, and synchronization with the shared policy or declared projections.
- [x] 2.4 Add positive static-fixture and negative live-runtime cases for `.sg-runtime`, `.sg-fixtures`, `.sgf`, `.runtime_workspaces`, caches, locks, runs, bootstrap outputs, result roots, and control-shaped nested fixture samples.
- [x] 2.5 Add repository ignore protection and perform scoped, root-verified cleanup of existing source and installed `.sg-runtime` residue without removing portable fixture evidence.

## 3. Complete TestMesh source inventories

- [x] 3.1 Define and validate deterministic source-inventory rows, inventory hashes, policy bindings, unsafe-link handling, missing-path handling, and duplicate-path handling.
- [x] 3.2 Replace the Python-only TestMesh directory fingerprint with recursive all-regular-file inventory expansion governed only by the shared artifact policy.
- [x] 3.3 Bind each child result, timeout authority, parent replay, and source-currentness decision to the complete inventory and policy version.
- [x] 3.4 Add mutation tests proving that Python, JSON, YAML, Markdown, schema, fixture, model, prompt, configuration, missing, escaped, and unsafe-link changes invalidate current evidence.

## 4. Proof-bound child reuse

- [x] 4.1 Add schemas and immutable records for a TestMesh child reuse request, reuse decision/ticket, source-result reference, target-profile binding, and reused-child parent projection.
- [x] 4.2 Implement exact reuse resolution for direct passed zero-skip children with matching manifest, profile/suite, command, inventory, policy, environment, verifier/runtime, coverage, result hash, locator, and evidence domain.
- [x] 4.3 Extend TestMesh execution and CLI inputs so accepted child reuse emits `reused_current_child`, while rejected or absent reuse executes only the affected child and records the rejection reason.
- [x] 4.4 Extend parent replay to resolve source child bytes and reuse tickets, recompute current identities, reject reuse chains, and preserve target-profile coverage and claim boundaries.
- [x] 4.5 Add positive focused-child-to-full-parent tests and adversarial failed, skipped, timed-out, cancelled, partial, progress-only, truncated, stale, foreign, tampered, changed-input, changed-command, changed-environment, changed-coverage, and chained-reuse tests.
- [x] 4.6 Add single-flight check execution with distinct semantic-check/execution/execution-key identities, terminal-success-only reusable heads, failed-attempt separation, source-change staleness, and runtime-output/source-authority separation; expose the receipt/disposition through supervisor and self-host.

## 5. Ordered and non-overlapping validation

- [x] 5.1 Add cheap runtime-authority, generated-contract, manifest, artifact-boundary, and inventory preflight before any expensive TestMesh child launch.
- [x] 5.2 Add validation ownership diagnostics that reject duplicate normalized command-and-obligation owners while allowing genuinely distinct evidence domains.
- [x] 5.3 Deduplicate the `retire-v1-runtime-compatibility` verification contract so every pytest file/obligation has one execution owner and downstream checks consume current proof instead of rerunning the same suite.
- [x] 5.4 Preserve explicit not-run children, skip lists, stopped-graph reasons, and fail-closed parent status after any early blocker.
- [x] 5.5 Add a read-only receipt consumer that explicitly requires `expected_profile_id=full` and `expected_parent_schema=skillguard.test_mesh_result.v2`, replays the parent-bound current installation identity, rejects fast/focused/V1/incomplete/partial/stale/foreign/tampered/missing-identity proof, and is structurally unable to invoke TestMesh execution, resume, repair, or backfill.
- [x] 5.6 Add one canonical validation-execution ownership policy to source templates, project/global managed prompt projection, documentation, FieldLifecycleMesh, BehaviorCommitmentLedger, executable scenarios, and TestMesh ownership: resume is execution, full requires frozen source/toolchain plus one owner, interrupted launchers require confirmed zero descendants, and Scheduled Task/background/unattended mutable-worktree retry is forbidden.
- [x] 5.7 Require the full V2 TestMesh parent and closure receipt to bind exactly one current installation identity plus one separately typed current global-router prompt binding; neither domain may be inferred from a child suite result or substituted for the other.

## 6. OpenSpec verification-output collision protection

- [x] 6.1 Implement SkillGuard-maintained verification-contract review that resolves report paths, declared receipt/result roots, and freshness files/globs and rejects report self-watch plus evidence-output/source collisions before execution.
- [x] 6.2 Add fixtures and tests for direct file, broad glob, normalized alias, link-equivalent report, declared custom evidence root, receipt/progress/runtime-control path, ambiguous `.skillguard` glob, safe source path, malformed path, and repository escape.
- [x] 6.3 Audit active SkillGuard OpenSpec verification contracts for report/evidence-output collisions and overlapping ownership, fixing only current in-scope contracts while preserving archived evidence.

## 7. Schemas, prompts, and documentation

- [x] 7.1 Register all new schemas and fields in SkillGuard V2 compilation, runtime fingerprint, self-host, closure, and generated-contract authorities.
- [x] 7.2 Update SkillGuard SKILL, execution-record, self-host, installation, and project-adoption references to explain exact evidence reuse, complete inventories, evidence-domain separation, and runtime-artifact boundaries.
- [x] 7.3 Update README, changelog, version metadata, and managed prompt templates without claiming that receipt reuse proves target-domain correctness or future AI behavior.

## 8. Focused verification and repair

- [x] 8.1 After the source/contract/model/task fixpoint, stop writes and run validation-composition FlowGuard checks plus one fixed-input affected unit/fixture regression for policy, inventory, reuse, replay, single-flight execution, read-only parent consumption, collision lint, installation, parity, provenance, and privacy; mutable-worktree runs are not evidence.
- [x] 8.2 Run deterministic compilation, manifest checks, static audits, JSON/schema validation, and self-host checks; inspect every counterexample or failure and repair the owning layer.
- [x] 8.3 Recheck the working tree for peer writes, rerun only affected focused checks, and confirm no unrelated user or peer changes were reverted.

## 9. Component impact model and contract

- [x] 9.1 Extend the existing validation-composition FlowGuard child to compile content components, derive the frozen affected plan, resolve exact owner receipts, execute only stale owners, aggregate without reverse invalidation, and derive full-admission reasons.
- [x] 9.2 Add BehaviorCommitmentLedger, FieldLifecycleMesh, TestMesh, ModelMesh, and DevelopmentProcessFlow rows for component roles, installation dispositions, owner selectors/dependencies, owner projections, plan hash, persistent receipt refs, aggregation identity, and old-path disposition.
- [x] 9.3 Update this proposal/design/spec/tasks/verification contract so component-scoped owner checks remain the only executable owners and final OpenSpec verification is a receipt-only consumer.
- [x] 9.4 Run the executable validation-composition scenario, contract/refinement, loop/stuck, progress, field, hierarchy, TestMesh, and process checks; repair every generalized bad case before runtime implementation.

## 10. Component-scoped implementation

- [x] 10.1 Add the shared content-impact compiler and schema health gate to the existing contract compiler; embed the generated plan in compiled-contract and check-manifest without adding a fourth authority file.
- [x] 10.2 Refactor check execution identity so run/step/parent-wide hashes are attempt metadata, exact owner inputs/dependencies define the semantic key, and terminal success is stored with complete sidecars in the persistent content-addressed evidence root for cross-run reuse.
- [x] 10.3 Add TestMesh plan-only preview and frozen-plan enforcement; replace broad suite source/manifest invalidation with compiled owner projections and make parent-only changes aggregate without child execution.
- [x] 10.4 Project the same graph into staged installation, installed parity, Portfolio impact, global-router refresh, and managed-prompt installation; remove caller-authored broad invalidation and installation-implies-full behavior.
- [x] 10.5 Make validation_execution_policy the only prompt-policy source and update SkillGuard/global-router/project-adoption projections so ordinary skill use does not run SkillGuard while maintenance/installation loads and obeys the frozen impact plan.
- [x] 10.6 Migrate every current SkillGuard check and non-check consumer to exact selectors/dependencies/domains; remove the V1 suite from daily TestMesh and retain old shapes only as fail-closed negative fixtures.

## 11. Affected regression and real receipt pilot

- [x] 11.1 Run only the affected compiler, check-runner, TestMesh planner, installation/parity, Portfolio, router, and prompt regressions, including unmapped/ambiguous/cycle, parent-only aggregation, cross-run reuse, sidecar tamper, test-only no-install, and full-admission bad cases.
- [x] 11.2 Run one real FlowGuard owner receipt through SkillGuard aggregation and OpenSpec `kind: receipt` consumption; prove the consumer launches zero owner processes and consumer coverage drift does not rerun the owner.
- [x] 11.3 Re-run deterministic compile/check, strict schemas, project audit, privacy/provenance boundaries, and the updated FlowGuard model; record exact source/policy/contract/manifest fingerprints and stop writes at source fixpoint.

## 12. Full closure and installation

- [x] 12.1 Transactionally install the upgraded SkillGuard first, prove canonical/stage/active component and authority parity, run only affected active smoke owners, confirm automatic rollback remains covered, and retain the exact current installation receipt root.
- [x] 12.2 Freeze source/toolchain/impact-plan identities and let exactly one owner run one fresh full TestMesh parent; prove every selected child is directly passed or exactly reused, replay the final parent, and write its installation-bound immutable closure receipt plus hash-bound HEAD.
- [x] 12.3 Execute the OpenSpec verification contract as receipt-only consumption with explicit current profile/schema/identity, confirm it launches no TestMesh child and does not resume/repair/backfill, confirm the report does not watch itself, and verify the resulting report remains current after it is written.
- [x] 12.4 Refresh and verify the global SkillGuard router/prompt projections and record the current source, installed, impact-plan, and routing identities for the Guard-family handoff.

## 13. Portfolio model-miss repair: reviewed fixture subtrees

- [x] 13.1 Record the Storyline installation-projection miss and extend the validation-composition model with positive complete-subtree and negative missed-descendant cases.
- [x] 13.2 Let one reviewed content-role override select a maintained directory subtree, inherit to future inventoried descendants, and block overlapping selectors without precedence or fallback.
- [x] 13.3 Run the focused compiler/model/schema regressions, install the affected current SkillGuard projection transactionally, and recompile Storyline Design with its example fixture subtree source-only.
- [x] 13.4 Defer the single full SkillGuard/TestMesh parent to the portfolio final gate after every governed source and target freezes; do not issue a second equivalent full owner here.

## 14. Portfolio model-miss repair: empty non-production schedule sentinel

- [x] 14.1 Record the Storyline supervisor miss and align the supervisor with the execution-depth domain rule: only `scheduled_production` owns installation identity loading.
- [x] 14.2 Accept only absent or empty schedule identity for non-production domains and keep non-empty non-production identities fail-closed.
- [x] 14.3 Run the focused supervisor regression, install the affected current SkillGuard projection transactionally, and rerun the Storyline formal supervisor contract.
- [x] 14.4 Defer the single full SkillGuard/TestMesh parent to the portfolio final gate after every governed source and target freezes.

## 15. Portfolio model-miss repair: nested skill-root installation projection

- [x] 15.1 Record the Storyline installation replay failure and add executable positive and negative model cases for exact current skill-root prefixes.
- [x] 15.2 Compile and hash one exact repository-relative `member_root_path`, strip only that declared root during installation replay, and block every projected path outside it without layout inference or fallback.
- [x] 15.3 Run the focused compiler/model/OpenSpec regressions, recompile and transactionally install the affected SkillGuard projection, then replay the exact Storyline installation identity.
- [x] 15.4 Rerun the affected Storyline formal supervisor contract under the changed Guard runtime and defer the sole full parent to the frozen portfolio final gate.

## 16. Portfolio capability gap: projection-exact single-skill installation

- [x] 16.1 Model and specify a single-skill transaction that is projection-exact, bound to `member_root_path`, and isolated from the SkillGuard self-install HEAD, receipts, backup, and recovery chain.
- [x] 16.2 Implement prepare, verify, activate, automatic rollback, explicit rollback, and crash recovery under one per-target namespace and the shared global installation lock; do not execute arbitrary target commands.
- [x] 16.3 Add first-install, replacement, source-only exclusion, stage drift, active parity failure, rollback, recovery, invalid id/root/path, reparse, path-budget, lock, and self-HEAD-isolation regressions.
- [x] 16.4 Recompile and transactionally install SkillGuard, then install Storyline through the new route and replay its installed parity/native owners without a second full parent.

## 17. Model-miss repair: task progress cannot refresh source authority

- [x] 17.1 Record the observed checkbox-only contract-currentness miss against the existing validation-composition commitment and FlowGuard counterexample.
- [x] 17.2 Normalize only real Markdown task-marker state in `tasks.md` through the shared source/content-impact fingerprint while preserving task text, order, indentation, fenced examples, and every non-task source byte.
- [x] 17.3 Make TestMesh/OpenSpec source projection reuse the same normalization function and pass focused compiler, projection, semantic-change, fenced-example, and FlowGuard regressions without adding a mode or target-domain rule.
- [x] 17.4 Recompile and transactionally install SkillGuard, replay real TraceGuard checkbox-only currentness, and leave the sole full parent to the frozen portfolio final gate.

## 18. Model-miss repair: installed audit cannot recompile source-only inputs

- [x] 18.1 Record the observed installed-audit miss and add an executable counterexample that blocks treating an installed projection as a complete source repository.
- [x] 18.2 Make installed audit consume only the current installed `contract-source.json`, `compiled-contract.json`, and exact `check-manifest.json` authority after runtime-authority validation; do not add a fallback, compatibility reader, or target-domain inference.
- [x] 18.3 Run the focused installed-audit regression, validation-composition model, strict OpenSpec validation, and a real twenty-target installed audit.
- [x] 18.4 Recompile and transactionally install the affected SkillGuard projection, then leave the sole full parent to the frozen portfolio final gate.
