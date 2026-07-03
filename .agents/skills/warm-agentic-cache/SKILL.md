---
name: warm-agentic-cache
description: Fill in missing agentic keyword classification cache for a registered app by spawning real subagents, then run the ASO filter pipeline. Use when the user asks to warm the cache, classify keywords, or run the pipeline for an app/market and the pipeline fails with "Agentic keyword classifier is cache-only" / "Agentic English gloss is missing", or when the user explicitly says something like "Hay nap cache bang subagents cho ung dung <AppName> tu file <CSV> cho thi truong <Market>" / "warm the cache for <AppName> <Market>" / "run pipeline for <AppName> <Market>".
---

# Warm Agentic Cache With Real Subagents

`run_pipeline.py` (and every app runner) is **cache-only**: Step 2 (`shared/agentic_keyword_classifier.py::analyze_dataframe`) and Step 2.5 (`shared/en_gloss_resolver.py::resolve_dataframe`) only ever read from the SQLite cache at `.cache/agentic_keyword_analysis.sqlite3`. If a keyword is missing (or missing its English gloss), the runner fails fast with `AIKeywordClassifierError` / `EnglishGlossError` instead of calling any AI itself — a plain Python script cannot spawn a subagent. Only the orchestrator running this skill (Antigravity, Claude Code, or any other multi-agent-capable environment) can do that.

Use this skill to close that gap end-to-end in one request: detect what's missing, spawn real subagents to classify it, save the results, and then run the actual pipeline — instead of the user manually running each `tools/warm_cache_helper.py` subcommand and handing batches to a subagent by hand.

## When to run this

- The user asks to warm/refresh the cache for an app + market.
- The user asks to run the pipeline for an app + market and it is not yet known whether the cache is complete.
- A pipeline run just failed with `Agentic keyword classifier is cache-only...` or `Agentic English gloss is missing...`.

If the user gives an ambiguous app name, resolve it via `shared/app_registry.py` (same resolution `.agents/skills/aso-keyword-research/SKILL.md` uses) rather than guessing a folder path.

## Workflow

### 1. Find what's missing

```powershell
python tools/warm_cache_helper.py find-misses --app <alias> --csv <path-to-csv> --market <MARKET>
```

Read the printed `missing_count` and the JSON file it wrote (default `.cache/<alias>_<market>_missing.json`, or pass `--output` to control the path). If `missing_count` is 0, skip straight to step 5 (verify-cache) and run the pipeline — no subagent needed.

If the app recently bumped top-level `ruleset_version`, expect old rows to stop matching and `missing_count` to jump for every market that uses the new config. That is intentional cache invalidation. Do not delete SQLite just for this; regenerate batches and save new rows under the new context hash.

### 2. Chunk into batches

```powershell
python tools/warm_cache_helper.py prepare-batches --misses <misses-json-from-step-1> --output-dir <dir>
```

Default chunk size is 200 keywords/batch (matches what real runs have used in practice). This prints a `batches[]` list; each entry has `batch_path` and `result_path`. Most real cases are 1-3 batches — don't reach for heavy multi-agent infrastructure for a handful of keywords.

### 3. Spawn one subagent per batch (in parallel when there's more than one)

For each batch, spawn a subagent (use whatever multi-agent tool is available in the current environment) with:
- The `batch_path` to read (JSON shape below).
- The classification rubric in this document (section "Classification rubric").
- An explicit instruction to write its output to the batch's `result_path`, following the result schema exactly, and to output nothing else (no prose, no partial JSON).

**Batch JSON shape** (what the subagent reads, produced by `prepare-batches`):
```json
{
  "app_id": "...", "app_name": "...", "market": "BR_PT", "context_hash": "...",
  "batch_id": "br_pt_batch_1", "batch_index": 1, "total_batches": 2,
  "keywords": [
    {"keyword": "ds emulador", "volume": 25, "rank": "Unranked", "reason": "missing_agentic_cache"}
  ]
}
```
`reason` is either `missing_agentic_cache` (never classified) or `missing_english_gloss` (already classified as non-English, but no gloss was recorded — only `detected_language`/`english_gloss` need to be produced accurately for these, though the full item is still required).

**Result JSON shape** (what the subagent must write to `result_path`):
```json
{
  "batch_id": "br_pt_batch_1",
  "items": [
    {
      "keyword": "ds emulador",
      "detected_language": "pt",
      "language_group": "PRIMARY",
      "semantic_bucket": "Core Intent Final",
      "confidence": 0.9,
      "english_gloss": "DS emulator",
      "decision_rule": "ai_core_intent",
      "reason": "Core intent: DS emulator in Portuguese"
    }
  ]
}
```

