# ASO-MVP-Lite Keyword Filter Pipeline & Tracker v4.5

Lite uses an agentic cache warmed by Antigravity subagents before runtime. The ASO system includes a keyword filtering pipeline, a local tracking dashboard, and Master Keywords export tools.

Need stronger local quality and offline execution after downloading a model? Use [ASO-MVP-Max](https://github.com/Ytube2403/ASO-MVP-Max).

## Folder Structure

```text
ASO-MVP-Lite/
|-- apps/                         # Per-app workspaces
|   |-- AR_Filter/
|   |-- Control_Widget/
|   |-- ElectricGun/
|   |-- Emoji_Battery_Icon_Customize/
|   |-- FunVid/
|   |-- Game_Emulator/
|   |-- NDS_Emulator/
|   |-- Prank_Sounds/
|   `-- App_Template/
|
|-- shared/                       # Required shared engine
|   |-- keyword_filter/           # Matcher, hard filter, classifier, validator, audit, cache
|   |-- app_registry.py           # Alias -> app folder -> runner -> config
|   |-- paths.py                  # Centralized workspace paths
|   |-- locale_parser.py
|   |-- language_detector.py
|   |-- agentic_keyword_classifier.py
|   |-- en_gloss_resolver.py
|   |-- profile_service.py
|   |-- project_memory.py         # Setup snapshot for dashboard, workbook, and handoff markdown
|   `-- text_dedup.py
|
|-- tools/                        # Operational tools
|   |-- run_aso_batch.py
|   |-- warm_cache_helper.py
|   |-- suitability_cache_helper.py
|   `-- export_master_keywords.py
|
|-- tracker/                      # Local Flask dashboard and SQLite database
|   |-- run_dashboard.py
|   `-- static/
|
|-- docs/                         # Specs, templates, guides, and dictionaries
|   |-- ASO_Keyword_Planner_v4_5.md
|   |-- SETUP_WINDOWS.md
|   |-- README_File_Guide.md
|   `-- english_words_10k.txt
|
|-- .vscode/                      # Recommended VS Code extensions
|-- .agents/                      # Internal skills for keyword research workflows
|-- requirements.txt              # Python packages for a complete environment
|-- data/                         # Shared resources and aggregate outputs
|   |-- google_play_country_language_map.xlsx
|   `-- master_keywords/          # Generated; do not commit
|
|-- releases/                     # Local zip packages; do not commit
|-- tests/                        # Regression tests
|-- run_aso_filter.py             # Main entrypoint
|-- run_aso_batch.py              # Compatibility wrapper for tools/run_aso_batch.py
|-- export_master_keywords.py     # Compatibility wrapper for tools/export_master_keywords.py
`-- Sync.bat
```

## Principles

- Each app keeps its own `app_config.py`, `App_Profile.json`, `PROJECT_MEMORY.md`, `Input/`, `Output/`, and runner under `apps/<AppName>/`.
- Filtering logic, locale parsing, agentic cache, English gloss resolution, profile loading, project memory, and deduplication must use the shared modules in `shared/`.
- Truncation logic in v4.5 uses the hardened shared engine: complete tokens such as `emoji`, `icon`, `sound`, `filter`, and `widget` are not dropped accidentally; suspicious prefixes go to Manual Review instead of hard-drop.
- All registered apps use `agentic_keyword_classifier` in cache-only mode. Runners do not call AI or translation network providers.
- Cache misses are handled outside the runner by Antigravity subagents through `tools/warm_cache_helper.py`.
- Metadata/ads suitability runs after the candidate pool exists. Related keywords that lack strong Play Store acquisition intent become `ResearchOnly` and do not enter `01_Main_Keyword_Shortlist`.
- The v4.5 main shortlist uses `target 40 utility + diversity`. Workbooks include `13_Top_By_Volume` for quick review of clean high-volume keywords.
- `FunVid` is registered with aliases `FunVid`, `Fun_Vid`, `FunnyFaceFilters`, `FunVid_100_Keywords`, and `FunVid_AnimalFace`.
- Every runner follows the agentic cache-only flow: Antigravity subagents write intent, language, and `english_gloss` to SQLite first; the runner only reads cache and fails fast on misses.
- Risk policy uses `shared/keyword_filter/classifier.py` as the source of truth. Core overrides only rescue risky/platform terms that are declared safe and have a functional anchor. `platform_affiliation_terms` cannot be overridden. AI rules such as `classic_ip_intent`/`ai_classic_ip` are handled as IP risk through `risky_ip_action`.
- Shared resources live under `data/`; documentation lives under `docs/`.
- Old root-level commands are kept as compatibility wrappers.

## Agentic Cache v4.5

Agentic results are cached in `.cache/agentic_keyword_analysis.sqlite3`. Sheet `06_All_Candidates` includes audit columns such as `NeedsAI`, `PreAIAction`, `PreAIRule`, `PreAIReason`, `CanonicalKeyword`, `AISemanticBucket`, `AIDecisionRule`, `AIReason`, `AIConfidence`, `AIStatus`, and `AIEnglishGloss` so operators can see which keywords used cache, reused a canonical result, or were skipped before batching.

Use the official flow for every app:

```powershell
python tools/warm_cache_helper.py find-misses --app Game_Emulator --csv "apps/Game_Emulator/Input/072026/Game Emulator_MX_ES.csv" --market MX_ES
python tools/warm_cache_helper.py prepare-batches --misses .cache/game_emulator_mx_es_missing.json
python tools/warm_cache_helper.py save-results --app Game_Emulator --batch .cache/agentic_batches/mx_es_batch_1.json --results .cache/agentic_batches/mx_es_batch_1_result.json
python tools/warm_cache_helper.py verify-cache --app Game_Emulator --csv "apps/Game_Emulator/Input/072026/Game Emulator_MX_ES.csv" --market MX_ES
```

You can replace `--csv` with `--input-dir apps/<App>/Input/<MMYYYY>` to scan multiple markets at once. Runners only read cache; if intent or `english_gloss` is missing for a non-English keyword, the pipeline fails fast and prints sample misses to warm first.

Cache keys can be intentionally invalidated with the top-level `ruleset_version` in `app_config.py`. Brand/risk lists such as `risky_ip_terms`, `risky_platform_terms`, `competitor_brands`, and `platform_affiliation_terms` are deterministic filters and take effect on every run without re-warming. Bump `ruleset_version` only when the agentic prompt/rubric changes and old `AISemanticBucket`/`AIDecisionRule` values must be reclassified.

## Metadata/Ads Suitability Gate

After keywords reach the candidate pool and have scoring/classification, the runner calls `shared.keyword_filter.apply_metadata_suitability`. This gate is separate from relevancy. It answers whether the exact query can surface the right app type on Google Play and whether it is specific enough for this app's metadata/ads.

Keywords such as `stik bluetooth`, `setting tombol gamepad`, `arcade`, `pizza`, `moonlight`, and `turbospeed` may be feature/category-related but still too weak as standalone acquisition queries. They become `MetadataEligible=False`, `AdsEligible=False`, and `ResearchOnly=True`.

Atomic platform terms such as `nds`, `ds`, `gba`, `snes`, `psp`, `3ds`, `n64`, and `supernds` are kept only when they appear in `metadata_suitability.single_token_policy.keep_terms`. App-specific phrase overrides can be configured in `user_overrides.suitability_keep_terms`.

Audit columns written to the workbook:

- `MetadataEligible`
- `AdsEligible`
- `ResearchOnly`
- `SuitabilityBucket`
- `SuitabilityRule`
- `SuitabilityReason`
- `SuitabilityConfidence`
- `SuitabilitySource`

`01_Main_Keyword_Shortlist` only accepts rows with `MetadataEligible=True`. Rejected rows appear in `14_Not_Selected_Audit` with reasons such as `SINGLE_TOKEN_TOO_BROAD`, `SUITABILITY_RESEARCH_ONLY`, or `SUITABILITY_PENDING_AUDIT`.

If a keyword needs suitability audit but has no cache row, the pipeline fails fast and exports a candidate pool under `.cache/candidate_pools/`. Audit scope includes unlisted single-token terms and multi-word candidates in `Feature Keywords`, `System Keywords`, `Broad Expansion`, `Consider Keywords`, `Style Keywords`, `Generic Style Reserve`, and `Game Keywords`; multi-word terms must meet `metadata_suitability.audit_min_volume` (default `5`).

Use that candidate pool with the suitability helper:

```powershell
python tools/suitability_cache_helper.py find-misses --app NDS_Emulator --csv ".cache/candidate_pools/com.emulator.nds.super.game.console.handheld_US_EN_candidates.csv" --market US_EN
python tools/suitability_cache_helper.py prepare-batches --misses .cache/nds_emulator_us_en_suitability_missing.json
python tools/suitability_cache_helper.py save-results --app NDS_Emulator --batch .cache/suitability_batches/us_en_suitability_batch_1.json --results .cache/suitability_batches/us_en_suitability_batch_1_result.json --market US_EN
python tools/suitability_cache_helper.py verify-cache --app NDS_Emulator --csv ".cache/candidate_pools/com.emulator.nds.super.game.console.handheld_US_EN_candidates.csv" --market US_EN
```

## Setup

Full setup instructions for a new Windows machine:

- [Complete Windows setup checklist](docs/SETUP_WINDOWS.md)

Create a virtual environment and install all Python packages:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Quick check:

```powershell
python -c "import flask, langdetect, numpy, openpyxl, pandas, snowballstemmer; print('Python environment OK')"
```

## English Gloss

The runtime pipeline does not translate keywords over the network. Column `EN` is resolved in this order: existing `EN` column in the CSV, `AIEnglishGloss` from agentic cache, or the original keyword if the keyword is already English.

If a non-English keyword does not have `english_gloss`, the runner fails fast and asks you to warm cache with `tools/warm_cache_helper.py` before running the pipeline.

## Run The Pipeline

Full operating guide: [docs/USAGE.md](docs/USAGE.md). The recommended order is to run `verify-cache`, warm any misses, and only then run the pipeline.

Prefer the central orchestrator:

```powershell
python run_aso_filter.py --csv C:\path\to\ARFilter_US_EN.csv
python run_aso_filter.py --csv C:\path\to\ARFilter_US_EN.csv --interactive
python run_aso_filter.py --csv C:\path\to\US_EN.csv --app Pranky
```

The orchestrator archives CSVs into `apps/<AppName>/Input/<MMYYYY>/`, writes workbooks into `apps/<AppName>/Output/<MMYYYY>/`, adds sheet `00_Project_Memory`, and updates `apps/<AppName>/PROJECT_MEMORY.md`.

## Run The Dashboard

```powershell
python tracker/run_dashboard.py
```

The dashboard opens at `http://127.0.0.1:5100`. The `Setup` tab shows Project Memory for the selected app: identity, positioning, keyword setup, competitor setup, risk/drop policy, overrides, quotas, and warnings.

## Run Batch

Sample manifest:

```json
{
  "jobs": [
    {"app": "Pranky", "csv": "path/to/Pranky_US_EN.csv"},
    {"app": "ARFilter", "csv": "path/to/ARFilter_BR_PT.csv"}
  ]
}
```

```powershell
python run_aso_batch.py --manifest path\to\manifest.json
```

Batch mode defaults to at most `2` locales in parallel to avoid CPU/disk contention on weaker machines.

## Export Master Keywords

```powershell
python export_master_keywords.py --all
```

Results are written under `data/master_keywords/`.

## Tests

```powershell
python -m unittest discover -s tests -v
python -m compileall -q .
```

## Documentation

- [Pipeline spec v4.5](docs/ASO_Keyword_Planner_v4_5.md)
- [Complete Windows setup](docs/SETUP_WINDOWS.md)
- [File guide](docs/README_File_Guide.md)
- [New app template](apps/App_Template/README.md)
