"""Run the plan-detailing template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    detail_reports, intake, process, contracts = run_checks()
    print("=== flowguard plan-detailing template ===")
    for report in detail_reports:
        print(report.format_text(max_findings=4))
        print()
    print(intake.format_text(max_findings=4))
    print()
    print(process.format_text(max_findings=4))
    print(f"contracts: {len(contracts)}")
    # PlanDetail and intake must pass.  The process projection must remain
    # blocked while its deliberately not-run implementation evidence is absent;
    # planning detail is not execution proof.
    expected_process_block = (
        not process.ok
        and any(finding.code == "validation_evidence_not_current" for finding in process.findings)
    )
    good_ok = detail_reports[0].ok and intake.ok and expected_process_block and contracts
    broken_blocked = all(not report.ok for report in detail_reports[1:])
    return 0 if good_ok and broken_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