Give the subagent the app's `app_config.py` (or resolved effective config) path so it can ground `intent_core_terms`/`feature_terms`/`style_terms`/`market_language_policy` in the app's real identity instead of guessing.

### 4. Save and verify

For each batch:
```powershell
python tools/warm_cache_helper.py save-results --app <alias> --batch <batch_path> --results <result_path> --market <MARKET>
```
This validates the result against the batch (every keyword accounted for exactly once, valid enums, `english_gloss` present for non-English) before writing to SQLite. Notes on how validation/saving behaves:

- `semantic_bucket` and `language_group` are matched **case-insensitively** and legacy `Visual*` labels fold into `Feature Keywords`, so a subagent returning `"core intent final"` or `"PRIMARY"` is accepted and normalized — you don't need to re-spawn just for casing.
- Keywords whose miss `reason` is `missing_english_gloss` are saved **gloss-only**: only `english_gloss` is updated on the existing row, so the previously-cached `semantic_bucket`/`confidence`/`decision_rule` are never clobbered by a fresh guess.
- By default the command still fails fast and reports **all** collected errors at once (not just the first). Add `--partial` to save the valid items anyway and write the still-missing/invalid keywords to `<batch>_remaining.json` (override with `--remaining-output`); then feed that file straight back into `prepare-batches` and re-spawn only the leftover keywords instead of the whole batch.
- Pass `--source <label>` (or set `$AGENTIC_SUBAGENT_SOURCE`) to record which environment produced the rows; it defaults to `antigravity_subagent`.

Then confirm nothing is left:
```powershell
python tools/warm_cache_helper.py verify-cache --app <alias> --csv <path-to-csv> --market <MARKET>
```
Must print `PASS ... 0 missing` (exit code 0) before moving on.

### 5. Run the real pipeline

Only after verify-cache passes, run the app's actual runner (e.g. `python apps/<AppName>/run_pipeline.py --csv <path> --market <MARKET> --output <path>`) as normal.

## Definition of done (self-check before you reply)

Do not finish until every box is true. If any is false, fix it before replying.

- [ ] `find-misses` ran for the exact app + market + CSV requested (not a different scope).
- [ ] Every batch with misses was classified by a **real subagent** — no hand-written, guessed, or rubber-stamped cache rows.
- [ ] `save-results` succeeded for every batch (or `--partial` was used and the remaining keywords were re-spawned until none are left).
- [ ] `verify-cache` prints `PASS ... 0 missing` (exit code 0).
- [ ] Only then was the real pipeline run — never before verify-cache passed.
- [ ] No `context_hash` mismatch was ignored (if one occurred, misses/batches were regenerated).

## Classification rubric

Ground every field in the app's actual identity (`app_config.py`'s `intent_core_terms`/`feature_terms`/`style_terms`/`market_language_policy`/category) — do not classify keywords generically.

### Strict Game Emulator (NDS Emulator) Rubric
Apply these strict rules for Game Emulator apps (e.g., NDS Emulator / SuperNDS) to prevent broad/IP leakages:
1. **Dropped for ALL Game IPs / Franchises / Characters**:
   - Any specific game/franchise/character name (e.g., `mario`, `super mario`, `zelda`, `pokemon`, `pokedex`, `pokemon fire red`, `gta`, `grand theft auto`, `mortal kombat`, `naruto`, `resident evil`, `pac man`, `metal slug`, `sonic`, `crash`, `goku`, `dragon ball`, `metroid`, `kirby`, `fifa`, `pes`, etc.) must be strictly dropped.
   - **`semantic_bucket`**: `Dropped`
   - **`decision_rule`**: `ai_classic_ip` (or `classic_ip_intent` if preserving a legacy label)
2. **Dropped for Competitor Brands / Publishers / Hardware Accessories**:
   - Competitor emulator apps (`vgbanext`, `drastic`, `citra`, etc.), controller brands (`gamesir`), publishers (`rockstar`, `rockstargames`, `2k`, `konami`, `capcom`, etc.), or stores (`google play`) must be dropped.
   - **`semantic_bucket`**: `Dropped`
   - **`decision_rule`**: `ai_competitor` (or `ai_classic_ip` for publisher/game-IP rows)
3. **Core Intent Final**:
   - ONLY when matching core intent terms (e.g., `nds emulator`, `ds emulator`, `nintendo ds emulator`, `nds emulador`, `supernds`, `retro emulator`, etc.).
   - **`decision_rule`**: `ai_core_intent`
