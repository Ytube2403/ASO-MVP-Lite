---
name: warm-suitability-cache
description: Warm the metadata and ads suitability cache for a registered ASO app by finding post-classification candidates that need store-search/acquisition suitability audit, spawning real subagents, saving validated results, verifying zero missing suitability entries, and then rerunning the ASO pipeline. Use when the pipeline fails with "Metadata suitability audit is cache-only", when the user asks to audit keyword suitability, store-search fit, or ads suitability, or when running an app/market pipeline may need suitability cache coverage.
---

# Warm Metadata/Ads Suitability Cache

Use this skill after semantic classification has already run. The suitability gate answers two questions:

1. If a user searches this exact keyword on Google Play, is it likely to surface the right type of app for this project?
2. If the store or an ad surfaces this app for that query, is the phrase specific enough to plausibly convert for THIS app, or is it only broad research/category traffic?

Both questions matter. A keyword can describe a real app feature but still fail Play Store acquisition intent; that is `Research Only`, not `Eligible`. A keyword can also be broad, but still suitable when users plausibly search it to find this app category.

`shared/keyword_filter/suitability.py::apply_metadata_suitability` is cache-only for candidates that `needs_suitability_audit` flags. If a flagged keyword has no row in the `keyword_suitability_analysis` SQLite table, the pipeline raises `SuitabilityAuditError` and exports a post-classification candidate pool CSV under `.cache/candidate_pools/`.

Do not guess suitability rows. Warm the cache with real subagents, save only validated JSON, and rerun the pipeline only after `verify-cache` passes.

## What Gets Audited

The helper scans a post-classification candidate CSV, not a raw AppTweak export. A keyword needs suitability audit when all of these are true:

- It is not already blocked by risk, language mismatch, manual review, naturalness, or hard-filter gates.
- It is either:
  - a single-token keyword that is not in single-token keep/block terms, or
  - a multi-word keyword in one of these buckets: `Feature Keywords`, `System Keywords`, `Broad Expansion`, `Consider Keywords`, `Style Keywords`, `Generic Style Reserve`, `Game Keywords`.
- For multi-word keywords, it meets `metadata_suitability.audit_min_volume` (default currently `5`). Single-token keywords are audited regardless of volume unless they are in single-token keep/block terms.
- It was AI-inferred (`DecisionRule` or `AIDecisionRule` starts with `ai_`), or it landed in a non-feature/core bucket such as `Broad Expansion`, `Consider Keywords`, `Style Keywords`, `Generic Style Reserve`, or `Game Keywords`.

Explicit app-owned feature/core terms usually skip the subagent audit when they land deterministically in `Feature Keywords`, `System Keywords`, or `Core Intent Final`. User suitability keep terms also bypass audit.

Important: `Consider Keywords` are in scope. If a candidate does not search toward the right app type, mark it `Research Only`. If it is only an in-app feature query with weak Play Store acquisition intent, also mark it `Research Only`. Do not make feature-only terms eligible just because the app supports that feature.

## Workflow

### 1. Find misses

Use the candidate pool CSV produced after classification/scoring. It should include at least `Keyword`, `Bucket`, `Volume`, and `DecisionRule` or `AIDecisionRule`; `EN`, `Reason`, and `LanguageGroup` are helpful grounding fields when present.

```powershell
python tools/suitability_cache_helper.py find-misses --app <alias> --csv <candidate-pool-csv> --market <MARKET>
```

Read the printed `missing_count` and the JSON path. The default output is `.cache/<alias>_<market>_suitability_missing.json`. If `missing_count` is `0`, run `verify-cache` and then rerun the pipeline.

### 2. Prepare batches

```powershell
python tools/suitability_cache_helper.py prepare-batches --misses <misses-json> --output-dir .cache/suitability_batches
```

Default chunk size is 200 keywords per batch. Record every `batch_path` and `result_path` from the printed `batches[]` recipe.

### 3. Spawn subagents

Spawn one real subagent per batch, in parallel when there is more than one. Give each subagent:

- The exact `batch_path`.
- The app's effective config or `app_config.py` path.
- The rubric below.
- An instruction to write only valid JSON to the provided `result_path`.

Batch JSON shape:

