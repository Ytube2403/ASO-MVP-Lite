import math
import re

from .matcher import has_any_term, normalize_filter_text, tokenize


DEFAULT_VOLUME_SCORE_POLICY = {
    # Reach grows exponentially with AppTweak Volume (empirically Reach ~ exp(0.15*Volume),
    # i.e. Volume is ~log(Reach); measured R^2=0.72 over 15.7k keywords). Scoring real reach
    # linearly (reach/ceiling) crushes >95% of keywords to ~0 -- only a few mega-terms score.
    # "log_reach" (default) normalizes log1p(reach) so mid-tier keywords keep a meaningful
    # score. "reach_linear" restores the old behavior.
    "mode": "log_reach",
    # Fixed anchor for log-reach normalization so scores are comparable across runs/months.
    # A keyword whose reach reaches this value scores ~1.0. Tune per app/market. When 0, falls
    # back to the dataset's reach ceiling (comparable within a run only).
    "reach_reference": 100000.0,
    "search_popularity_floor": 5.0,
    "search_popularity_ceiling": 100.0,
    "exponential_curve_factor": 4.0,
    "current_volume_weight": 0.85,
    "historical_max_volume_weight": 0.15,
    "low_tier_threshold": 5.0,
    "low_tier_score_cap": 0.05,
    "exclude_low_tier_from_metadata_shortlist": False,
    "max_low_tier_consider_keywords": 999,
}

QUERY_PATTERNS = [
    r"\bwhat\s+is\b",
    r"\bhow\s+to\b",
    r"\bwhy\s+do\b",
    r"\bwhen\s+is\b",
    r"\bwhere\s+is\b",
]


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def volume_score_policy(config=None):
    policy = dict(DEFAULT_VOLUME_SCORE_POLICY)
    policy.update((config or {}).get("volume_score_policy", {}) or {})
    return policy


def _normalize_search_popularity(value, policy):
    floor = number(policy.get("search_popularity_floor"), 5.0)
    ceiling = max(floor + 1.0, number(policy.get("search_popularity_ceiling"), 100.0))
    curve_factor = number(policy.get("exponential_curve_factor"), 4.0)
    popularity = min(ceiling, max(floor, number(value)))
    if popularity <= floor:
        return 0.0
    ratio = (popularity - floor) / (ceiling - floor)
    if curve_factor <= 0:
        return ratio
    return math.expm1(curve_factor * ratio) / math.expm1(curve_factor)


def calculate_volume_score(volume, max_volume=None, maximum_reach=0, max_maximum_reach=0, config=None):
    """Score AppTweak volume, preferring real reach when the CSV provides it."""
    policy = volume_score_policy(config)
    current_volume = number(volume)
    historical_volume = max(current_volume, number(max_volume, current_volume))
    reach = max(0.0, number(maximum_reach))
    reach_ceiling = max(0.0, number(max_maximum_reach))
    reach_reference = number(policy.get("reach_reference"), 0.0)
    reference = reach_reference if reach_reference > 0 else reach_ceiling
    if reach > 0 and reference > 0:
        if str(policy.get("mode", "log_reach")).strip().lower() == "reach_linear":
            score = reach / reference
        else:
            # log-reach: log1p compresses the exponential reach distribution so mid-tier
            # keywords are ranked meaningfully instead of collapsing to ~0.
            score = math.log1p(min(reach, reference)) / math.log1p(reference)
    else:
        current_score = _normalize_search_popularity(current_volume, policy)
        historical_score = _normalize_search_popularity(historical_volume, policy)
        current_weight = max(0.0, number(policy.get("current_volume_weight"), 0.85))
        historical_weight = max(0.0, number(policy.get("historical_max_volume_weight"), 0.15))
        total_weight = current_weight + historical_weight
        score = current_score if total_weight <= 0 else ((current_weight * current_score) + (historical_weight * historical_score)) / total_weight
    if current_volume <= number(policy.get("low_tier_threshold"), 5.0):
        score = min(score, number(policy.get("low_tier_score_cap"), 0.05))
    return max(0.0, min(1.0, score))


def is_low_volume_tier(row, config=None):
    volume = row.get("Volume", 0) if hasattr(row, "get") else row
    return number(volume) <= number(volume_score_policy(config).get("low_tier_threshold"), 5.0)


def is_shortlist_volume_eligible(row, section, selected_low_tier_count=0, config=None):
    policy = volume_score_policy(config)
    if not is_low_volume_tier(row, config):
        return True
    if section in {"Core Intent Final", "Broad Expansion"}:
        return not bool(policy.get("exclude_low_tier_from_metadata_shortlist", False))
    if section == "Consider Keywords":
        return selected_low_tier_count < int(number(policy.get("max_low_tier_consider_keywords"), 999))
    return True