4. **Feature Keywords**:
   - ONLY for specific features in `feature_terms` (e.g., `controller skins`, `gamepad skins`, `custom buttons`, `save state`, `cheat codes`, etc.) or specific supported emulator consoles (e.g., `gba emulator`, `snes emulator`, `nds roms`, `ds games`).
   - Never use for generic retro keywords or bare device/retro terms.
   - **`decision_rule`**: `ai_feature`
5. **Broad Expansion**:
   - Genuinely related but generic/bare-category terms, or device attributes that don't state a specific feature (e.g., `emulator`, `emulador`, `games`, `jogos`, `videogame`, bare `gba`/`snes`/`nes`, `gaming emulator`, `retro games`, `games retro`, `gba retro`, `boy gba`, `retro console`, `portable`, `portátil`, `tilt`, `inclinação`, `arcade`).
   - **`decision_rule`**: `ai_broad_expansion`
6. **Style Keywords**:
   - Matching style terms (e.g., `retro`, `nostalgia`, `classic`, `vintage`, `8-bit`, `oldschool`, `childhood`).
   - **`decision_rule`**: `ai_style`
7. **Consider Keywords**:
   - Only for neutral terms that don't fall into the categories above. **Never** use `Consider Keywords` to avoid dropping an IP/competitor keyword.

### Standard Field Rubric
- **`detected_language`**: lowercase ISO code of the keyword's actual language (e.g. `en`, `pt`, `es`, `id`, `hi`). Use `"en"` only when the keyword is genuinely English.
- **`language_group`**: one of `PRIMARY`, `SECONDARY`, `MIXED`, `FOREIGN`, `UNKNOWN`, relative to the app's `market_language_policy` for this market (primary language of the market, its configured secondary languages, and whether the policy allows mixing). A market-primary-language keyword mixed with a common English loanword (e.g. a console/brand/tech term) is `MIXED`, not `FOREIGN` — mixing primary + a loanword is normal search behavior, not a language mismatch.
- **`semantic_bucket`**: exactly one of `Core Intent Final`, `Broad Expansion`, `Feature Keywords`, `Style Keywords`, `Consider Keywords`, `Generic Style Reserve`, `Language Mismatch Audit`, `Manual Review`, `Dropped`. Match the keyword against the app's own `intent_core_terms` (-> Core Intent Final), `feature_terms` (-> Feature Keywords), `style_terms` (-> Style Keywords); genuinely off-topic/competitor/IP content -> `Dropped`; wrong-language content -> `Language Mismatch Audit`; ambiguous/unclear -> `Manual Review`.
- **`confidence`**: 0.0-1.0. Use 0.85-0.95 for a clear, unambiguous match (this is what real prior runs used for clean cases); drop to 0.55-0.75 for genuinely ambiguous keywords. Below the app's configured `min_confidence` (default 0.55), the classifier ignores the cached row's bucket entirely, so don't round up just to make it stick.
- **`english_gloss`**: a short, natural English translation/description a native speaker would write — not a literal word-for-word machine translation. Required whenever `detected_language != "en"`. For already-English keywords, the gloss is typically just the keyword itself.
- **`decision_rule`**: a short snake_case label prefixed `ai_` (e.g. `ai_core_intent`, `ai_feature`, `ai_style`, `ai_broad_expansion`, `ai_lang_mismatch`, `ai_manual_review`, `ai_dropped`, `ai_irrelevant`) — matches the convention already used across every existing cache entry in this project.
- **`reason`**: one short sentence justifying the decision (e.g. `"Core intent: DS emulator in Portuguese"`).

This classification is a supplementary signal, not the final word: `shared/keyword_filter/classifier.py` still runs its own deterministic hard-filter/risk checks first and only falls back to this cached result when nothing else already resolved the keyword. Current guardrails are stricter than the AI cache: core override only rescues declared-safe risky/platform terms when the row also has a functional anchor; `platform_affiliation_terms` are never rescued; `classic_ip_intent`/`ip_intent`/`franchise_intent`/`ai_classic_ip` are treated as classic game IP risk and mapped through `risky_ip_action`. Getting `language_group`/`detected_language`/`english_gloss` right matters most, since those feed the pipeline directly and pervasively; `semantic_bucket` mostly matters for keywords with no other signal.

## Notes

- Never invent or guess-fill cache entries without actually reasoning about each keyword — the whole point of spawning a real subagent per batch is genuine classification, not a rubber stamp.
- Do not run `find-misses --input-dir` / batch an entire app's every market unless the user actually asked for that — scope to the app/market actually requested.
- If `save-results` reports a context_hash mismatch, the app's config/profile changed since `find-misses` ran — redo steps 1-2 for that market before retrying.
