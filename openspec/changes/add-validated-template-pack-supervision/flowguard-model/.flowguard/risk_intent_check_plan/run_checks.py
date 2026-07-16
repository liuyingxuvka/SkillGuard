"""Run the validated Template Pack Risk Intent + CheckPlan model."""

from flowguard import maintenance_scan_plan_from_summary_report, review_maintenance_scan
from model import risk_profile, run_checks


def main() -> int:
    print(f"risk_intent: {risk_profile().modeled_boundary}")
    current, broken = run_checks()
    print(current.format_text())
    print()
    print("known_bad_variant:")
    print(broken.format_text())
    print()
    scan = review_maintenance_scan(
        maintenance_scan_plan_from_summary_report(
            current,
            plan_id="template-pack-selection-summary-bridge",
            claim_scope="planning_ready",
        )
    )
    print(scan.format_text())
    return 0 if current.overall_status in {"pass", "pass_with_gaps"} and broken.overall_status == "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
