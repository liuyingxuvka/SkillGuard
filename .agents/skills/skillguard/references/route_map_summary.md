# SkillGuard route map summary

This is the small prompt-facing map. The complete current route catalog remains the
generated `skillguard-route-index.json`; do not preload that file for an ordinary task.

Use the read-only query first and load only the returned capsule:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py route-reference --route-id <current-route>
```

`route-reference` returns one current route, its `next_reference`, conditional
references, load order, authority, and claim boundary. It never executes the route,
returns the full catalog, installs a consumer, or refreshes author/router state.

Route families remain discoverable in the generated index and registry: planning and
generation; contract/depth/capability checks; maintainer adoption/audit; evidence and
Portfolio operations; installation/currentness; fixture and stale-evidence checks;
README/release checks; self-check and report commands. Zero, many, stale, forbidden,
or missing-input matches remain blocked; no keyword score or fallback selects a route.

For ordinary work read only `SKILL.md`, this summary, and the one route reference
returned by the query. Read the supervisor, test-mesh, installation, self-host, or
release references only when the selected route explicitly requires them.