DEFAULT_REACH_CEILING_POLICY = {
    "percentile": 0.95,
}


def reach_ceiling_policy(config=None):
    policy = dict(DEFAULT_REACH_CEILING_POLICY)
    policy.update((config or {}).get("reach_ceiling_policy", {}) or {})
    return policy


def safe_reach_ceiling(df, config=None):
    """Reach ceiling for volume/utility normalization, robust to outlier brand terms.

    A single competitor/irrelevant keyword can have a MaximumReach orders of
    magnitude above every legitimate candidate (e.g. a blocked competitor-brand
    term). Using that as the normalization denominator crushes VolumeN/reach
    signal to ~0 for every real keyword, making search volume invisible to
    scoring. Excluding competitor/irrelevant rows and using a percentile
    (default p95) instead of the raw max keeps the ceiling representative of
    the actual candidate pool.
    """
    if df is None or len(df) == 0 or "MaximumReach" not in df.columns:
        return 0.0
    pool = df
    if "is_competitor" in df.columns and "is_irrelevant" in df.columns:
        safe_mask = ~df["is_competitor"].astype(bool) & ~df["is_irrelevant"].astype(bool)
        if safe_mask.any():
            pool = df.loc[safe_mask]
    values = pool["MaximumReach"].apply(number)
    if len(values) == 0 or values.max() <= 0:
        values = df["MaximumReach"].apply(number)
    if len(values) == 0:
        return 0.0
    percentile = number(reach_ceiling_policy(config).get("percentile"), 0.95)
    return max(float(values.quantile(percentile)), 1.0)


DEFAULT_RELEVANCY_STACKING_POLICY = {
    "enabled": True,
    "min_category_hits": 2,
    "max_volume": 10.0,
    # NOTE: MaximumReach is typically a raw AppTweak reach count (0, 14, 172, ...), not a
    # 0-1 score. A threshold of 0.0 only exempts *literally zero* reach -- any keyword with
    # even a few units of reach (still negligible in absolute terms) would skip dampening
    # entirely. 5.0 matches this codebase's existing "low tier" convention
    # (DEFAULT_VOLUME_SCORE_POLICY.low_tier_threshold) for what counts as no real signal.
    "max_reach": 5.0,
    "score_cap": 0.65,
}


DEFAULT_AGENTIC_RELEVANCY_FLOORS = {
    "enabled": True,
    "min_confidence": 0.55,
    "core": 0.65,
    "feature": 0.50,
    "broad": 0.45,
}


# Rubric-based relevancy (v1): a graded, explainable relevancy derived from the cached
# agentic classification instead of a raw LLM float. The subagent only supplies discrete,
# defensible judgments (semantic bucket, confidence, language group); this deterministic
# formula turns them into the number, so "why 0.90 not 0.85" always traces to a criterion,
# the weights are tunable in config, and the score is recomputable without re-warming cache.
#   score = bucket_base - (1 - confidence) * confidence_span + language_adjust   (clamped 0..1)
DEFAULT_RELEVANCY_RUBRIC = {
    "enabled": True,
    "bucket_base": {
        "core intent final": 0.90,
        "feature keywords": 0.70,
        "system keywords": 0.70,
        "broad expansion": 0.55,
        "consider keywords": 0.45,
        "style keywords": 0.45,
        "generic style reserve": 0.35,
        "manual review": 0.30,
        "language mismatch audit": 0.15,
        "dropped": 0.00,
    },
    "confidence_span": 0.15,          # lose up to this as confidence falls to 0
    "language_adjust": {"PRIMARY": 0.0, "SECONDARY": -0.05, "MIXED": -0.05, "UNKNOWN": -0.10},
    "zero_language_groups": ["FOREIGN"],  # these get 0 relevancy from the rubric
}


def relevancy_rubric_policy(config=None):
    policy = dict(DEFAULT_RELEVANCY_RUBRIC)
    override = (config or {}).get("relevancy_rubric", {}) or {}
    policy.update(override)
    # nested dicts should merge, not wholesale-replace, so a partial override still works
    if "bucket_base" in override:
        merged = dict(DEFAULT_RELEVANCY_RUBRIC["bucket_base"])
        merged.update(override["bucket_base"] or {})
        policy["bucket_base"] = merged
    if "language_adjust" in override:
        merged = dict(DEFAULT_RELEVANCY_RUBRIC["language_adjust"])
        merged.update(override["language_adjust"] or {})
        policy["language_adjust"] = merged
    return policy


