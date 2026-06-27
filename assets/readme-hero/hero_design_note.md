# SkillGuard README Hero Design Note

## Project summary

SkillGuard is a local runtime-contract and maintenance framework for Codex skills. It helps a skill preserve its original route, bind missing contract gates around that route, record current run evidence, and block shallow or skipped closure claims.

## Target users

- Codex skill authors.
- Maintainers of skill suites.
- Developers who need evidence-backed AI workflow maintenance.
- Users who want SkillGuard to strengthen existing skill paths without replacing them.

## Core problem

AI-maintained skills can drift into shallow entrypoint updates: a skill may list a route, but not prove source requirements, acceptance obligations, checks, run evidence, or closure blockers. A native skill may already have its own route, so adding a second SkillGuard route can reduce clarity instead of improving it.

## Core workflow

1. Inspect the target skill and detect whether a native route/check system already exists.
2. Use `native-integrated` or `hybrid-extension` when a native path exists; use `skillguard-runtime` only when SkillGuard owns the route.
3. Compile a work contract with source requirements, acceptance obligations, skill-specific checks, closure blockers, and non-parallel route proof.
4. Create a run record bound to the current contract hash.
5. Check evidence and block closure when work is shallow, stale, skipped, or outside the claim boundary.

## Hero tagline

A local runtime-contract system for keeping Codex skills on the right path.

## Visual concept

The hero shows several original skill routes entering a transparent contract executor. Each lane remains visible as it passes through checkpoints for source requirements, acceptance obligations, run records, checks, and closure blockers. The approved outputs keep their separate lanes, making the native-first rule visually clear: SkillGuard governs routes; it does not replace them.

## Image keywords

Skill routes, contract executor, native bindings, source requirements, acceptance obligations, run records, verification gates, closure blockers, evidence feedback loop, bright technical product render.

## File paths

- `assets/readme-hero/hero.png`
- `assets/readme-hero/hero_prompt.md`
- `assets/readme-hero/hero_design_note.md`
- `assets/readme-hero/readme_model_evidence.md`

## README insertion position

The hero block is placed immediately after the H1 title in `README.md`.
