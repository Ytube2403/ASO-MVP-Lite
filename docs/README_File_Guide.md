# ASO Keyword Filter v4.5 File Structure Guide

## Root

### `run_aso_filter.py`

Main entrypoint. It parses locale, resolves app aliases through `shared/app_registry.py`, archives the CSV into `apps/<AppName>/Input/<MMYYYY>/`, runs the app runner, and writes the workbook to `apps/<AppName>/Output/<MMYYYY>/`.

### `run_aso_batch.py`

Compatibility wrapper for `tools/run_aso_batch.py`. Runs multiple locales from a JSON manifest; defaults to at most 2 parallel jobs.

### `export_master_keywords.py`

Compatibility wrapper for `tools/export_master_keywords.py`. Scans app inputs and workbook outputs, finds sheets ending in `Dropped_Audit`, removes hard-dropped terms, and writes aggregate workbooks to `data/master_keywords/`.

### `Sync.bat`

One-click pull, status, and push helper for Windows users.

## `apps/`

Each app has its own workspace:

```text
apps/<AppName>/
|-- app_config.py
|-- App_Profile.json
|-- PROJECT_MEMORY.md
|-- Input/<MMYYYY>/
|-- Output/<MMYYYY>/
`-- runner Python
```

Registered apps:

- `apps/AR_Filter/`
- `apps/Control_Widget/`
- `apps/ElectricGun/`
- `apps/Emoji_Battery_Icon_Customize/`
- `apps/FunVid/`
- `apps/Game_Emulator/`
- `apps/NDS_Emulator/`
- `apps/Prank_Sounds/`
- `apps/App_Template/`

`AR_Filter` and `Control_Widget` still use `*_v4_3.py` runners. `Game_Emulator` uses `run_game_emulator_v4_4.py`. `ElectricGun`, `Emoji_Battery_Icon_Customize`, `FunVid`, `NDS_Emulator`, `Prank_Sounds`, and `App_Template` use `run_pipeline.py`.

Seed filenames `FunVid_100_Keywords_<locale>.csv` and `FunVid_AnimalFace_<locale>.csv` are routed to `FunVid` through registry aliases.

## `shared/`

- `shared/paths.py`: central path source for `apps`, `docs`, `data`, and `data/master_keywords`.
- `shared/app_registry.py`: maps app aliases to folder, runner, and config.
- `shared/effective_config.py`: loads runtime-equivalent effective app config, including legacy runner config and `FILTER_POLICY`.
- `shared/locale_parser.py`: shared locale parser for orchestrator, exporter, tracker, and batch.
- `shared/language_detector.py`: market-policy-aware language detection.
- `shared/agentic_keyword_classifier.py`: cache-only classifier/runtime using provider `antigravity_subagent`; runners fail fast when cache is missing.
- `shared/ai_keyword_classifier.py`: compatibility shim that re-exports `agentic_keyword_classifier`.
- `shared/en_gloss_resolver.py`: resolves `EN` from CSV or `AIEnglishGloss`; does not call translation networks.
- `shared/keyword_filter/`: precompiled matcher, hard filter, classifier, validator, audit, atomic cache, complete-token truncation hardening, and `shortlist.py` for the shared `target 40 utility + diversity` main shortlist. It deduplicates by utility, applies semantic cluster diversity with Jaccard similarity, and safe-backfill rechecks score/relevancy/demand. `suitability.py` is the post-candidate metadata/ads suitability gate: it writes `MetadataEligible`/`AdsEligible`/`ResearchOnly`, blocks feature/category queries with weak acquisition intent, keeps owner-approved single-token/phrase overrides, fails fast when a keyword needs subagent audit but has no cache row, and reads subagent audits from SQLite table `keyword_suitability_analysis`. `classifier.py` is the risk-precedence source of truth: declared-safe + functional-anchor core override, no override for `platform_affiliation_terms`, and `ai_classic_ip` for AI-recognized classic game IP. `scoring.py` is the scoring v4.5 source of truth: log-reach `VolumeN`, cache-backed `calculate_rubric_relevancy`, `resolve_balanced_weights` removing KEIN from `BalancedScore`, `safe_reach_ceiling` using percentile 95 over non-competitor/non-irrelevant rows, and `dampen_stacked_relevancy` for low-demand keyword stuffing. `report_export.py::write_quality_log_sheet` exports selector warnings such as `SAFE_POOL_EXHAUSTED` to sheet `15_Selector_Quality_Log`. See section 37 in `ASO_Keyword_Planner_v4_5.md`.
- `shared/text_dedup.py`: Unicode deduplication for `01_Main_Keyword_Shortlist`.
- `shared/profile_service.py`: custom/generated profile cache and stale fallback.
- `shared/project_memory.py`: reads `app_config.py` and `App_Profile.json` to render Project Memory for the dashboard, workbook, and `PROJECT_MEMORY.md`.

## `tools/`

- `tools/run_aso_batch.py`: batch implementation.
- `tools/export_master_keywords.py`: Master Keywords exporter implementation.
- `tools/warm_cache_helper.py`: official agentic-cache workflow for the whole project: `find-misses`, `prepare-batches`, `save-results`, `verify-cache`. When an app bumps `ruleset_version`, old cache rows become misses under the new context hash and the tool forces re-warm for markets that need to run.
- `tools/suitability_cache_helper.py`: subagent-audit workflow for metadata/ads suitability: `find-misses`, `prepare-batches`, `save-results`, `verify-cache`. It uses the shared SQLite file `.cache/agentic_keyword_analysis.sqlite3` but a separate table, `keyword_suitability_analysis`.
- `tools/generate_funvid_csv.py`, `tools/generate_animalface_csv.py`, `tools/generate_100_keywords_csv.py`: generate sample seed CSVs for `FunVid`.

Root wrappers are kept so old commands still work.

## `.agents/`

- `.agents/skills/aso-keyword-research/SKILL.md`: internal skill that guides agents to expand seed keyword sets by app using config/profile, competitor research, local search behavior, and web research. It supports input research and does not replace the pipeline/filter runner.
- `.agents/skills/aso-keyword-research/agents/openai.yaml`: minimal UI metadata for the skill, including display name, short description, and default prompt.
- `.agents/skills/warm-agentic-cache/SKILL.md`: skill that guides an orchestrator such as Antigravity, Claude Code, or similar tooling to warm missing agentic classification cache with real subagents (`find-misses -> prepare-batches -> spawn subagent classification -> save-results -> verify-cache`) before the real pipeline run, instead of asking the user to run each `tools/warm_cache_helper.py` command manually.
- `.agents/skills/warm-agentic-cache/agents/openai.yaml`: minimal UI metadata for this skill, same format as `aso-keyword-research`.
- `.agents/skills/warm-suitability-cache/SKILL.md`: skill that guides an orchestrator to warm metadata/ads suitability cache after the candidate pool with real subagents. It uses the candidate pool CSV exported by the pipeline on `SuitabilityAuditError`, never the raw AppTweak CSV. Its rubric is generic to the current app and requires an app-specific acquisition brief before choosing `Eligible` or `Research Only`.
- `.agents/skills/warm-suitability-cache/agents/openai.yaml`: minimal UI metadata for the suitability skill.

Current validation note: local parser checks pass. The skill no longer contains `file:///`, `search_web`, or folder/skill-name mismatch. `quick_validate.py` from `skill-creator` requires Python module `yaml`/`PyYAML`; if the environment has not installed PyYAML, the official validator cannot run, but the main form rules have been checked with local scripts.

