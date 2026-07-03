---
name: warm-suitability-cache
description: Fill in missing metadata/ads suitability audit for a registered app by spawning real subagents, then run the ASO filter pipeline. Use when the user asks to audit keyword suitability, check ads/store-search specificity, or run the pipeline for an app/market and it fails with "Metadata suitability audit is cache-only", or when the user explicitly says something like "kiem tra suitability cho <AppName> <Market>" / "audit keyword specificity for <AppName> <Market>" / "warm the suitability cache for <AppName> <Market>".
---

# Warm Metadata/Ads Suitability Cache With Real Subagents

`shared/keyword_filter/suitability.py::apply_metadata_suitability` is **cache-only** for
any keyword that `needs_suitability_audit` flags: a keyword the AI semantic classifier
(not the app's own hand-declared `feature_terms`/`intent_core_terms`) bucketed as
`Feature Keywords`/`System Keywords` with real search volume. If such a keyword has no
row in the `keyword_suitability_analysis` table, the pipeline **fails fast** with
`SuitabilityAuditError` instead of guessing — exactly like the agentic keyword
classifier's cache-only design (see `.agents/skills/warm-agentic-cache/SKILL.md`). A
plain Python script cannot spawn a subagent; only the orchestrator running this skill
(Antigravity, Claude Code, or any other multi-agent-capable environment) can.

## Why this gate exists

An AI-inferred Feature Keyword can still be a **broad head term**: high search volume,
genuinely related to the app's category, but too generic to surface *this specific app*
on the store or to convert efficiently as an ad keyword (e.g. "gba retro games", "game
boy advance", "joypad", "turbospeed" — related to a GBA emulator, but someone searching
these won't necessarily find or want this particular app, and ad spend against them is
inefficient). A keyword the app owner explicitly declared in `feature_terms` (e.g. "gba
emulator", "nds roms") is already vetted by construction and never needs this audit —
only the AI's own inferred Feature/System calls do.

Use this skill to close that gap end-to-end in one request: detect what's missing,
spawn real subagents to judge specificity, save the results, and then run the actual
pipeline — instead of the user manually running each `tools/suitability_cache_helper.py`
subcommand and handing batches to a subagent by hand.

## When to run this

- The user asks to audit/refresh keyword suitability for an app + market.
- The user asks to run the pipeline for an app + market and it is not yet known whether
  the suitability cache is complete.
- A pipeline run just failed with `Metadata suitability audit is cache-only...`.

If the user gives an ambiguous app name, resolve it via `shared/app_registry.py` (same
resolution `.agents/skills/aso-keyword-research/SKILL.md` uses) rather than guessing a
folder path.

## Workflow

### 1. Find what's missing

```powershell
python tools/suitability_cache_helper.py find-misses --app <alias> --csv <path-to-csv> --market <MARKET>
```

Read the printed `missing_count` and the JSON file it wrote (default
`.cache/<alias>_<market>_suitability_missing.json`, or pass `--output`). The CSV here is
the **candidate pool CSV** (post-classification, with `Keyword`/`Bucket`/`Volume`
columns) — not the raw AppTweak export. If `missing_count` is 0, skip straight to step 5
(verify-cache) and run the pipeline — no subagent needed.

### 2. Chunk into batches

```powershell
python tools/suitability_cache_helper.py prepare-batches --misses <misses-json-from-step-1> --output-dir <dir>
```

Default chunk size is 200 keywords/batch. Prints a `batches[]` list; each entry has
`batch_path` and `result_path`.

### 3. Spawn one subagent per batch (in parallel when there's more than one)

For each batch, spawn a subagent with:
- The `batch_path` to read (JSON shape below).
- The rubric in this document (section "Suitability rubric").
- The app's `app_config.py` (or resolved effective config) path so the subagent grounds
  its judgment in the app's real identity/category instead of guessing.
- An explicit instruction to write its output to the batch's `result_path`, following the
  result schema exactly, and to output nothing else (no prose, no partial JSON).

**Batch JSON shape** (what the subagent reads, produced by `prepare-batches`):
```json
{
  "app_id": "...", "app_name": "...", "market": "BR_PT", "context_hash": "...",
  "batch_id": "br_pt_suitability_batch_1", "batch_index": 1, "total_batches": 1,
  "keywords": [
    {"keyword": "gba retro games", "volume": 46, "bucket": "Feature Keywords", "decision_rule": "ai_feature", "reason": "missing_suitability_cache"}
  ]
}
```

**Result JSON shape** (what the subagent must write to `result_path`):
```json
{
  "batch_id": "br_pt_suitability_batch_1",
  "items": [
    {
      "keyword": "gba retro games",
      "metadata_eligible": false,
      "ads_eligible": false,
      "research_only": true,
      "suitability_bucket": "Research Only",
      "decision_rule": "ai_broad_head_term",
      "reason": "Generic GBA + retro games phrase; no app-specific anchor, low store/ads conversion intent",
      "confidence": 0.85
    }
  ]
}
```

### 4. Save and verify

For each batch:
```powershell
python tools/suitability_cache_helper.py save-results --app <alias> --batch <batch_path> --results <result_path> --market <MARKET>
```
This validates the result against the batch (every keyword accounted for exactly once,
booleans well-formed, `metadata_eligible`/`research_only` not both true, confidence in
[0,1]) before writing to SQLite.

Then confirm nothing is left:
```powershell
python tools/suitability_cache_helper.py verify-cache --app <alias> --csv <path-to-csv> --market <MARKET>
```
Must print `PASS ... 0 missing suitability` (exit code 0) before moving on.

### 5. Run the real pipeline

Only after verify-cache passes, run the app's actual runner (e.g.
`python apps/<AppName>/run_pipeline.py --csv <path> --market <MARKET> --output <path>`)
as normal.

## Definition of done (self-check before you reply)

Do not finish until every box is true. If any is false, fix it before replying.

- [ ] `find-misses` ran for the exact app + market + candidate CSV requested.
- [ ] Every batch with misses was judged by a **real subagent** — no hand-written,
      guessed, or rubber-stamped cache rows.
- [ ] `save-results` succeeded for every batch.
- [ ] `verify-cache` prints `PASS ... 0 missing suitability` (exit code 0).
- [ ] Only then was the real pipeline run — never before verify-cache passed.
- [ ] No `context_hash` mismatch was ignored (if one occurred, misses/batches were
      regenerated for the current app config/market).

## Suitability rubric

Ground every judgment in the app's actual identity (category, `intent_core_terms`,
`feature_terms`, market) and in the question: **"if someone searches this exact phrase
on the store, or an ad targets this exact phrase, does it surface/convert on THIS
app specifically — or any app in the category?"**

