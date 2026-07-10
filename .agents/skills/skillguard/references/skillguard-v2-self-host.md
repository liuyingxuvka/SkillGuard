# SkillGuard V2 self-host bootstrap

SkillGuard V2 uses a two-stage bootstrap so the verifier does not silently certify itself.

1. The frozen V1 checker fingerprint runs the current static skill check, deep-contract check, self-check, and—at the release boundary—the complete legacy regression suite. Any red result blocks the bootstrap and remains visible.
2. The V2 compiler checks or regenerates only `.skillguard/compiled-contract.json` and `.skillguard/check-manifest.json` from the FlowGuard model plus confirmed binding source.
3. The V2 runtime selects the declared maintenance composition, claims a target-local run, locks write targets, and executes only checks bound to ready steps.
4. Every native check result is stored immutably before it can become hard evidence. The receipt verifier confirms run, contract, step, check, execution status, proof fingerprint, and record hash.
5. Functional closure runs before release closure. Both consume exact current receipts and are replay-verified. A V1 result cannot become an alternate success after a V2 failure.

Run the focused bootstrap while developing:

```powershell
python .agents/skills/skillguard/scripts/skillguard_v2_self_host.py --repository-root . --skip-old-full
```

Run the full bootstrap before release:

```powershell
python .agents/skills/skillguard/scripts/skillguard_v2_self_host.py --repository-root .
```

Task runs, check records, receipts, reports, and closure receipts stay under the target project's ignored `.skillguard/` runtime directory. They are evidence for the exact local source and environment only; they are not published contract files.
