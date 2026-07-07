# ASO App Workspace - FunVid

This folder contains ASO configuration, app profile, and the keyword filtering runner for FunVid keyword sets, including the `FunVid_100_Keywords` and `FunVid_AnimalFace` aliases.

## Folder Structure

```text
apps/FunVid/
|-- README.md
|-- app_config.py
|-- App_Profile.json
|-- PROJECT_MEMORY.md
|-- run_pipeline.py
|-- Input/
`-- Output/
```

## Configure FunVid

Edit `app_config.py` when needed:

- `intent_core_terms`: core search intent for funny face filters, video effects, camera filters, and related short-video creation flows.
- `feature_terms`: concrete features such as animal face filters, funny effects, camera effects, stickers, and video editing helpers.
- `style_terms`: style/theme terms allocated carefully to descriptive fields.
- `competitor_brands`, `noise_terms`, `typo_blacklist`: deterministic filters for competitor, generic, and noisy queries.

`App_Profile.json` stores live metadata and competitor context for scoring and Project Memory.

## Run The Pipeline

Use the current operating flow in `../../docs/USAGE.md`: verify cache first, warm misses if any, then run the pipeline. If the agentic prompt/rubric changes and `ruleset_version` is bumped, warm every market you plan to run.

From `ASO-MVP-Lite/apps/FunVid`:

```powershell
python run_pipeline.py --csv C:\path\to\FunVid_US_EN.csv --market US_EN
python run_pipeline.py --csv C:\path\to\FunVid_US_EN.csv --market US_EN --interactive
```

From the repo root:

```powershell
python apps\FunVid\run_pipeline.py --csv C:\path\to\FunVid_US_EN.csv --market US_EN
```

The workbook includes the full report, `target 40 utility + diversity` shortlist, `13_Top_By_Volume`, `00_Project_Memory`, and audit reasons for each keyword. The pipeline updates `PROJECT_MEMORY.md` for handoff and setup audit.

## Shared Platform Logic v4.5

FunVid uses the shared ASO engine:

- Cache-only agentic classification and English gloss resolution.
- Shared language policy grouping.
- Shared risk/filter/classifier/scoring modules.
- Shared metadata/ads suitability gate.
- Shared main shortlist builder with utility + diversity.

Batch command:

```powershell
python ..\..\run_aso_batch.py --manifest path\to\manifest.json --max-workers 3
```
