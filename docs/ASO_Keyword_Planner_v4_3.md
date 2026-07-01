# ASO Keyword Planner v4.3 Archive

This historical spec has been superseded by `docs/ASO_Keyword_Planner_v4_4.md`.

Active runtime contract:

```text
find-misses -> prepare-batches -> Antigravity subagents -> save-results -> verify-cache -> run_aso_filter
```

App runners are cache-only and do not call AI or translation network providers.
See the v4.4 spec and `tools/warm_cache_helper.py` for the current workflow.
