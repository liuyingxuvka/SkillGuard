"""Run the one current SkillGuard executable-contract model."""

from __future__ import annotations

import json

from model import all_reports, reports_ok


def main() -> int:
    reports = all_reports()
    payload = {
        "schema_version": "skillguard.flowguard_model_result.v1",
        "model_id": "skillguard.executable_contract_runtime.v2",
        "status": "pass" if reports_ok(reports.values()) else "fail",
        "reports": {
            name: {
                "ok": bool(getattr(report, "ok", False)),
                "finding_count": len(getattr(report, "findings", ())),
            }
            for name, report in reports.items()
        },
        "claim_boundary": (
            "This runner covers the current SkillGuard executable-contract "
            "model, including its read-only assurance-diagnostics route. It "
            "does not prove repository tests, installation, Git, or release."
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
