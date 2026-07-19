# SkillGuard current execution and receipt records

This reference defines the one current execution-record boundary shared by manifest-bound owner checks and TestMesh aggregation. These records improve observability and recovery; they do not turn activity, output, or a timeout into passing evidence.

## Progress and heartbeat authority

- `start`, `progress`, `heartbeat`, and `end` are observation events. Final check or suite result artifacts remain the completion authority.
- A `progress` event is emitted only when the combined observed stdout/stderr byte count increases. It carries the positive `progress_delta_bytes`; repeated output-free polling must not be presented as progress.
- A `heartbeat` records liveness at the polling interval. It carries `progress_delta_bytes: 0` and `no_progress_ms`; it does not prove useful work, a passing check, or eventual completion.
- Every event has a monotonic `sequence`, `previous_event_hash`, and `event_hash`. Loading the log revalidates each event, sequence continuity, and the full hash chain.
- Event logs are append-only JSONL with flush/fsync. Their locators use a path token plus a relative path rather than persisting a machine-specific absolute location.

## Time and output accounting

- Event timestamps use UTC millisecond precision. Execution results and timeout receipts carry integer `elapsed_ms`, `timeout_ms`, or `duration_ms` where applicable.
- `stdout_total_bytes` and `stderr_total_bytes` record the complete observed stream lengths. `stdout_captured_bytes` and `stderr_captured_bytes` record how many bytes were retained in the bounded diagnostic capture.
- Full-stream hashes remain separate from bounded captured text. A truncated diagnostic therefore cannot silently claim to be the whole output.
- Persisted stdout/stderr diagnostics replace known local roots with path tokens and the user home with `{{user_home}}`. These diagnostics are private runtime records and are not public release artifacts.

## Timeout terminal handling

- Checks launch in an isolated Windows process group or POSIX session. A timeout triggers process-tree termination: Windows uses `taskkill /T /F` with a parent-kill fallback; POSIX terminates the process group and escalates when required.
- Termination facts record the scope, whether termination was attempted, whether it succeeded, the method, and any error kind. A failed or incomplete termination attempt remains visible and never changes `timed_out` into success.
- A timed-out owner attempt records `status: timed_out`, `terminal_kind: timeout`, command identity, full output hashes, total/captured byte counts, timing, and process-tree cleanup facts. It never creates or updates the terminal-success head. TestMesh does not launch processes and therefore cannot turn a timeout into a retry.

## Frozen affected plan and aggregation

- TestMesh `plan_only` reads the compiled component graph and persistent owner-receipt pool. It records exact changed components, reusable owners, owners that still require execution, installation/router/Portfolio projections, and any derived full-admission reason. It launches and writes nothing.
- The declared owner runner—not TestMesh—executes only `will_execute_owner_ids`. Each successful owner publishes one immutable receipt with complete stdout, stderr, result, and termination sidecars.
- TestMesh `aggregation_only` accepts the byte-exact frozen plan and references the matching owner receipts. A parent/profile-only change may create a new aggregation identity without changing or reissuing child receipts.
- Read-only replay resolves the aggregation reference and every child receipt. Missing or tampered evidence blocks; replay never executes, resumes, repairs, or backfills an owner.

## Self-host CLI exception terminal

- The thin self-host CLI catches ordinary `Exception` failures from the bootstrap and emits one path-safe JSON terminal containing exactly `schema_version`, `artifact_type`, `status`, `error_code`, `reason`, and `claim_boundary`. It does not expose the exception string or a local absolute path, prints no traceback, and returns a nonzero exit status.
- Declared `SelfHostError` failures retain a safe declared error code or fall back to `self_host_declared_error`; `OSError` becomes the blocked `self_host_os_error`; all other ordinary exceptions become `self_host_unexpected_exception`.
- `KeyboardInterrupt` and `SystemExit` derive from `BaseException`, are deliberately not caught by this boundary, and preserve normal operator/process-control behavior.
- This exception terminal proves only that the bootstrap did not return a normal self-host result. It does not prove self-host closure, installation, release readiness, or publication.

## Durable immutable owner binding

