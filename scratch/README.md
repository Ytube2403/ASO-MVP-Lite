# Scratch Scripts

This directory is for one-off experiments only. The official Game Emulator
agentic cache workflow now lives in:

```powershell
python tools/warm_cache_helper.py find-misses ...
python tools/warm_cache_helper.py prepare-batches ...
python tools/warm_cache_helper.py save-results ...
python tools/warm_cache_helper.py verify-cache ...
```

Do not use scratch scripts as the source of truth for cache coverage or pipeline
readiness.

Do not place runnable API clients here. Runtime ASO pipelines are cache-only;
all batch/result/cache operations must go through `tools/warm_cache_helper.py`.
