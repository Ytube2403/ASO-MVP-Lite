# ASO App Template - New App Configuration Guide

This template helps you set up the ASO keyword filtering workflow for a new app without editing the shared pipeline source code.

The system separates configuration from code:

- App-specific configuration lives in `app_config.py`.
- Store/profile context lives in `App_Profile.json`.
- Shared runtime logic lives under `../../shared/`.

Before running on a new Windows machine, follow [the full setup guide](../../docs/SETUP_WINDOWS.md).

## Folder Structure

```text
apps/App_Template/
|-- README.md
|-- app_config.py
|-- App_Profile.json
|-- PROJECT_MEMORY.md
|-- run_pipeline.py
|-- interactive_optimizer.html
`-- interactive_description_editor.html
```

## Configure A New App

### 1. Edit `app_config.py`

Update these sections:

- **Identity:** `app_id`, `app_name`, `category`, and default target `market`.
- **Semantic groups:**
  - `intent_core_terms`: main app-search intent, for example `photo editor`, `crop photo`.
  - `feature_terms`: concrete app features, for example `retouch`, `filter`, `collage`.
  - `style_terms`: style, UI, IP, or aesthetic themes, for example `aesthetic`, `vintage`. These are allocated only to Full Description to reduce IP risk.
- **Filters:**
  - `competitor_brands`: competitor names blocked from primary metadata.
  - `noise_terms`: generic broad words such as `app`, `free`, `download`, `android`.
  - `typo_blacklist`: misspellings or meaningless auto-suggest noise.

### 2. Fill `App_Profile.json`

Provide:

- `app_identity`: package ID, app name, and category.
- `live_store_metadata`: current short description and related store text.
- `suggested_competitors`: 3-5 main competitors with `package_id`, `title`, `short_description`, and `desc200`.

Project Memory reads `app_config.py` and `App_Profile.json` directly. It renders the current setup in dashboard tab `Setup`, workbook sheet `00_Project_Memory`, and `PROJECT_MEMORY.md`.

### 3. Name Input CSVs Clearly

Use:

```text
<AppName>_<Country>_<Language>.csv
```

Example:

```text
MyNewApp_US_EN.csv
```

## Run Keyword Filtering

Current usage flow is in `../../docs/USAGE.md`: verify cache first, warm misses if any, then run the pipeline. If the agentic prompt/rubric changes and `ruleset_version` is bumped, warm every market you plan to run.

From `ASO-MVP/apps/App_Template`:

```powershell
python run_pipeline.py --csv C:\path\to\MyNewApp_US_EN.csv --market US_EN
python run_pipeline.py --csv C:\path\to\MyNewApp_US_EN.csv --market US_EN --interactive
```

From the repo root:

```powershell
python apps\App_Template\run_pipeline.py --csv C:\path\to\MyNewApp_US_EN.csv --market US_EN
```

The workbook includes the full report, `target 40 utility + diversity` shortlist, `13_Top_By_Volume`, `00_Project_Memory`, and audit reasons for keeping/dropping each keyword. The pipeline also updates `PROJECT_MEMORY.md` for handoff and setup audit.

## After Filtering

From the repo root, you can run:

```powershell
python export_master_keywords.py --app <AppName>
python export_master_keywords.py --all
python tracker/run_dashboard.py
```

Master Keywords exports are written to `data/master_keywords/`. The dashboard opens at `http://127.0.0.1:5100`.

## Shared Platform Logic v4.5

The template pipeline uses shared modules under `ASO-MVP/shared/`:

- `shared/language_detector.py`: market-policy-aware language grouping into `PRIMARY`, `SECONDARY`, `MIXED`, `FOREIGN`, `UNKNOWN`.
- `shared/keyword_filter/`: precompiled matcher, hard filter, classifier, validator, audit, cache, and versioning.
- `shared/text_dedup.py`: Unicode `NFKC` + `casefold()` deduplication, locale-aware stemming, and `MergedVariants`.
- `shared/en_gloss_resolver.py`: resolves `EN` from CSV or `AIEnglishGloss` warmed by agentic cache.
- `shared/profile_service.py`: strict custom profile priority, atomic generated cache, and stale fallback.
- `shared/project_memory.py`: setup overview for tracker tab `Setup`, sheet `00_Project_Memory`, and `PROJECT_MEMORY.md`.
- `shared/locale_parser.py`: shared locale parsing for orchestrator, exporter, tracker, and batch runner.

Important rules:

- `FOREIGN` -> `Language Mismatch Audit`.
- `UNKNOWN` -> `Manual Review`.
- `MIXED` -> `Consider Keywords` when `mixed_allowed=True`.
- `SECONDARY` stays in `Consider Keywords`.
- Naturalness no longer hard-drops non-Latin scripts through `LANGUAGE_BLEED`; language is handled by the language detector.
- Agentic cache is read-only at runtime. If the prompt/rubric changes, bump top-level `ruleset_version` in `app_config.py` to force re-warm. Brand/risk list edits do not require re-warm.
- Risk policy source of truth is `shared/keyword_filter/classifier.py`.
- Main shortlist v4.5 uses `target 40 utility + diversity`; Feature has its own quota and sheet `02_Feature_Keywords`.
- Workbook v4.5 includes `13_Top_By_Volume`.
- Truncation v4.5 protects complete tokens and singular/plural variants.
- Word-order permutations remain separate when `auto_merge_token_bag=False`.
- Dedup applies only to `01_Main_Keyword_Shortlist`; feature/style sheets sort by normal priority.
- Accent-fold and near-duplicate keywords remain independent; `ReviewVariants` is no longer used.

Batch command:

```powershell
python ..\..\run_aso_batch.py --manifest path\to\manifest.json --max-workers 3
```
