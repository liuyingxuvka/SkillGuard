# Single-skill target installation

Use this route only for a maintained target skill other than the SkillGuard self-install cohort.

1. Compile the current contract. Its content-impact plan must contain one repository-relative `member_root_path` and one exact `projection:installation`.
2. Choose a new isolated stage whose final directory name equals the validated manifest `skill_id`.
3. Prepare and verify without activation:

   `python scripts/skillguard_target_install.py --repository-root <repo> --skill-root <repo/member_root_path> --stage-root <isolated-stage/skill-id> --codex-home <CODEX_HOME> --prepare`

4. Activate only after the returned stage verification is current:

   `python scripts/skillguard_target_install.py --repository-root <repo> --skill-root <repo/member_root_path> --stage-root <isolated-stage/skill-id> --codex-home <CODEX_HOME> --activate`

   The same invocation may use `--prepare --activate` when the stage does not yet exist.

5. Run target-native installed checks separately through their frozen execution owners. Installation itself never executes target repository commands.

6. Recover an interrupted target transaction with:

   `python scripts/skillguard_target_install.py --codex-home <CODEX_HOME> --skill-id <skill-id> --recover`

7. Roll back only the current committed target HEAD with:

   `python scripts/skillguard_target_install.py --codex-home <CODEX_HOME> --skill-id <skill-id> --rollback <target-install-id>`

The target transaction domain is separate from `scripts/skillguard_install.py`. It must not write or reuse the SkillGuard self-install `install-transactions/HEAD.json`, self-install receipts, global-router cohort, or self smoke plan. A target receipt proves exact local activation and rollback boundaries only; it does not prove semantic behavior, release readiness, GitHub publication, or future AI behavior.
