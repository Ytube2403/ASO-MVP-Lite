# SKILL: ASO Keyword Filter Trigger & Automation

**SKILL_ID:** `aso_keyword_filter_trigger`
**VERSION:** 4.5
**AUTHOR:** AI Assistant
**SCOPE:** Detect trigger requests, resolve the app/market from a CSV filename, and run the ASO keyword filtering pipeline from the ASO-MVP workspace.
**RUNTIME:** Python 3.9+

---

## Trigger Conditions

Use this workflow when the user asks to filter keywords, run the ASO filter, or process an ASO keyword CSV.

Expected input:

- A raw keyword CSV exported from AppTweak, Sensor Tower, or an equivalent source.
- A filename that usually follows:

```text
{AppName}_{Country}_{Language}.csv
```

Examples:

- `ARFilter_US_EN.csv`
- `ControlWidget_BR_PT.csv`
- `GameEmulator_US_EN.csv`
- `PrankSounds_PH_FIL.csv`

If the filename is only a locale such as `US_EN.csv`, pass `--app <RegisteredAlias>` explicitly.

## Workflow For The Agent

When the trigger conditions are met, do these steps in order.

### Step 1. Validate And Prepare The Input

1. Identify the attached or provided CSV file.
2. Parse the filename to extract `AppName` and market code `Country_Language` when possible.
3. Resolve the app through `shared/app_registry.py`. If the app is not registered, fail clearly instead of guessing a folder.
4. Determine the run month in `MMYYYY` format, for example `052026`.
5. Let the orchestrator archive the CSV into the standard folder:

```text
apps/<AppFolder>/Input/<MMYYYY>/
```

The original file is not deleted.

### Step 2. Run The Central Orchestrator

Run the central orchestrator from the repo root:

```powershell
python run_aso_filter.py --csv <CSV_PATH> --app <RegisteredAlias>
```

Default mode is non-interactive/headless.

If the user explicitly wants the interactive web UI for manual adjustments, add `--interactive` or `-i`:

```powershell
python run_aso_filter.py --csv <CSV_PATH> --app <RegisteredAlias> --interactive
```

### Step 3. Report Results To The User

After the script succeeds:

1. Read the output log summary.
2. Present a concise Markdown summary table with:
   - Total raw keywords.
   - Clean keyword count after filtering.
   - Feature and style keyword counts.
   - Output workbook path.
3. Provide a clickable local path to the workbook under the matching app output folder.

Example output paths:

- `apps/AR_Filter/Output/<MMYYYY>/...xlsx`
- `apps/Control_Widget/Output/<MMYYYY>/...xlsx`
- `apps/Game_Emulator/Output/<MMYYYY>/...xlsx`
- `apps/Prank_Sounds/Output/<MMYYYY>/...xlsx`

### Logic Notes For v4.5

The pipeline currently uses shared logic:

- `shared/language_detector.py` provides `detect_keyword_language` and market-policy-aware language grouping.
- `shared/keyword_filter/` provides the precompiled matcher, raw + EN hard filter, classification, validator, audit, and selection/cache metadata. Low-volume keywords (`Volume <= 5`) are not auto-dropped; their `VolumeN` score becomes `0`.
- Truncation logic is hardened: complete tokens and singular/plural terms such as `emoji`, `icon`, `sound`, `filter`, and `widget` are not hard-dropped; prefixes missing anchors go to `possible_truncated_keyword` and Manual Review.
- `shared/text_dedup.py` provides indexed Unicode `NFKC` + `casefold()`, locale-aware stemming, and `MergedVariants` in the main shortlist. Word-order permutations stay separate when `auto_merge_token_bag = False`.
- `shared/en_gloss_resolver.py` resolves `EN` from the CSV or `AIEnglishGloss` already warmed into agentic cache; it does not call a translation network at runtime.
- `shared/profile_service.py` handles custom/generated profile cache and stale fallback.
- `shared/project_memory.py` renders read-only Project Memory from `app_config.py` + `App_Profile.json` into the dashboard Setup tab, workbook sheet `00_Project_Memory`, and `PROJECT_MEMORY.md`.
- `shared/app_registry.py` handles exact app alias routing. Unregistered apps must fail clearly.

Language bucket behavior:

- `FOREIGN` -> `Language Mismatch Audit`.
- `UNKNOWN` -> `Manual Review`.
- `MIXED` -> `Consider Keywords` if the market policy allows mixed language; otherwise `Manual Review`.
- `SECONDARY` -> `Consider Keywords`.

Example for `PH_FIL`: `tunog prank` is valid Filipino/English mixed language and can go to `Consider Keywords`; `sonidos de broma` is foreign and goes to `Language Mismatch Audit`.

### Step 4. Optional Follow-Up Utilities

After the pipeline completes, the agent may suggest:

**Keyword Tracker Dashboard**

```powershell
python tracker\run_dashboard.py
```

**Master Keywords Export**

```powershell
python export_master_keywords.py --all
```

---

## Required Agent Rules

1. Always use the central orchestrator `run_aso_filter.py`; do not manually reproduce each runner step.
2. Keep all operations and generated Excel/JSON files inside the ASO-MVP workspace unless the user explicitly asks otherwise.
3. Do not open the interactive web UI unless the user explicitly asks for it or the command includes `--interactive`.