- The receipt binds one exact owner declaration, input-component projection, semantically consumed dependency receipts, explicitly universal target inputs, only that owner's declared target-input role fingerprints, command/toolchain, environment/verifier, and evidence domain. Run id, run-root path, step, timestamp, parent profile, progress state, and display text are attempt or aggregation metadata, not semantic freshness inputs.
- Receipt ids and hashes are derived from canonical content. File creation is durable and no-replace; an existing different payload is a collision, while the exact same immutable payload is idempotent.
- Loading revalidates the schema, artifact type, policy, owner fields and hash, command token, terminal fields, receipt id/hash, safe relative locator, and filename. Supplying a different expected owner rejects cross-owner replay.
- A timeout receipt proves only the exact failed execution boundary. Closure still requires the declared successful check or suite evidence after diagnosis and an authorized retry or resume.

## Single-flight check execution

- Treat `semantic_check_id` as the stable declared check meaning, `execution_key` as the exact owner declaration/input/dependency/toolchain/environment identity, and `execution_id` as one concrete attempt. Never substitute one for another.
- Serialize each owner identity across runs. Reuse only a complete immutable `terminal_success` receipt whose key, sidecars, source components, target inputs, dependencies, and toolchain all replay exactly.
- Persist a failed attempt as diagnostic execution history but never publish it to the canonical success slot. A retry receives a new execution id; a source or target-input change blocks as stale instead of reusing or silently replacing prior authority.
- Exclude `.sg-runtime`, run results, diagnostics, progress, receipts, locks, and test output from source authority. Those outputs may change without changing the execution key, while declared implementation, model, contract, check, or target-input changes must stale it.

## Read-only same-unit aggregation

- The canonical ownership policy is `skillguard.validation_execution_ownership.current` and is rendered only from `validation_execution_policy.py`.
- Before validation, freeze one maintenance unit's exact checks in the existing verification contract or TestMesh, including member, evidence subject, semantic check, covered obligation/evidence domain, dependency order, persistent private receipt root, and one execution owner per check. Missing, duplicate, foreign-unit, or cyclic ownership blocks before execution.
- An author-side same-unit aggregator resolves the exact current owner receipt from the frozen execution identity and inputs. A consumer distribution carries neither that receipt nor the owner's command.
- Maintained inputs invalidate only affected receipts. `depends_on_check_ids` is reserved for checks that actually consume the upstream immutable receipt; order-only relationships do not enter receipt identity. Reports, receipts, task checkboxes, progress logs, and other runtime outputs stay outside source authority and cannot trigger the check that produced them.
- Create one frozen TestMesh aggregation after this maintenance unit's planned owner receipts exist. Only author-side checks in the same unit may replay that aggregation; another unit must own its own checks and evidence.
- Full aggregation in an external maintained author repository binds the single current canonical SkillGuard source with `--canonical-skillguard-root`. Aggregation and replay re-check that same author source against the active SkillGuard installation receipt; a missing or different source blocks, and no fallback source is discovered.
- The replay path never invokes execution, resume, repair, uncovered-owner completion, or receipt backfill. A missing, partial, stale, foreign, tampered, or identity-incomplete aggregation/child authority returns failed.
- A final full aggregation may bind the unit's clean consumer installation projection when installation is in scope. The private global prompt is author routing state, not a child proof or consumer requirement.
- Do not expose an execution-capable `--resume` path as a receipt auditor. A runner allowed to fill missing checks is an executor and must remain inside the owning maintenance unit.
- Official OpenSpec may be read as requirements context, but it is never a receipt consumer, execution owner, cache/session bridge, or SkillGuard maintenance target.
- Start full validation only after the source and toolchain identities are frozen, under one explicit execution owner.
- After a launcher timeout, cancellation, or interruption, confirm that the entire descendant process tree count is zero before accepting evidence or starting another owner. A `cleanup-unconfirmed` result is invalid and non-reusable.
- Do not use a Windows Scheduled Task, background resume, or unattended retry script to run full validation or resume a mutable worktree.

## Privacy and display boundary

Persistent execution records use path tokens, relative locators, command tokens, hashes, and redacted diagnostic text. They stay in the author-maintenance evidence root and never enter a consumer skill or ordinary project. Runtime path displays may help a maintainer distinguish the canonical source, private working root, and installed copy, but they default to home-redacted display and remain stderr-only private diagnostics. Neither form proves that an install, release, GitHub operation, or remote CI run occurred.