def calculate_rubric_relevancy(row, config):
    """Graded relevancy from the cached agentic classification. Returns 0.0 when the
    keyword has no usable classification (so the lexical score takes over)."""
    policy = relevancy_rubric_policy(config)
    if not policy.get("enabled", True) or not hasattr(row, "get"):
        return 0.0

    bucket = str(row.get("AISemanticBucket", "") or "").strip().lower()
    base_map = policy.get("bucket_base", {})
    if bucket not in base_map:
        return 0.0  # unclassified / no AI signal -> let lexical relevancy decide

    language = str(row.get("LanguageGroup", "PRIMARY") or "PRIMARY").strip().upper()
    if language in {str(g).upper() for g in policy.get("zero_language_groups", [])}:
        return 0.0

    base = number(base_map.get(bucket), 0.0)
    # confidence defaults to 1.0 when the row was classified but carries no explicit score
    has_rule = bool(str(row.get("AIDecisionRule", "") or "").strip())
    confidence = min(1.0, max(0.0, number(row.get("AIConfidence"), 1.0 if has_rule else 0.0)))
    span = number(policy.get("confidence_span"), 0.15)
    score = base - (1.0 - confidence) * span
    score += number(policy.get("language_adjust", {}).get(language), 0.0)
    return max(0.0, min(1.0, score))


# New KEIN-free BalancedScore weights. KEI is collinear with Volume & Difficulty (KEI is
# derived from them), so it is dropped and its weight redistributed toward Relevancy.
DEFAULT_BALANCED_WEIGHTS = {
    "VolumeN": 0.35,
    "DifficultyN": 0.15,
    "KEIN": 0.0,
    "RelevancyScore": 0.30,
    "CurrentRankN": 0.10,
    "ExpansionValue": 0.10,
}


def resolve_balanced_weights(config):
    """Return BalancedScore weights, migrating legacy KEIN-based configs.

    Legacy app configs carry a non-zero ``KEIN`` weight (the old 6-way split). Those are
    migrated wholesale to DEFAULT_BALANCED_WEIGHTS so KEI no longer double-counts the
    volume/difficulty axis. A config that omits KEIN (or sets it to 0) is treated as
    already using the new scheme and its weights are respected, so apps can still tune
    weights per their needs. ``KEIN`` is always present (=0.0) so callers that still
    reference ``weights['KEIN']`` don't KeyError.
    """
    cfg = (config or {}).get("balanced_weights", {}) or {}
    if number(cfg.get("KEIN"), 0.0) > 0:
        return dict(DEFAULT_BALANCED_WEIGHTS)
    merged = dict(DEFAULT_BALANCED_WEIGHTS)
    merged.update(cfg)
    merged.setdefault("KEIN", 0.0)
    return merged


def relevancy_stacking_policy(config=None):
    policy = dict(DEFAULT_RELEVANCY_STACKING_POLICY)
    policy.update((config or {}).get("relevancy_stacking_dampener", {}) or {})
    return policy


def dampen_stacked_relevancy(row, config):
    """Cap RelevancyScore for keyword-stuffed long-tail phrases with weak real demand.

    RelevancyScore stacks a bonus independently for each intent category matched
    (core/feature/style), so a phrase stuffed with buzzwords ("retro emulator save
    state") can reach ~1.0 purely from term overlap with no search demand behind
    it. When that happens AND the keyword has no meaningful volume/reach, cap it
    back down so it can't out-rank genuinely higher-volume keywords in scoring
    that only matched one category naturally.

    Checks both the raw Keyword and the EN gloss, matching how RelevancyScore
    itself is computed (has_core_intent/has_feature_intent/has_style_intent look
    at both text sources) -- checking only one would miss hits that appear only
    in the other (e.g. an abbreviation in Keyword vs its spelled-out EN gloss).
    """
    policy = relevancy_stacking_policy(config)
    relevancy = number(row.get("RelevancyScore", 0))
    if not policy.get("enabled", True):
        return relevancy
    hits = sum([
        has_core_intent(row, config),
        has_feature_intent(row, config),
        has_style_intent(row, config),
    ])
    min_hits = number(policy.get("min_category_hits"), 2)
    if hits < min_hits:
        return relevancy
    if number(row.get("Volume"), 0) > number(policy.get("max_volume"), 10.0):
        return relevancy
    if number(row.get("MaximumReach"), 0) > number(policy.get("max_reach"), 0.0):
        return relevancy
    return min(relevancy, number(policy.get("score_cap"), 0.65))


def has_core_intent(value, config):
    return has_any_term(value, config.get("intent_core_terms", [])) or has_any_term(value, config.get("intent_core_words", []))


def has_feature_intent(value, config):
    return has_any_term(value, config.get("feature_terms", []))


def has_style_intent(value, config):
    return has_any_term(value, config.get("style_terms", []))


