# SkillGuard current execution records

Execution records describe what one declared owner actually did. They improve
observability and recovery; activity, output, timeout, or a progress event is
never a passing result by itself.

Every event is append-only and hash chained. It records a monotonic sequence,
the previous event hash, event hash, UTC timestamp, owner identity, request
identity, input/dependency identities, toolchain, environment, and bounded
output counts. A progress event means observed output grew; a heartbeat means
only that polling occurred. Neither proves useful work or success.

The terminal result records the real process state: started, completed, failed,
cancelled, timed out, and whether cleanup was confirmed. A timeout or
cancellation never publishes the current-success head. On Windows and POSIX,
the declared process-group cleanup must leave zero descendants; an unknown or
incomplete cleanup is `cleanup-unconfirmed` and cannot be reused.

The producer receipt binds one exact owner, input-component projection,
declared dependencies, command, toolchain, environment, and verifier. A
semantic check projection separately records its evidence subject, check,
covered obligations, and evidence domain. Command similarity never authorizes
cross-owner reuse. Only a complete immutable `terminal_success` receipt with
the same maintenance unit and all identities may be reused.

Read-only replay resolves immutable records and verifies their hashes. It never
executes, resumes, repairs, fills missing owners, or writes a current pointer.
An absent, partial, stale, foreign, tampered, or identity-incomplete record is
a typed failure. Reports, progress logs, receipts, and checkboxes are output
evidence; they cannot make their own source current or trigger their producer.

Records stay in the private author evidence root. They use relative locators,
path tokens, hashes, and bounded redacted diagnostics; they do not enter a
consumer skill or ordinary project. OpenSpec may be read for requirement
context, but it is never a receipt consumer, execution owner, or evidence
bridge.

The current operation boundary remains `read`, `change`, and `release`.
There is no old stream reader, migration, alias, evidence-GC command,
compatibility path, or fallback success path. A former record format reachable
from current authority blocks; it is not interpreted through another parser.