## `tracker/`

- `tracker/run_dashboard.py`: Flask API, web launcher, and `GET /api/setup/<app_name>` API for the Setup tab.
- `tracker/db_manager.py`: SQLite schema and queries.
- `tracker/data_scanner.py`: scans CSVs under `apps/*/Input/`.
- `tracker/static/`: SPA HTML, CSS, and JavaScript, including the `Setup` tab for app identity, keyword setup, competitor setup, drop policy, overrides, and warnings.

`tracker/keyword_tracker.db` is a local file and should not be committed.

## `docs/`

- `docs/ASO_Keyword_Planner_v4_5.md`: pipeline v4.5 logic spec, including the new shortlist quota, sheet `13_Top_By_Volume`, app `FunVid`, and agentic cache-only runtime.
- `docs/USAGE.md`: current operator guide: prepare app/CSV, verify cache, warm cache, run pipeline, review workbook, and decide when to bump `ruleset_version`.
- `apps/Game_Emulator/AGENTIC_CACHE_WORKFLOW.md`: cache-only workflow guide for Game Emulator, replacing old scratch scripts.
- `docs/SETUP_WINDOWS.md`: Windows software, extension, Python package, and environment-check checklist.
- `docs/App_Config_Template.py`: config template.
- `docs/App_Profile_Template.json`: profile template.
- `docs/english_words_10k.txt`: English whitelist.
- `docs/DESIGN.md`: dashboard design system.
- `.env.example`: local environment-variable template for auxiliary tooling; ASO runners do not read AI runtime API keys.

## `data/`

- `data/google_play_country_language_map.xlsx`: country and language mapping.
- `data/master_keywords/`: generated Master Keywords workbooks; do not commit.

## `tests/`

Regression tests cover registry, locale parser, hard filter, truncation false positives, deduplication, EN gloss resolver, profile, project memory, exporter, and batch runner.

- `tests/test_ai_keyword_classifier.py`: cache-only hit/miss behavior, canonical duplicate reuse, and pre-AI skip/preserve rules.
- `tests/test_en_gloss_resolver.py`: `EN` column priority, `AIEnglishGloss` fallback, and fail-fast behavior when a non-English keyword lacks a gloss.
- `tests/test_warm_cache_helper.py`: effective config, batch contract, and agentic-cache result validation.
- `tests/test_metadata_suitability.py`: single-token keep/block policy and shortlist exclusion.
- `tests/test_main_shortlist_builder.py`: selector quality gate, boolean suitability parsing from CSV/export, and `SUITABILITY_PENDING_AUDIT` in the not-selected log.
- `tests/test_suitability_cache_helper.py`: schema validation, duplicate/missing keyword rejection, context hash mismatch, and `verify-cache` for suitability audit.

## `releases/`

No local zip package is currently checked in. Zip files are ignored to keep the repository source-only and lightweight.

## Root Setup Files

- `requirements.txt`: Python package list for the full pipeline environment.
- `.vscode/extensions.json`: recommended VS Code extensions for Python, Pylance, and CSV editing.