def check_naturalness(value, config):
    en_text = value.get("EN", value.get("Keyword", "")) if hasattr(value, "get") and not isinstance(value, str) else value
    normalized = normalize_filter_text(en_text)
    words = tokenize(en_text)
    if not words:
        return "UNNATURAL", "Empty keyword"
    counts = {word: words.count(word) for word in set(words)}
    if len(words) > 2 and (max(counts.values()) / len(words)) > 0.5:
        return "STUFFING", "Too many repeated words"
    if len(words) > 6 and not (has_core_intent(value, config) or has_feature_intent(value, config)):
        return "TOO_LONG", f"Keyword has too many words ({len(words)})"
    if any(re.search(pattern, normalized) for pattern in QUERY_PATTERNS):
        return "UNNATURAL", "Fails structural validation"
    for word, count in counts.items():
        if count > 1 and len(words) <= 4 and f"{word} {word}" in normalized:
            return "UNNATURAL", "Repeated adjacent keyword token"
    return "OK", "Natural enough for keyword research"


def calculate_expansion(row, config):
    token_count = len(tokenize(row.get("Keyword", "")))
    score = 0.85 if token_count <= 1 else 0.75 if token_count == 2 else 0.55 if token_count == 3 else 0.35
    if has_core_intent(row, config):
        score += 0.10
    elif has_feature_intent(row, config):
        score += 0.05
    if row.get("is_competitor"):
        score = 0.10
    if has_style_intent(row, config) and not has_core_intent(row, config):
        score = min(score, 0.35)
    return max(0.0, min(1.0, score))


def get_language_bonus(row):
    group = str(row.get("LanguageGroup", "PRIMARY")).upper()
    return 0.02 if group == "PRIMARY" else 0.01 if group == "SECONDARY" else 0.0


def _agentic_relevancy_floors(config=None):
    policy = dict(DEFAULT_AGENTIC_RELEVANCY_FLOORS)
    policy.update((config or {}).get("agentic_relevancy_floors", {}) or {})
    classifier = (config or {}).get("agentic_keyword_classifier", {}) or {}
    if "min_confidence" not in ((config or {}).get("agentic_relevancy_floors", {}) or {}):
        policy["min_confidence"] = classifier.get("min_confidence", policy["min_confidence"])
    return policy


def _agentic_relevancy_floor(row, config):
    policy = _agentic_relevancy_floors(config)
    if not policy.get("enabled", True):
        return 0.0
    if not hasattr(row, "get"):
        return 0.0

    blocked_flags = (
        "is_competitor",
        "is_typo",
        "is_truncated",
        "is_irrelevant",
        "is_noise",
        "is_risky_ip",
        "is_platform_affiliation",
    )
    if any(bool(row.get(flag)) for flag in blocked_flags):
        return 0.0
    if str(row.get("NaturalnessFlag", "OK") or "OK").upper() != "OK":
        return 0.0
    if str(row.get("LanguageGroup", "PRIMARY") or "PRIMARY").upper() in {"FOREIGN", "UNKNOWN"}:
        return 0.0

    confidence_raw = row.get("AIConfidence", "")
    confidence = number(confidence_raw, 1.0 if str(row.get("AIDecisionRule", "") or "").strip() else 0.0)
    if confidence < number(policy.get("min_confidence"), 0.55):
        return 0.0

    bucket = str(row.get("AISemanticBucket", "") or "").strip().lower()
    rule = str(row.get("AIDecisionRule", "") or "").strip().lower()
    if bucket == "core intent final" or rule in {"ai_core_intent", "agentic_core_intent", "core_intent_final"}:
        return number(policy.get("core"), 0.65)
    if bucket in {"feature keywords", "system keywords", "effect / filter type"} or rule in {"ai_feature_intent", "feature_keywords", "system_keywords"}:
        return number(policy.get("feature"), 0.50)
    if bucket == "broad expansion" or rule in {"ai_broad_expansion", "broad_expansion"}:
        return number(policy.get("broad"), 0.45)
    return 0.0


def calculate_relevancy(row, config):
    score = float(config.get("relevancy_weights", {}).get("base", 0.30))
    if has_core_intent(row, config):
        score += 0.35
    if has_feature_intent(row, config):
        score += 0.20
    if has_style_intent(row, config):
        score += 0.15
    if row.get("is_competitor"):
        score -= 0.20
    if row.get("is_irrelevant"):
        score -= 0.25
    if str(row.get("LanguageGroup", "")).upper() == "FOREIGN":
        score -= 0.30
    score += float(row.get("CompetitorBoost", 0.0) or 0.0)
    score = max(score, _agentic_relevancy_floor(row, config))
    return max(0.0, min(1.0, score))