```json
{
  "app_id": "...",
  "app_name": "...",
  "market": "MARKET",
  "context_hash": "...",
  "batch_id": "market_suitability_batch_1",
  "batch_index": 1,
  "total_batches": 1,
  "keywords": [
    {
      "keyword": "drop 4",
      "volume": 14,
      "bucket": "Consider Keywords",
      "decision_rule": "ai_broad_expansion",
      "reason": "missing_suitability_cache"
    }
  ]
}
```

Result JSON shape:

```json
{
  "batch_id": "market_suitability_batch_1",
  "items": [
    {
      "keyword": "drop 4",
      "metadata_eligible": false,
      "ads_eligible": false,
      "research_only": true,
      "suitability_bucket": "Research Only",
      "decision_rule": "ai_off_core_query",
      "reason": "Unrelated phrase with no current app category, feature, or acquisition anchor.",
      "confidence": 0.9
    }
  ]
}
```

### 4. Save results

For every batch:

```powershell
python tools/suitability_cache_helper.py save-results --app <alias> --batch <batch_path> --results <result_path> --market <MARKET>
```

The helper validates that every expected keyword appears exactly once, booleans are parseable, `metadata_eligible` and `research_only` do not conflict, required fields are present, and confidence is between 0 and 1. If it reports a `context_hash` mismatch, regenerate misses and batches before retrying.

### 5. Verify cache

```powershell
python tools/suitability_cache_helper.py verify-cache --app <alias> --csv <candidate-pool-csv> --market <MARKET>
```

This must print `PASS <MARKET>: 0 missing suitability` and exit 0 before rerunning the pipeline.

### 6. Rerun pipeline

Run the app runner or master orchestrator only after verification passes. If the rerun exports a new candidate pool and fails again, repeat this skill for the new pool.

## Suitability Rubric

Ground every judgment in the current app, not in any example app. Before judging a batch, build an app-specific acquisition brief from the effective config, profile, market, and candidate rows.

### Build App-Specific Acquisition Brief

For the current app, identify:

- `right_app_type`: the app category or job a Play Store user should be trying to find.
- `core_acquisition_queries`: direct app/category queries likely to surface the right app type.
- `category_acquisition_queries`: broader category, platform, content, or use-case queries that can still surface the right app type and plausibly convert.
- `eligible_feature_anchors`: feature terms that users actually search as acquisition terms for this app, especially when combined with a core/category anchor.
- `feature_only_research_terms`: real app features that are poor Play Store acquisition terms unless paired with a core/category anchor.
- `wrong_app_type_queries`: unrelated products, apps, games, utilities, media, brands, or categories.

Use `app_name`, `category`, `intent_core_terms`, `feature_terms`, `style_terms`, `market_language_policy`, `App_Profile.json`, competitor metadata, candidate `Bucket`, `EN`, `Reason`, and the exact keyword text. Do not copy another app's examples or category rules. SuperNDS/emulator examples apply only to emulator apps whose own config/profile supports that identity.

### Decision Tree

1. App-type fit: Would this exact query likely surface the current app's `right_app_type` on Google Play?
   - If no, return `Research Only` with a rule such as `ai_wrong_app_type`, `ai_off_core_query`, or `ai_unrelated_app`.
2. Acquisition suitability: If the query can surface the right app type, is it specific enough to use in this app's metadata or ads?
   - Feature support alone is not enough. A phrase can describe a real in-app feature and still be weak acquisition traffic.
   - Broad category traffic can be enough when users plausibly search that phrase to find this app category and the app can compete for the query.
   - If yes, return `Eligible`.
   - If no, return `Research Only` with a rule such as `ai_feature_only_low_acquisition`, `ai_broad_head_term`, `ai_generic_category_term`, or `ai_weak_app_anchor`.

Return `Eligible` only when both questions pass:

- The query points to the current app's right app type on Google Play.
- It names this app's core acquisition intent.
- It names a supported category, platform, content type, use case, or user job that users plausibly search to find apps like this one.
- It names a concrete supported feature only when that feature is itself an acquisition term or the query also contains a core/category anchor.
- Or it combines a broad term with an app-specific anchor strong enough to make the search intent clear.

Return `Research Only` when either question fails:

