"""StructureMesh for the SkillGuard evidence runtime split.

The public dispatcher remains the only CLI facade.  Evidence storage,
producer integration, lifecycle command adaptation, and installation hygiene
have one code owner each; the model blocks duplicate evidence state or a
second public command implementation.
"""

from __future__ import annotations

from flowguard import (
    CodeStructureRecommendation,
    EVIDENCE_CONFORMANCE_GREEN,
    ModuleStructureEvidence,
    PublicEntrypointEvidence,
    StructureMeshPlan,
    StructurePartitionItem,
    TargetModuleRecommendation,
)


PARENT_MODULE_ID = "skillguard-evidence-runtime"
PUBLIC_COMMANDS = (
    "skillguard.py evidence-audit",
    "skillguard.py evidence-gc-plan",
    "skillguard.py evidence-gc-apply",
    "skillguard.py evidence-gc-purge",
)


FUNCTION_OWNER_MAP = (
    ("persist-compressed-stream", "evidence-store"),
    ("verify-compressed-stream", "evidence-store"),
    ("publish-current-head-authority", "evidence-store"),
    ("coordinate-active-writers", "evidence-store"),
    ("audit-evidence-reachability", "evidence-store"),
    ("plan-evidence-collection", "evidence-store"),
    ("quarantine-evidence", "evidence-store"),
    ("purge-evidence-quarantine", "evidence-store"),
    ("persist-producer-sidecars", "check-runner"),
    ("replay-producer-sidecars", "check-runner"),
    ("adapt-lifecycle-commands", "evidence-store-cli"),
    ("dispatch-public-command", "checker-engine-facade"),
    ("project-installed-runtime", "installation"),
    ("reject-installed-bytecode", "installation"),
)


def target_structure() -> CodeStructureRecommendation:
    module_paths = {
        "evidence-store": ".agents/skills/skillguard/scripts/skillguard_v2/evidence_store.py",
        "check-runner": ".agents/skills/skillguard/scripts/skillguard_v2/check_runner.py",
        "evidence-store-cli": ".agents/skills/skillguard/scripts/skillguard_v2/evidence_store_cli.py",
        "checker-engine-facade": ".agents/skills/skillguard/scripts/checker_engine.py",
        "installation": ".agents/skills/skillguard/scripts/skillguard_v2/installation.py",
    }
    target_modules = tuple(
        TargetModuleRecommendation(
            module_id,
            path=module_paths[module_id],
            owns_function_blocks=tuple(
                block for block, owner in FUNCTION_OWNER_MAP if owner == module_id
            ),
            owns_state=(
                ("current-head-authorities", "active-writer-markers")
                if module_id == "evidence-store"
                else ()
            ),
            owns_side_effects=(
                ("publish-evidence", "quarantine-evidence", "purge-quarantine")
                if module_id == "evidence-store"
                else ()
            ),
            owns_config=(
                ("evidence-lifecycle-policy", "logical-byte-budget")
                if module_id == "evidence-store"
                else ()
            ),
            public_entrypoints=(
                PUBLIC_COMMANDS if module_id == "checker-engine-facade" else ()
            ),
            validation_boundaries=("focused structure and lifecycle regressions",),
            rationale=f"{module_id} has one bounded evidence-runtime responsibility.",
        )
        for module_id in module_paths
    )
    return CodeStructureRecommendation(
        "skillguard-evidence-runtime-current-structure",
        source_model_id="skillguard-validation-composition-current",
        source_model_path=".flowguard/validation_composition/validation_composition_model.py",
        parent_module_id=PARENT_MODULE_ID,
        target_modules=target_modules,
        function_block_map=FUNCTION_OWNER_MAP,
        state_owner_map=(
            ("current-head-authorities", "evidence-store"),
            ("active-writer-markers", "evidence-store"),
        ),
        side_effect_owner_map=(
            ("publish-evidence", "evidence-store"),
            ("quarantine-evidence", "evidence-store"),
            ("purge-quarantine", "evidence-store"),
        ),
        config_owner_map=(
            ("evidence-lifecycle-policy", "evidence-store"),
            ("logical-byte-budget", "evidence-store"),
        ),
        public_entrypoint_map=tuple(
            (command, "checker-engine-facade") for command in PUBLIC_COMMANDS
        ),
        facade_module_id="checker-engine-facade",
        validation_boundaries=(
            "compressed evidence regression",
            "current-head and active-writer lifecycle regression",
            "public command dispatch regression",
            "installation projection regression",
        ),
        rationale=(
            "The functional model separates immutable evidence mechanics, owner-runner "
            "integration, CLI adaptation, the sole public facade, and installation hygiene."
        ),
    )


def build_structure_mesh() -> StructureMeshPlan:
    recommendation = target_structure()
    dependencies = {
        "evidence-store": (),
        "check-runner": ("evidence-store",),
        "evidence-store-cli": ("evidence-store",),
        "checker-engine-facade": ("evidence-store-cli",),
        "installation": (),
    }
    modules = tuple(
        ModuleStructureEvidence(
            module.module_id,
            path=module.path,
            owns_functions=module.owns_function_blocks,
            owns_state=module.owns_state,
            owns_side_effects=module.owns_side_effects,
            owns_config=module.owns_config,
            dependencies=dependencies[module.module_id],
            facade_retained=True,
            behavior_parity_current=True,
            behavior_parity_tier=EVIDENCE_CONFORMANCE_GREEN,
        )
        for module in recommendation.target_modules
    )
    partitions = tuple(
        StructurePartitionItem(block, owner_module_id=owner)
        for block, owner in FUNCTION_OWNER_MAP
    ) + tuple(
        StructurePartitionItem(
            command,
            item_type="entrypoint",
            owner_module_id="checker-engine-facade",
            public_surface=True,
            old_path="",
            new_path=".agents/skills/skillguard/scripts/skillguard.py",
        )
        for command in PUBLIC_COMMANDS
    )
    entrypoints = tuple(
        PublicEntrypointEvidence(
            command,
            entrypoint_type="cli",
            old_path="",
            new_path=".agents/skills/skillguard/scripts/skillguard.py",
            compatibility_preserved=True,
            facade_available=True,
            parity_evidence_current=True,
            parity_evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
            evidence_path="tests/test_evidence_store_cli.py",
        )
        for command in PUBLIC_COMMANDS
    )
    return StructureMeshPlan(
        parent_module_id=PARENT_MODULE_ID,
        target_structure=recommendation,
        decision_scope="release",
        required_evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
        partition_items=partitions,
        child_modules=modules,
        public_entrypoints=entrypoints,
    )


def build_bad_structure_mesh() -> StructureMeshPlan:
    current = build_structure_mesh()
    evidence_store = current.child_modules[0]
    duplicate = ModuleStructureEvidence(
        "second-evidence-store",
        path=".agents/skills/skillguard/scripts/skillguard_v2/alternate_store.py",
        owns_state=("current-head-authorities",),
        owns_side_effects=("purge-quarantine",),
        facade_retained=True,
        behavior_parity_current=False,
        behavior_parity_tier=EVIDENCE_CONFORMANCE_GREEN,
    )
    return StructureMeshPlan(
        parent_module_id=PARENT_MODULE_ID,
        target_structure=current.target_structure,
        decision_scope="release",
        required_evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
        partition_items=current.partition_items,
        child_modules=(evidence_store, *current.child_modules[1:], duplicate),
        public_entrypoints=current.public_entrypoints,
    )

