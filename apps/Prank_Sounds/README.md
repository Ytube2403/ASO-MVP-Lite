# Prank Sounds ASO Pipeline - Run & Configuration Guide

This folder contains the production pipeline for the Prank Sounds app family. It can run directly through `run_pipeline.py` or through the root orchestrator `run_aso_filter.py` with CSV names containing `Prank` or `Pranky`.

Configuration is separated from source code:

- App-specific configuration lives in `app_config.py`.
- Store/profile context lives in `App_Profile.json`.

Before running on a fresh Windows machine, follow [the full setup guide](../../docs/SETUP_WINDOWS.md).

## Folder Structure

```text
apps/Prank_Sounds/
|-- README.md
|-- app_config.py
|-- App_Profile.json
|-- PROJECT_MEMORY.md
|-- run_pipeline.py
|-- interactive_optimizer.html
`-- interactive_description_editor.html
```

## Configure Prank Sounds

Edit `app_config.py` when needed:

- **Identity:** `app_id`, `app_name`, `category`, and default target `market`.
- **Semantic groups:**
  - `intent_core_terms`: main app-search intent.
  - `feature_terms`: concrete sound/prank features.
  - `style_terms`: style, UI, IP, or aesthetic themes allocated only to safer fields.
- **Filters:**
  - `competitor_brands`: competitor brands blocked from primary metadata.
  - `noise_terms`: broad generic terms such as `app`, `free`, `download`, `android`.
  - `typo_blacklist`: misspellings or auto-suggest noise.

`App_Profile.json` stores live metadata and 3-5 main competitors. Project Memory reads `app_config.py` and `App_Profile.json` directly and renders the current setup into dashboard tab `Setup`, workbook sheet `00_Project_Memory`, and `PROJECT_MEMORY.md`.

## Input File Naming

Use:

```text
<AppName>_<Country>_<Language>.csv
```

Examples:

- `PrankSounds_US_EN.csv`
- `Pranky_PH_FIL.csv`

## Run Keyword Filtering

Use the current operating flow in `../../docs/USAGE.md`: verify cache first, warm cache if there are misses, then run the pipeline. If the agentic prompt/rubric changes and `ruleset_version` is bumped, warm every market you plan to run.

From `ASO-MVP/apps/Prank_Sounds`:

```powershell
python run_pipeline.py --csv C:\path\to\PrankSounds_US_EN.csv --market US_EN
python run_pipeline.py --csv C:\path\to\PrankSounds_US_EN.csv --market US_EN --interactive
```

Or from the repo root through the orchestrator:

```powershell
python run_aso_filter.py --csv C:\path\to\PrankSounds_US_EN.csv
python run_aso_filter.py --csv C:\path\to\Pranky_PH_FIL.csv --interactive
```

The orchestrator archives inputs into `apps/Prank_Sounds/Input/<MMYYYY>/` and writes outputs into `apps/Prank_Sounds/Output/<MMYYYY>/`.

The workbook includes the full report, `target 40 utility + diversity` shortlist, `13_Top_By_Volume`, `00_Project_Memory`, and audit reasons for keeping/dropping each keyword. The pipeline also updates `PROJECT_MEMORY.md`.

## Shared Platform Logic v4.5

Prank Sounds uses shared modules under `ASO-MVP/shared/`:

- `shared/language_detector.py`: market-policy-aware grouping into `PRIMARY`, `SECONDARY`, `MIXED`, `FOREIGN`, `UNKNOWN`.
- `shared/keyword_filter/`: matcher, hard filter, classifier, validator, audit, cache, and versioning.
- `shared/text_dedup.py`: Unicode `NFKC` + `casefold()` deduplication, locale-aware stemming, and `MergedVariants`.
- `shared/en_gloss_resolver.py`: resolves `EN` from CSV or `AIEnglishGloss` warmed by agentic cache.
- `shared/profile_service.py`: strict `App_Profile.json` priority, generated cache, and stale fallback.
- `shared/project_memory.py`: setup overview for tracker tab `Setup`, sheet `00_Project_Memory`, and `PROJECT_MEMORY.md`.

Important rules:

- `FOREIGN` -> `Language Mismatch Audit`.
- `UNKNOWN` -> `Manual Review`.
- `MIXED` -> `Consider Keywords` when `mixed_allowed=True`.
- `SECONDARY` normally stays in `Consider Keywords`; exact raw matches to `intent_core_terms` can still keep Core behavior.
- Naturalness does not hard-drop other scripts through `LANGUAGE_BLEED`; language detection owns that decision.
- Selection cache can be reused only when `app_id`, market, input hash, config hash, and engine version match the current run.
- Dedup applies only to `01_Main_Keyword_Shortlist`; topic sheets remain independent review lists.

## Sheet Overlap Rule

`01_Main_Keyword_Shortlist` and topic sheets such as `02_Hairclipper_Keywords`, `03_Taser_Keywords`, `04_Gun_Sound_Keywords`, and `05_Prank_Sound_General` are independent lists. Strong keywords may appear in both the Main List and the relevant topic sheet. Dedup applies only inside the Main List; topic sheets keep the full keyword set for evaluation.
