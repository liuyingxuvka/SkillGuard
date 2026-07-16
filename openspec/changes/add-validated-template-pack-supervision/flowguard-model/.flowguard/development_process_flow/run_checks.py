"""Run the DevelopmentProcessFlow template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    routine, broken = run_checks()
    print(routine.format_text())
    print()
    print(broken.format_text(max_findings=6))
    return 0 if routine.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
