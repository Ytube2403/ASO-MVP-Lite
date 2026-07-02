# Agentic Cache Workflow

Registered app runners use `agentic_keyword_classifier` in cache-only mode. If a
keyword is not already in the SQLite cache, or a non-English keyword lacks
`english_gloss`, the pipeline fails fast and prints sample misses.

## Standard sequence

1. Find uncached keywords for a market:

```powershell
python tools/warm_cache_helper.py find-misses --app Game_Emulator --csv "apps/Game_Emulator/Input/072026/Game Emulator_MX_ES.csv" --market MX_ES --output .cache/game_emulator_mx_es_missing.json
```

2. Prepare Antigravity subagent batches:

```powershell
python tools/warm_cache_helper.py prepare-batches --misses .cache/game_emulator_mx_es_missing.json --output-dir .cache/agentic_batches --chunk-size 200
```

3. Run Antigravity subagents outside the repo. Each subagent receives one batch
JSON and writes the matching `*_result.json` file.

4. Save each result into SQLite:

```powershell
python tools/warm_cache_helper.py save-results --app Game_Emulator --batch .cache/agentic_batches/mx_es_batch_1.json --results .cache/agentic_batches/mx_es_batch_1_result.json
```

5. Verify cache coverage:

```powershell
python tools/warm_cache_helper.py verify-cache --app Game_Emulator --csv "apps/Game_Emulator/Input/072026/Game Emulator_MX_ES.csv" --market MX_ES
```

6. Run the pipeline only after verification passes:

```powershell
python run_aso_filter.py --csv "apps/Game_Emulator/Input/072026/Game Emulator_MX_ES.csv" --app Game_Emulator
```

## Subagent result contract

The result JSON must contain `items[]`. Every item must match exactly one
keyword from the batch and include:

- `keyword`
- `detected_language`
- `language_group`
- `semantic_bucket`
- `decision_rule`
- `reason`
- `confidence`
- `english_gloss`

`english_gloss` is required for every non-English keyword. Invalid buckets,
invalid language groups, duplicate keywords, missing keywords, and keywords that
were not in the batch are rejected before anything is written to cache.
