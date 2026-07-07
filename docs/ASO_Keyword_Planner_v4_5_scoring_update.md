# ASO Keyword Planner v4.5 - Scoring & Tooling Update

`FILTER_LOGIC_VERSION = v4.5_logreach_rubric_relevancy`

This update is folded into release 4.5. It focuses on scoring (Volume, Relevancy, BalancedScore), leaner workbook output, orchestration skills, and new risk/cache guardrails. Selection cache is refreshed because scoring logic changed. AI classification cache (`agentic_keyword_analysis.sqlite3`) only needs re-warm when app config bumps `ruleset_version`; brand/risk lists remain deterministic filters and take effect on every run.

## 1. Scoring Highlights

### VolumeN: Log Normalization On Real Reach

Reach grows exponentially with Volume. Empirical measurement on 15.7k keywords showed `Reach ~= exp(0.15 * Volume)`, R2 ~= 0.72. The old linear normalization (`reach/ceiling`) compressed more than 95% of keywords toward 0.

- New: `VolumeN = log1p(reach) / log1p(reach_reference)` with default `reach_reference = 100000` configured in `volume_score_policy`.
- `mode: "reach_linear"` restores the old behavior.
- `reach_reference: 0` uses the dataset-derived ceiling.
- The old `-0.15` low-volume penalty was removed. Log scaling already dampens low volume; `low_tier_score_cap` remains the only low-tier noise floor.

### BalancedScore: Remove KEIN

KEI is collinear with Volume and Difficulty, so it was removed and weight shifted toward Relevancy.

- New weights: VolumeN `0.35`, DifficultyN `0.15`, RelevancyScore `0.30`, CurrentRankN `0.10`, ExpansionValue `0.10`; total `1.0`.
- `resolve_balanced_weights()` automatically migrates old config with `KEIN > 0` to the new scheme. Configs without KEIN are respected and remain per-app tunable.

### RelevancyScore: Rubric Scale From AI Classification

Relevancy now prioritizes a deterministic rubric derived from AI cache rather than subjective floats:

```text
base(AISemanticBucket) - (1 - AIConfidence) * 0.15 + language_adjust   (clamp 0..1)
Core 0.90 | Feature 0.70 | Broad 0.55 | Consider/Style 0.45 | ...
language: PRIMARY 0 | SECONDARY -0.05 | MIXED -0.05 | UNKNOWN -0.10 | FOREIGN -> 0
```

- `RelevancyScore = max(lexical, rubric)`: rubric is primary for AI-classified keywords.
- Lexical scoring is still required for keywords that do not go through AI, such as English/deterministic rows with empty `AISemanticBucket`, and for `CompetitorBoost`.
- Scores such as `0.90` versus `0.85` now trace back to clear criteria (language/confidence) instead of subjective judgment. Changing weights/base scores does not require subagent re-warm.

## 2. Output Workbook: Lean/Full Modes

Implemented through `shared/report_builder.py` and config `output_mode`.

- `lean` (default): keeps operational sheets such as README, Project Memory, Main Shortlist, curated sheets, Report Summary, and All Candidates. Audit/derived sheets 04 and 07-15 are omitted because they are filtered/sorted views of `06_All_Candidates`.
- `full`: exports the complete workbook as before.
- Per-app overrides: `report_output.keep_extra` / `report_output.drop_extra`.

## 3. Warm-Cache Tooling (`tools/warm_cache_helper.py`)

- `save-results`: gloss-only fills do not overwrite good classifications; casing and aliases are normalized for `semantic_bucket` and `language_group`.
- Validation aggregates all errors instead of stopping at the first error.
- `--partial` saves valid rows and writes `<batch>_remaining.json` for re-spawning invalid rows.
- `--source` or `$AGENTIC_SUBAGENT_SOURCE` records source metadata.
- `AIKeywordClassifier._update_english_gloss()` supports targeted gloss patching.
- `ruleset_version`: top-level app config key used to invalidate semantic cache when the agentic prompt/rubric changes. Risk/brand lists are not part of the context hash because `classifier.py` hard-filters them on every run.

## 4. Risk Guardrails

- `classifier.py` allows core override for risky/platform terms only when the term is declared safe in core/feature vocabulary and the keyword has a separate functional anchor. Generic tokens such as `game`, `games`, `play`, `app`, and `free` cannot rescue a brand term.
- `platform_affiliation_terms` has no core override. Official/affiliation/brand-claim phrases still follow `platform_affiliation_action`.
- AI-recognized classic game IP can use `AIDecisionRule` values such as `classic_ip_intent`, `ip_intent`, `franchise_intent`, or `ai_classic_ip`. Without a valid override, the classifier applies `risky_ip_action` and writes rule `ai_classic_ip`.

## 5. Orchestration Skills (`.agents/skills/`)

- `run-pipeline-aso`: runs the pipeline end to end: resolve app -> preflight profile/config -> warm cache with subagents -> verify -> filter -> report.
- `create-profile`: creates schema-correct `App_Profile.json` 2.0 and validates it with `build_project_memory_for_app`.
- `warm-agentic-cache`, `aso-keyword-research`: add Execution Contract (MUST/NEVER) and Definition of Done sections for stronger compliance.

## 6. Tests

- New or expanded: `tests/test_scoring_upgrades.py` for log-reach, `resolve_balanced_weights`, and rubric behavior; `tests/test_report_builder.py`; `tests/test_warm_cache_helper.py`.
- `tests/test_volume_score.py` updated to log-reach semantics.

## Migration Notes

- Apps with very different reach scale should tune `reach_reference` in `volume_score_policy`.
- Old selection cache is recalculated because `FILTER_LOGIC_VERSION` changed; this is expected and desired.
- Old agentic cache remains usable when `ruleset_version` does not change. When `ruleset_version` is bumped, rerun `warm_cache_helper` for markets that need a pipeline run. Old rows are not deleted; they simply no longer match the new context hash.
- Old dead runner code such as `apply_volume_penalty` has been removed. The remaining optional future work is rubric v2 (`positioning_fit` / `specificity` from subagent) if deeper scoring is needed later.