- Wrong app type: off-core, unrelated utility, unrelated product/media/sport/tool, unrelated game-title query, or different app category.
- Real feature but weak acquisition: feature-only terms that describe something the app supports but are unlikely to make users discover this app on Play Store.
- Right app type but too broad or weak: vague category terms without enough app/category acquisition intent for the current app.
- Generic hardware, setting, action, UI, or modifier phrases that are unlikely to surface this app type.
- Broad style terms unless tied to the current app's core/category intent.
- Vague marketing modifiers such as `advanced`, `pro`, `lite`, or `free` without a concrete app-specific anchor.
- Any keyword whose semantic classification says `off-core`, `non-gaming`, `unrelated`, `utility`, `different category`, or equivalent.

Field rules:

- `metadata_eligible` and `ads_eligible`: `true` only for `Eligible` phrases.
- `research_only`: `true` exactly when both eligibility flags are `false`.
- `suitability_bucket`: use `Eligible` or `Research Only`.
- `decision_rule`: short snake_case, for example `ai_specific_feature`, `ai_specific_core_intent`, `ai_supported_category_intent`, `ai_feature_only_low_acquisition`, `ai_broad_head_term`, `ai_generic_category_term`, `ai_weak_app_anchor`, `ai_wrong_app_type`, `ai_off_core_query`, `ai_unrelated_app`.
- `reason`: one short sentence naming the concrete anchor, or naming whether the failure is wrong app type versus right app type but too broad.
- `confidence`: 0.8 to 0.95 for clear cases; 0.55 to 0.7 for genuinely borderline cases.

Generic examples:

| Keyword pattern | Verdict | Why |
|---|---|---|
| `<core app category>`, `<category + core action>`, `<brand-neutral app type query>` | Eligible | Directly searches for the current app's right app type. |
| `<supported platform/content/use-case that users search to find this app type>` | Eligible | Broader than the app name, but still plausible Play Store acquisition traffic for this app. |
| `<specific feature + core/category anchor>` | Eligible | Feature is connected to an acquisition query for this app type. |
| `<feature-only setting/action/hardware term>` | Research Only | May be a real feature, but weak store-search or ads acquisition traffic by itself. |
| `<unrelated product/app/media/game/tool>` | Research Only | Wrong app type or off-core query. |
| `<generic modifier only>` | Research Only | Too broad without a concrete app-specific anchor. |

Example only: SuperNDS / NDS Emulator. Derive equivalent examples per app; do not reuse these rules for non-emulator apps.

| Keyword | Verdict | Why |
|---|---|---|
| `nds emulator`, `emulator semua konsol`, `nds emulator with save states` | Eligible | Core emulator intent or core intent plus concrete feature. |
| `gba retro games`, `game boy advance`, `gba emulator retro game`, `nds 64 emulator retro` | Eligible | Console/category acquisition terms that can plausibly surface emulator apps on Play Store. |
| `dual screen emulator`, `nds emulator with save states`, `controller skin emulator` | Eligible | Feature terms with a clear emulator/core anchor. |
| `stik bluetooth`, `setting tombol gamepad`, `game controller`, `simpan permainan`, `joypad`, `turbospeed` | Research Only | Real or related feature/category terms, but weak Play Store acquisition intent without an emulator/ROM/retro-console anchor. |
| `drop 4`, `fs advanced`, `and pies`, `mma manager`, `roll spike`, `yoto player` | Research Only | Wrong app type or unrelated query; should not be metadata or ads eligible. |

## Definition Of Done

- `find-misses` ran against the exact app, market, and candidate pool CSV.
- Every missing batch was judged by a real subagent.
- `save-results` succeeded for every batch.
- `verify-cache` printed `PASS <MARKET>: 0 missing suitability`.
- The pipeline was rerun only after verification passed.
- Scope stayed on the requested app/market only.

## Guardrails

- Never hand-write or guess-fill suitability rows.
- Never use the raw AppTweak CSV for `find-misses`; use the post-classification candidate pool CSV.
- Never ignore `context_hash` mismatch.
- Do not batch every app or market unless the user explicitly asks for that scope.
- Remember that semantic cache and suitability cache are separate tables. If semantic classification/gloss cache is missing, warm `warm-agentic-cache` first.
