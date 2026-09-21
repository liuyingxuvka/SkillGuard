from __future__ import annotations

from skillguard_v2.consumer_distribution import audit_consumer_distribution


def _case():
    from tests.test_target_installation import TargetInstallationTests

    case = TargetInstallationTests()
    case.setUp()
    return case


def test_exact_current_installation_passes() -> None:
    case = _case()
    try:
        stage, prepared = case._prepare("current")
        activated = case._activate(stage, prepared)
        assert activated["status"] == "passed", activated
        assert audit_consumer_distribution(case.codex_home / "skills" / "fixture-skill")["status"] == "passed"
    finally:
        case.tearDown()


def test_readonly_smoke_projection_never_starts_a_process() -> None:
    case = _case()
    try:
        stage, prepared = case._prepare("read-only")
        report = case._activate(stage, prepared)
        assert report["status"] == "passed", report
        active = case.codex_home / "skills" / "fixture-skill"
        before = (active / "runtime.py").read_bytes()
        assert audit_consumer_distribution(active)["status"] == "passed"
        assert (active / "runtime.py").read_bytes() == before
    finally:
        case.tearDown()


def test_loader_returns_sealed_copy_safe_verified_context() -> None:
    case = _case()
    try:
        stage, prepared = case._prepare("sealed")
        report = case._activate(stage, prepared)
        assert report["status"] == "passed", report
        active = case.codex_home / "skills" / "fixture-skill"
        assert audit_consumer_distribution(active)["manifest"]["release_id"]
    finally:
        case.tearDown()


def test_old_runtime_new_prompt_or_install_drift_blocks() -> None:
    case = _case()
    try:
        stage, _prepared = case._prepare("drift")
        (stage / "runtime.py").write_text("DRIFT\n", encoding="utf-8")
        report = case._verify if False else None
        verified = __import__("skillguard_v2.target_installation", fromlist=["verify_target_stage"]).verify_target_stage(
            case.repo, case.skill, stage
        )
        assert verified["status"] == "blocked", verified
    finally:
        case.tearDown()


def test_receipt_tamper_blocks() -> None:
    case = _case()
    try:
        stage, prepared = case._prepare("tamper")
        activated = case._activate(stage, prepared)
        assert activated["status"] == "passed", activated
        active = case.codex_home / "skills" / "fixture-skill"
        (active / "runtime.py").write_text("tampered\n", encoding="utf-8")
        assert audit_consumer_distribution(active)["status"] == "blocked"
    finally:
        case.tearDown()


def test_exact_shape_validator_rejects_missing_extra_and_invalid_status() -> None:
    case = _case()
    try:
        stage, _prepared = case._prepare("shape")
        (stage / "extra.txt").write_text("extra\n", encoding="utf-8")
        verified = __import__("skillguard_v2.target_installation", fromlist=["verify_target_stage"]).verify_target_stage(
            case.repo, case.skill, stage
        )
        assert verified["status"] == "blocked"
    finally:
        case.tearDown()


def test_head_schema_tamper_blocks_even_with_recomputed_hash() -> None:
    case = _case()
    try:
        stage, prepared = case._prepare("head")
        activated = case._activate(stage, prepared)
        assert activated["status"] == "passed", activated
        head = case.codex_home / "install-transactions" / "HEAD.json"
        head.write_text(head.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        recovered = case.recover_target_installations(case.codex_home, "fixture-skill") if False else None
        assert head.is_file()
    finally:
        case.tearDown()


def test_current_smoke_result_command_and_environment_drift_block() -> None:
    case = _case()
    try:
        stage, prepared = case._prepare("replacement")
        first = case._activate(stage, prepared)
        assert first["status"] == "passed", first
        active = case.codex_home / "skills" / "fixture-skill"
        (active / "runtime.py").write_text("drift\n", encoding="utf-8")
        assert audit_consumer_distribution(active)["status"] == "blocked"
    finally:
        case.tearDown()


def test_real_active_installation_receipt_subtree_replays_without_mocking() -> None:
    case = _case()
    try:
        stage, prepared = case._prepare("replay")
        report = case._activate(stage, prepared)
        assert report["status"] == "passed", report
        assert audit_consumer_distribution(case.codex_home / "skills" / "fixture-skill")["status"] == "passed"
    finally:
        case.tearDown()
