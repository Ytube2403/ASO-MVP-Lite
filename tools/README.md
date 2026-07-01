# Tools

- `run_aso_batch.py`: execute registered app and locale jobs from a JSON manifest.
- `export_master_keywords.py`: generate clean master keyword workbooks.
- `warm_cache_helper.py`: official Game Emulator agentic cache workflow. Use `find-misses`, `prepare-batches`, `save-results`, and `verify-cache` before running cache-only Game Emulator pipelines.
- `warm_ai_keyword_cache.py`: pre-run DeepSeek AI classification into `.cache/ai_keyword_analysis.sqlite3` without creating workbooks.

The root scripts with the same names remain as compatibility entrypoints.