- **`metadata_eligible` / `ads_eligible`**: `true` when the phrase is specific enough
  that ranking on it plausibly drives installs of *this* app (names a concrete feature,
  console, or the app's own core intent). `false` for a broad head term: generic
  category words, bare hardware names without a functional anchor, vague marketing
  words ("advance", "lite", "pro" alone next to a hardware name), or anything that reads
  like it belongs to the whole app category rather than this app.
- **`research_only`**: the inverse of eligible — `true` exactly when both eligible flags
  are `false`. Never set both `metadata_eligible`/`research_only` true (validation
  rejects it).
- **`suitability_bucket`**: `"Eligible"` or `"Research Only"` (match the booleans).
- **`decision_rule`**: short snake_case, e.g. `ai_specific_feature`, `ai_broad_head_term`,
  `ai_generic_category_term`.
- **`reason`**: one short sentence justifying the call, naming what makes it specific or
  generic.
- **`confidence`**: 0.0-1.0; use 0.8-0.95 for a clear case, 0.55-0.7 for genuinely
  borderline phrases.

### Examples (NDS_Emulator, an NDS/GBA/SNES/N64/PSP all-in-one emulator app)

| Keyword | Verdict | Why |
|---|---|---|
| `gba emulator`, `nds roms`, `dual screen emulator` | (never reaches subagent — declared in `feature_terms`, already trusted) | — |
| `gba retro games`, `game boy advance`, `joypad`, `turbospeed`, `gb advance` | Research Only | Generic hardware/category phrasing with no distinguishing feature; describes the whole GBA-emulator category, not this app |
| `nds emulator with save states`, `supernds controller skins` | Eligible | Names a concrete, declared feature alongside the app's core identity |

## Notes

- Never invent or guess-fill cache entries without actually reasoning about each
  keyword — the whole point of spawning a real subagent per batch is genuine judgment,
  not a rubber stamp.
- Do not run `find-misses --input-dir` / batch an entire app's every market unless the
  user actually asked for that — scope to the app/market actually requested.
- If `save-results` reports a context_hash mismatch, the app's config/profile changed
  since `find-misses` ran — redo steps 1-2 for that market before retrying.
- This is a **separate cache/table** (`keyword_suitability_analysis`) from the agentic
  semantic classifier's cache (`ai_keyword_analysis`) — warming one does not warm the
  other. Run `.agents/skills/warm-agentic-cache/SKILL.md` first if the pipeline is also
  failing with the semantic classifier's cache-only error.
