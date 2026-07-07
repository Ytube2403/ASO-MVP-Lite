# ASO MVP Usage Guide

This is the current operator guide for running the pipeline. The detailed spec lives in `docs/ASO_Keyword_Planner_v4_5.md`; this file focuses on the correct operating order.

## 1. Prepare An App

Each app needs:

- `apps/<AppName>/app_config.py`: identity, market, semantic groups, filters, scoring/risk policy.
- `apps/<AppName>/App_Profile.json`: live metadata and competitor profile.
- An input keyword CSV from AppTweak/SensorTower with a clear market name, for example `NDS Emulator_BR_PT.csv`.

If you change deterministic brand/risk lists such as `risky_ip_terms`, `risky_platform_terms`, `competitor_brands`, or `platform_affiliation_terms`, rerun the pipeline. You do not need to re-warm the AI cache.

Only bump the top-level `ruleset_version` when the agentic prompt/rubric changes and you want old `AISemanticBucket`/`AIDecisionRule` values to be reclassified. After bumping it, warm cache again for every market you plan to run.

## 2. Put The CSV In The Standard Folder

Recommended input location:

```text
apps/<AppName>/Input/<MMYYYY>/<AppName>_<MARKET>.csv
```

Example:

```text
apps/NDS_Emulator/Input/072026/NDS Emulator_BR_PT.csv
```

You can pass a CSV from any path to `run_aso_filter.py`; the orchestrator archives it into the app folder.

## 3. Verify Agentic Cache Before Running

The runtime pipeline is cache-only: runners do not call AI or translation network providers. Before a real pipeline run, verify cache:

```powershell
python tools/warm_cache_helper.py verify-cache --app <AppName> --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --market <MARKET>
```

If the output is `PASS ... 0 missing`, you can run the pipeline.

If verification fails because intent or `english_gloss` is missing, warm cache in this order:

```powershell
python tools/warm_cache_helper.py find-misses --app <AppName> --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --market <MARKET> --output .cache/<app>_<market>_missing.json
python tools/warm_cache_helper.py prepare-batches --misses .cache/<app>_<market>_missing.json --output-dir .cache/agentic_batches
```

Then use Antigravity/Codex/subagents to classify each batch according to `.agents/skills/warm-agentic-cache/SKILL.md`, save the results, and verify again:

```powershell
python tools/warm_cache_helper.py save-results --app <AppName> --batch <batch_path> --results <result_path> --market <MARKET>
python tools/warm_cache_helper.py verify-cache --app <AppName> --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --market <MARKET>
```

Run the pipeline only after `verify-cache` passes.

## 4. Metadata/Ads Suitability Audit After Candidate Pool

After agentic cache, the pipeline has a separate post-candidate gate for `MetadataEligible`/`AdsEligible`. This gate does not replace relevancy. It also asks: "If a user searches this keyword on Play Store, can it surface the right app type?" and "If it surfaces this app, is it specific enough for metadata/ads?"

For example, `stik bluetooth`, `setting tombol gamepad`, `arcade`, `pizza`, `moonlight`, and `turbospeed` may be related to a feature/category but are too weak by themselves, so they go to `ResearchOnly`. Atomic platform terms such as `nds`, `ds`, and `gba` are kept only when they are in the config keep list. App-specific phrase overrides can be set in `user_overrides.suitability_keep_terms`.

Suitability audit does not run on raw AppTweak CSVs. It needs a candidate pool after classification/scoring, with columns such as `Keyword`, `Bucket`, `DecisionRule`, and `Volume`. Correct flow:

1. Run the pipeline after agentic cache passes.
2. If a keyword needs suitability audit but has no cache row, the pipeline fails fast with `Metadata suitability audit is cache-only`.
3. The error exports a candidate pool to `.cache/candidate_pools/..._candidates.csv`.
4. Use that candidate pool to warm suitability cache, then rerun the pipeline.

Check the candidate pool:

```powershell
python tools/suitability_cache_helper.py verify-cache --app <AppName> --csv ".cache/candidate_pools/<exported_candidates>.csv" --market <MARKET>
```

If verification fails, create subagent audit batches from the candidate pool:

```powershell
python tools/suitability_cache_helper.py find-misses --app <AppName> --csv ".cache/candidate_pools/<exported_candidates>.csv" --market <MARKET> --output .cache/<app>_<market>_suitability_missing.json
python tools/suitability_cache_helper.py prepare-batches --misses .cache/<app>_<market>_suitability_missing.json --output-dir .cache/suitability_batches
```

Each subagent result must include `keyword`, `suitability_bucket`, `metadata_eligible`, `ads_eligible`, `research_only`, `confidence`, `decision_rule`, and `reason`. Save and verify again:

```powershell
python tools/suitability_cache_helper.py save-results --app <AppName> --batch <batch_path> --results <result_path> --market <MARKET>
python tools/suitability_cache_helper.py verify-cache --app <AppName> --csv ".cache/candidate_pools/<exported_candidates>.csv" --market <MARKET>
```

Notes:

- Deterministic rules still beat subagent output.
- Risk/drop/language/manual-review rows cannot be rescued.
- Single-token block terms stay `SINGLE_TOKEN_TOO_BROAD`.
- Single-token keep terms and `user_overrides.suitability_keep_terms` stay eligible.
- Hand-declared `feature_terms`/`intent_core_terms` usually skip subagent audit when they land deterministically in `Feature Keywords`, `System Keywords`, or `Core Intent Final`.
- The gate fails loud for unlisted single-token terms, AI-inferred keywords, and multi-word keywords in `Feature Keywords`, `System Keywords`, `Broad Expansion`, `Consider Keywords`, `Style Keywords`, `Generic Style Reserve`, and `Game Keywords` when they meet `metadata_suitability.audit_min_volume` (default `5`).

## 5. Run The Pipeline

Prefer the central orchestrator from the repo root:

```powershell
python run_aso_filter.py --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --app <AppName>
```

Interactive mode:

```powershell
python run_aso_filter.py --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --app <AppName> --interactive
```

If the CSV name is enough to resolve the app, `--app` can be omitted. If an app has ambiguous aliases, pass `--app` explicitly.

## 6. Review Workbook Output

After the run finishes, open the workbook in `apps/<AppName>/Output/<MMYYYY>/`.

Review at least:

- `00_Project_Memory`: app/profile/config snapshot for audit.
- `01_Main_Keyword_Shortlist`: metadata-safe target 40 selected by utility + diversity; only rows with `MetadataEligible=True`.
- `04_Dropped_Audit`: dropped keywords and drop reasons.
- `06_All_Candidates`: audit columns `PreAIRule`, `AISemanticBucket`, `AIDecisionRule`, `AIReason`, `AIEnglishGloss`, `MetadataEligible`, `AdsEligible`, `ResearchOnly`, `SuitabilityRule`, `SuitabilityReason`.
- `13_Top_By_Volume`: clean high-volume keywords to quickly check for missed opportunities.
- `14_Not_Selected_Audit`: reasons such as `SINGLE_TOKEN_TOO_BROAD`, `SUITABILITY_RESEARCH_ONLY`, or `SUITABILITY_PENDING_AUDIT` for related keywords that should not be used in metadata/ads or still need suitability cache.
- `15_Selector_Quality_Log`, when present: selector/backfill warnings.

For game/emulator apps, pay special attention to IP/game/franchise/brand keywords. Terms such as `mortal kombat`, `naruto`, `resident evil`, `pac man`, and `metal slug` should appear only in Dropped Audit, not in shortlist/feature sheets.

## 7. When To Rerun

- Change `app_config.py` risk/brand/noise/feature/core terms: rerun the pipeline; AI cache does not need re-warming.
- Change `App_Profile.json`: rerun the pipeline; if profile changes affect agentic context and `verify-cache` reports misses, warm them.
- Bump `ruleset_version`: warm every market you plan to run, then run the pipeline.
- Change `metadata_suitability.single_token_policy.keep_terms`/`block_terms`, `metadata_suitability.audit_min_volume`, or `user_overrides.suitability_keep_terms`: rerun the pipeline. If suitability verification reports misses because the context hash changed, warm suitability audit for that market.
- New CSV or new market: run `verify-cache` first; warm cache if there are misses.

## 8. Batch Command

Use a manifest:

```powershell
python run_aso_batch.py --manifest path\to\manifest.json
```

The batch runner is also cache-only. If any market has misses, that job fails fast; warm cache for that market and rerun.
