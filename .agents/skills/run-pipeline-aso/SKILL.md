---
name: run-pipeline-aso
description: Run the full ASO keyword pipeline end-to-end for a registered app from an Input CSV, in the correct order: resolve app/market, check app config + Google Play profile health, detect and warm any missing agentic cache with real subagents, then run the actual filter pipeline and report the Output workbook. Use when the user asks to run or execute the ASO pipeline for an app, for example "Run pipeline ASO", "Run ASO pipeline for <AppName>", "Run the full pipeline for <AppName> <Market>", or drops a normalized AppTweak CSV into an app's Input folder and asks to process it.
---

# Run Pipeline ASO (end-to-end orchestrator)

This skill is the single entry point that runs the whole ASO pipeline **the right way**. The raw runners (`run_aso_filter.py` and each app's runner) are **cache-only** for AI steps and will fail fast if any keyword is unclassified — so calling them directly on a fresh AppTweak export is not enough. This skill sequences every prerequisite first, then runs the pipeline.

Do not skip steps or run the runner directly when the user invokes this skill. Run steps 0→5 in order; stop and report if a hard gate fails.

## Inputs

The user provides (or you infer) an **Input CSV** exported from AppTweak. Resolve three things before doing anything else:

- **CSV path** — the file to process.
- **App** — from the CSV filename prefix, or an explicit app name/alias, resolved via `shared/app_registry.py` (never guess a folder path).
- **Market** — from the CSV filename locale suffix, or explicit in the request.

**Filename contract** (required for auto-detection): `<AppName>_<COUNTRY>_<LANGUAGE>.csv`, e.g. `Game Emulator_US_EN.csv`, `FunVid_BR_PT-BR.csv`. The CSV must contain a `Keyword` column (`Volume`/`Rank` are optional). If the filename is locale-only (no app prefix), an explicit `--app` alias is required downstream.

If the requested market conflicts with `app_config.py` and the intended market cannot be safely inferred, ask; otherwise proceed with the detected values.

## Step 0 — Resolve app, market, CSV

Confirm the CSV exists and derive `app_alias` + `market`:

```powershell
python -c "from shared.locale_parser import split_app_and_locale; print(split_app_and_locale('<csv-filename>'))"
```

Resolve the app against the registry (this also gives you `folder`, `runner_path`, `config_path`):

```powershell
python -c "from shared.app_registry import resolve_app; import os; print(resolve_app('<alias>', os.getcwd()))"
```

If resolution fails, show the registered aliases and stop — do not invent a folder.

## Step 1 — Profile & config preflight (the "check profile" gate)

Confirm the app is actually configured and its store profile is healthy before spending subagent effort.

1. **Config**: read `<app folder>/app_config.py`. It should expose a full `APP_CONFIG` (identity, `intent_core_terms`, `feature_terms`, `style_terms`, `market_language_policy`, category). If it only exposes a legacy `FILTER_POLICY`, note that identity/terms will be derived from `App_Profile.json` + `PROJECT_MEMORY.md` — quality is lower; warn the user.
2. **Profile**: check `<app folder>/App_Profile.json` and `<app folder>/.cache/profiles/generated_profile.json`. The runner resolves the profile via `shared/profile_service.py::get_app_profile` (custom `App_Profile.json` wins; otherwise a generated profile is used/refreshed with a **14-day TTL**; otherwise it scrapes; otherwise it degrades to `EMPTY_FETCH_FAILED`).

You can inspect the effective profile status without side effects:

```powershell
python -c "from shared.effective_config import resolve_effective_app; import os; _,_,cfg,prof = resolve_effective_app('<alias>', os.getcwd(), '<MARKET>'); print(prof.get('ProfileStatus'), '| competitors:', len(prof.get('competitors', [])), '| last_checked:', prof.get('last_checked',''), '| err:', prof.get('ProfileError',''))"
```

Interpret the `ProfileStatus`:
- `CUSTOM` / `GENERATED_FRESH` → healthy, proceed.
- `GENERATED_STALE_FALLBACK` → network fetch failed but a stale cache exists; proceed but warn that competitors/metadata may be outdated.
- `EMPTY_FETCH_FAILED` → no custom profile and fetch failed; competitor-based filtering will be weak. Surface this and let the user decide whether to continue, author an `App_Profile.json`, or retry when online.

Report the config + profile findings in one short block before moving on. This is a **soft gate** (warn, don't hard-stop) unless the user asked to abort on a bad profile.

## Step 2 — Detect missing agentic cache

The AI classification (Step 2) and English gloss (Step 2.5) are read-only against the SQLite cache. Find what this CSV needs:

```powershell
python tools/warm_cache_helper.py find-misses --app <alias> --csv <csv-path> --market <MARKET>
```

Read `missing_count`. If **0**, skip straight to Step 4 (verify) — no subagents needed. Otherwise continue to Step 3.

## Step 3 — Warm the cache with real subagents

If `missing_count > 0`, warm the cache by delegating to the **`warm-agentic-cache`** procedure (do not hand-write cache rows). Follow `.agents/skills/warm-agentic-cache/SKILL.md` exactly:

1. `prepare-batches` → chunk the misses (200/batch by default).
2. Spawn **one subagent per batch** (in parallel when there is more than one) using the multi-agent tool available in this environment. Give each subagent its `batch_path`, the classification rubric from the warm-agentic-cache skill, the app's effective config for grounding, and an instruction to write only its `result_path`.
3. `save-results` per batch (add `--partial` to keep valid items and re-batch only the leftovers from `<batch>_remaining.json` instead of re-spawning a whole batch). Gloss-only misses are patched without clobbering existing classifications; bucket/language casing is normalized automatically.

Re-spawn only the batches/keywords that failed validation. Do not fabricate classifications.

## Step 4 — Verify cache is complete (hard gate)

```powershell
python tools/warm_cache_helper.py verify-cache --app <alias> --csv <csv-path> --market <MARKET>
```

This must print `PASS ... 0 missing` (exit code 0) before running the pipeline. If it still reports misses, return to Step 2/3 for the remaining keywords. **Do not run the pipeline until this passes.**

## Step 5 — Run the real pipeline

Run the master orchestrator (it resolves the runner from the registry, archives the CSV into `Input/<MMYYYY>/`, and writes the workbook to `Output/<MMYYYY>/`):

```powershell
python run_aso_filter.py --csv <csv-path> --app <alias>
```

Notes:
- `--app` is optional when the filename carries the app prefix, but pass it explicitly to be safe.
- Add `--interactive` only if the user asked for the web UI selector.
- The runner auto-refreshes the profile per Step 1's TTL, so a `GENERATED_FRESH`/scrape may happen here — that is expected.

## Step 6 — Report

On success, report:
- Detected app + market.
- Profile status (from Step 1) and whether cache warming was needed (how many keywords, how many batches/subagents).
- The Output workbook path (`.../Output/<MMYYYY>/<AppName>_<MARKET-hyphen>_Output.xlsx`).

On failure, surface the failing step, the exact error, and the concrete next action (fix config, author profile, re-warm remaining keywords, etc.) rather than silently retrying.

## Definition of done (self-check before you reply)

Do not finish until every box is true. If any is false, fix it before replying.

- [ ] App + market + CSV were resolved (Step 0); registry resolution succeeded.
- [ ] Profile/config preflight (Step 1) was run and its result reported (config type + `ProfileStatus`).
- [ ] `find-misses` ran; if misses existed they were warmed via **real subagents** (Step 3), not skipped or hand-filled.
- [ ] `verify-cache` printed `PASS ... 0 missing` **before** the pipeline was run (hard gate — never bypassed).
- [ ] `run_aso_filter.py` completed successfully and the Output workbook path was reported.
- [ ] Scope stayed on the requested app/market only.

## Guardrails

- Never run `run_aso_filter.py` / an app runner before Step 4 passes — cache-only steps will crash on unclassified keywords.
- Never fabricate cache entries or profile data to force a pass; warm via real subagents and let profile health be reported honestly.
- Scope to the app/market the user asked for; do not batch every app/market unless explicitly requested.
- If `save-results` reports a `context_hash` mismatch, the app config/profile changed since `find-misses` — redo Step 2 before retrying.
- This skill only runs the pipeline. Seed keyword *creation* is a separate, earlier step — use `.agents/skills/aso-keyword-research/SKILL.md` when the user needs to build seeds rather than process an existing export.

## Addendum - metadata/ads suitability gate

After Step 4 passes, run `run_aso_filter.py`. The post-candidate suitability gate runs inside the app runner after classification/scoring. If suitability cache is missing for a keyword that needs metadata/ads suitability audit, the runner fails fast with `Metadata suitability audit is cache-only...` and exports a candidate pool CSV under `.cache/candidate_pools/`.

Suitability audit answers whether the exact query can surface the right app type on Google Play and whether it is specific enough for this app's metadata/ads. It covers unlisted single-token terms and multi-word candidates in audited buckets such as `Feature Keywords`, `System Keywords`, `Broad Expansion`, `Consider Keywords`, `Style Keywords`, `Generic Style Reserve`, and `Game Keywords` when they meet the configured volume rule.

Use that exported candidate pool CSV for the suitability helper:

```powershell
python tools/suitability_cache_helper.py verify-cache --app <alias> --csv <candidate-pool-csv> --market <MARKET>
```

If it fails, warm the suitability cache with real subagents:

```powershell
python tools/suitability_cache_helper.py find-misses --app <alias> --csv <candidate-pool-csv> --market <MARKET>
python tools/suitability_cache_helper.py prepare-batches --misses <suitability-misses-json> --output-dir .cache/suitability_batches
python tools/suitability_cache_helper.py save-results --app <alias> --batch <batch_path> --results <result_path> --market <MARKET>
python tools/suitability_cache_helper.py verify-cache --app <alias> --csv <candidate-pool-csv> --market <MARKET>
```

Result schema for each suitability subagent batch:

```json
{
  "batch_id": "us_en_suitability_batch_1",
  "items": [
    {
      "keyword": "singleword",
      "suitability_bucket": "Research Only",
      "metadata_eligible": false,
      "ads_eligible": false,
      "research_only": true,
      "confidence": 0.8,
      "decision_rule": "subagent_too_broad",
      "reason": "Single-word feature is too broad for metadata."
    }
  ]
}
```

Do not fabricate suitability rows. Deterministic code still wins: risk/drop/language/manual-review cannot be rescued by subagent output, block-listed single tokens stay `SINGLE_TOKEN_TOO_BROAD`, keep-listed platform terms stay eligible, and app-specific `user_overrides.suitability_keep_terms` bypass the subagent audit only for exact phrases the app owner has accepted.
