import re

from shared.language_detector import get_market_language_policy

from .hard_filters import evaluate_hard_filters
from .matcher import has_any_term, normalize_filter_text
from .scoring import has_core_intent, has_feature_intent, has_style_intent


DEFAULT_RISK_POLICY = {
    "competitor_brand_action": "drop",
    "ambiguous_brand_action": "consider",
    "risky_ip_action": "consider",
    "platform_context_action": "consider",
    "platform_only_action": "drop",
    "platform_affiliation_action": "drop",
    "style_only_action": "reserve",
    "core_intent_override": True,
}
HARD_BOOLEAN_COLUMNS = [
    "is_competitor", "is_typo", "is_truncated", "is_irrelevant", "is_noise",
    "is_risky_ip", "is_platform_risk", "is_platform_only",
    "is_platform_affiliation", "is_ambiguous_brand",
]


def _row_flags(row, config):
    if all(key in row for key in HARD_BOOLEAN_COLUMNS):
        return {key: bool(row.get(key)) for key in HARD_BOOLEAN_COLUMNS}
    return evaluate_hard_filters(row, config)


def _risk_policy(config):
    policy = dict(DEFAULT_RISK_POLICY)
    configured = dict(config.get("risk_policy", {}) or {})
    if "platform_style_action" in configured and "platform_context_action" not in configured:
        configured["platform_context_action"] = configured["platform_style_action"]
    policy.update(configured)
    return policy


def _app_mode(config):
    mode = str(config.get("semantic_mode", "")).strip().lower()
    if mode == "game_emulator":
        return "game"
    if mode == "ar_filter":
        return "ar_filter"
    return "generic"


def _declared_safe_terms(config, terms):
    # A risky/platform brand term is only safe to override when the app's OWN
    # FUNCTIONAL vocabulary (intent_core_terms or feature_terms) already spells
    # that exact brand word out (e.g. "nintendo" inside "nintendo ds emulator",
    # or listed directly in feature_terms like "nintendo"/"playstation"/"xbox"
    # for a multi-console emulator app). That is a deliberate declaration that
    # this brand reference is app functionality -- not just an incidental word
    # landing in the same keyword (e.g. "pokemon" next to a generic single-word
    # core term like "prank" is still a real IP risk and must not be swept in).
    #
    # `terms` must be the SINGLE list relevant to the flag being overridden
    # (risky_ip_terms for is_risky_ip; risky_platform_terms for is_platform_risk/
    # is_platform_only) -- never the union of both. Mixing lists lets a term
    # declared safe in one list rescue a completely different flag: e.g. an
    # AI-generated EN gloss for "super mario" reads "Super Mario (Nintendo
    # game)" -- "nintendo" is declared safe in feature_terms, but that must not
    # rescue the is_risky_ip flag that "mario" (undeclared, real franchise IP)
    # triggered on the same row.
    #
    # style_terms is deliberately EXCLUDED here. In this codebase style_terms
    # doubles as an "aesthetic/theme" bucket AND, for game_emulator apps, a
    # "Game Title/Franchise (Research Only)" bucket -- e.g. Game_Emulator lists
    # "mario"/"super mario"/"mario kart" in style_terms purely to track search
    # volume for competitive research, NOT to declare Mario references safe for
    # real App Store metadata. Letting style_terms grant the override would let
    # that research-only declaration silently rescue genuine franchise IP.
    declared_terms = [
        normalize_filter_text(t)
        for key in ("intent_core_terms", "feature_terms")
        for t in config.get(key, []) or []
        if normalize_filter_text(t)
    ]
    if not declared_terms:
        return set()
    declared_pool = " ".join(declared_terms)
    return {
        term
        for term in terms or []
        if normalize_filter_text(term)
        # Word-boundary match, not raw substring -- a bare `in` check would let a
        # short risky term like "cod" or "play" match inside an unrelated word
        # ("decode", "gameplay") and silently grant an override app-wide.
        and re.search(r"\b" + re.escape(normalize_filter_text(term)) + r"\b", declared_pool)
    }


def _matches_declared_safe_term(row, config, terms):
    safe = _declared_safe_terms(config, terms)
    if not safe:
        return False
    from .matcher import find_term, row_texts
    matched_terms = set()
    for source, text in row_texts(row):
        for term in terms:
            if find_term(text, [term]):
                matched_terms.add(term)
    if not matched_terms:
        return False
    return matched_terms.issubset(safe)


def _is_explicit_core_term(row, config):
    keyword = normalize_filter_text(row.get("Keyword", ""))
    core_terms = {
        normalize_filter_text(term)
        for term in config.get("intent_core_terms", []) or []
        if normalize_filter_text(term)
    }
    return bool(keyword and keyword in core_terms)


def _action_result(action, rule, label):
    if action == "drop":
        return "Dropped", rule, f"Dropped: {label}"
    if action == "reserve":
        return "Generic Style Reserve", rule, f"Reserve: {label}"
    return "Consider Keywords", rule, f"Consider: {label}"


def _ai_classification_result(row, config):
    bucket = str(row.get("AISemanticBucket", "") or "").strip()
    if not bucket:
        return None
    try:
        confidence = float(row.get("AIConfidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    classifier_config = (
        config.get("agentic_keyword_classifier", {})
        or {}
    )
    minimum = float((classifier_config.get("min_confidence", 0.55)) or 0.55)
    if confidence < minimum:
        return None

    language_group = str(row.get("LanguageGroup", "PRIMARY")).upper()
    if language_group == "FOREIGN" and bucket not in {"Dropped", "Language Mismatch Audit", "Manual Review"}:
        return "Language Mismatch Audit", "foreign_language_mismatch", "Foreign language mismatch"
    if language_group == "UNKNOWN" and bucket not in {"Dropped", "Manual Review"}:
        return "Manual Review", "manual_review", "Unknown language"

    rule = str(row.get("AIDecisionRule", "") or "ai_semantic_classification")
    reason = str(row.get("AIReason", "") or "AI semantic classification")
    return bucket, rule, reason


def classify_keyword(row, config):
    flags = _row_flags(row, config)
    policy = _risk_policy(config)
    app_mode = _app_mode(config)
    has_core = has_core_intent(row, config)
    has_feature = has_feature_intent(row, config)
    has_style = has_style_intent(row, config)

    if flags["is_competitor"]:
        return _action_result(policy["competitor_brand_action"], "competitor_brand", "Competitor brand")
    if flags["is_typo"]:
        return "Dropped", "typo_truncated_broken", "Dropped: Typo or broken keyword"
    if flags["is_truncated"]:
        return "Dropped", "typo_truncated_broken", "Dropped: Truncated keyword"
    if flags["is_irrelevant"]:
        if policy.get("core_intent_override", False) and has_core:
            return "Consider Keywords", "irrelevant_intent_core_override", "Consider: Core intent with broad irrelevant-risk term"
        return "Dropped", "irrelevant_intent", "Dropped: Irrelevant category/intent"
    if flags["is_noise"]:
        return "Dropped", "noise_only", "Dropped: Noise-only generic term"
    if flags.get("HardFilterRule") == "possible_truncated_keyword":
        action = str((config.get("truncation_policy", {}) or {}).get("low_confidence_action", "manual_review")).strip().lower()
        if action == "consider":
            return "Consider Keywords", "possible_truncated_keyword", "Consider: Possible truncated keyword"
        if action != "ignore":
            return "Manual Review", "possible_truncated_keyword", "Manual Review: Possible truncated keyword"

    naturalness = str(row.get("NaturalnessFlag", "OK"))
    if naturalness != "OK":
        return "Dropped", "unnatural", f"Dropped: Unnatural phrase ({row.get('NaturalnessReason', '')})"

    if flags["is_platform_affiliation"]:
        # Deliberately NO core_intent_override here, unlike is_risky_ip/is_platform_risk/
        # is_platform_only below. platform_affiliation_terms is meant for explicit
        # impersonation-claim phrases (e.g. "official nintendo", "official playstation"),
        # which carry real affiliation/trademark risk regardless of whether the app's own
        # intent_core_terms/feature_terms/style_terms happen to declare that brand word --
        # unlike a plain functional brand mention (e.g. "nintendo ds emulator"), claiming
        # "official" status is risky on its own terms. Do not add an override here without
        # revisiting this reasoning.
        return _action_result(policy["platform_affiliation_action"], "platform_affiliation", "Platform affiliation risk")
    if flags["is_platform_only"]:
        # "Platform-only" means the keyword has no *recognized* core/feature phrase
        # alongside the brand word (e.g. "nds pro emulator" doesn't literally contain
        # the configured phrase "nds emulator" because "pro" breaks the substring). If
        # the brand word itself is one the app has explicitly declared as core (see
        # _declared_safe_terms) -- checked against risky_platform_terms specifically,
        # since is_platform_only is only ever set when is_platform_risk already fired.
        if policy.get("core_intent_override", False) and _matches_declared_safe_term(row, config, config.get("risky_platform_terms", [])):
            return "Consider Keywords", "platform_only_core_override", "Consider: Core app intent term also matches a platform/hardware brand word"
        return _action_result(policy["platform_only_action"], "platform_only", "Platform-only keyword")
    if flags["is_risky_ip"]:
        # A risky-IP/brand term can appear only because the AI-generated EN gloss spells
        # the abbreviation out in full (e.g. "nds" -> "Nintendo DS"), even though the
        # visible keyword never names the brand. Only relax this when the app's own
        # intent_core_terms/feature_terms config already spells that exact risky_ip_terms
        # word out (see _declared_safe_terms) -- checked against risky_ip_terms
        # specifically, NOT risky_platform_terms, so a declared-safe platform word (e.g.
        # "nintendo") appearing incidentally in the same row can't rescue an unrelated,
        # undeclared risky_ip_terms hit (e.g. "mario" in "Super Mario (Nintendo game)").
        if policy.get("core_intent_override", False) and _matches_declared_safe_term(row, config, config.get("risky_ip_terms", [])):
            return "Consider Keywords", "risky_ip_core_override", "Consider: Core app intent term also matches a sensitive IP/brand word"
        return _action_result(policy["risky_ip_action"], "risky_ip", "Sensitive IP term")
    if flags["is_ambiguous_brand"]:
        return _action_result(policy["ambiguous_brand_action"], "ambiguous_brand", "Ambiguous brand term")
    if flags["is_platform_risk"]:
        if policy.get("core_intent_override", False) and _matches_declared_safe_term(row, config, config.get("risky_platform_terms", [])):
            return "Consider Keywords", "platform_risk_core_override", "Consider: Core app intent term also matches a platform/hardware brand word"
        return _action_result(policy["platform_context_action"], "platform_style_risk", "Platform-style context")

    language_group = str(row.get("LanguageGroup", "PRIMARY")).upper()
    ai_result = _ai_classification_result(row, config)
    if ai_result:
        return ai_result

    if language_group == "FOREIGN":
        return "Language Mismatch Audit", "foreign_language_mismatch", "Foreign language mismatch"
    if language_group == "UNKNOWN":
        return "Manual Review", "manual_review", "Unknown language"
    if language_group == "MIXED":
        language_policy = get_market_language_policy(config.get("market", "US_EN"), config)
        if language_policy.get("mixed_allowed", False):
            return "Consider Keywords", "mixed_language_consider", "Mixed language allowed for this market"
        return "Manual Review", "manual_review", "Mixed language needs review"
    if language_group == "SECONDARY":
        if _is_explicit_core_term(row, config):
            return "Core Intent Final", "secondary_explicit_core_intent", "Explicit core intent term retained across market languages"
        return "Consider Keywords", "secondary_language_handling", "Secondary language handling"

    if has_core:
        if app_mode == "game":
            return "Core Intent Final", "core_intent_final", "Strong core game emulator search intent"
        if app_mode == "ar_filter":
            return "Core Intent Final", "core_intent_final", "Strong core camera filter/effect search intent"
        return "Core Intent Final", "core_intent_final", "Strong core app search intent"

    if app_mode == "game":
        if has_style:
            if has_any_term(row, ["retro games", "classic games", "gba games", "arcade games", "game emulator"]):
                return "Broad Expansion", "broad_expansion", "Generic game/emulator variant"
            return "Game Keywords", "game_keywords", "Game Title/Franchise candidate (Research Only)"
        if has_feature:
            return "System Keywords", "system_keywords", "System/Console candidate"
    elif app_mode == "ar_filter":
        if has_style and not has_feature:
            return _action_result(policy["style_only_action"], "style_only", "Generic aesthetic/style-only term")
        if has_feature:
            return "Effect / Filter Type", "feature_keywords", "Specific effect/filter candidate"
        if has_style:
            return "User Intent / Content Use Case", "style_keywords", "User intent/content use case candidate"
    else:
        if has_style and not has_feature:
            return _action_result(policy["style_only_action"], "style_only", "Generic aesthetic/style-only term")
        if has_feature:
            return "Feature Keywords", "feature_keywords", "Specific feature candidate"
        if has_style:
            return "Style Keywords", "style_keywords", "Aesthetic/theme candidate"

    if float(row.get("RelevancyScore", 0) or 0) < 0.45:
        return "Dropped", "dropped", "Dropped: Weak app intent after scoring"
    if app_mode == "game":
        return "Broad Expansion", "broad_expansion", "Moderately relevant emulator expansion"
    if app_mode == "ar_filter":
        return "Broad Expansion", "broad_expansion", "Broad camera filter expansion"
    return "Broad Expansion", "broad_expansion", "Broad app expansion"


def apply_user_overrides(row, config):
    keyword = normalize_filter_text(row.get("Keyword", ""))
    overrides = config.get("user_overrides", {}) or {}
    force_drop = {normalize_filter_text(term) for term in overrides.get("force_drop_terms", []) or []}
    if keyword in force_drop:
        return "Dropped", "user_override_force_drop", "Dropped: Force drop by user override"

    flags = _row_flags(row, config)
    immutable = (
        flags["is_competitor"] or flags["is_typo"] or flags["is_truncated"] or
        flags["is_irrelevant"] or flags["is_noise"] or flags["is_platform_affiliation"] or
        str(row.get("NaturalnessFlag", "OK")) != "OK" or
        str(row.get("LanguageGroup", "")).upper() in {"FOREIGN", "UNKNOWN", "MIXED"}
    )
    if immutable:
        return row["Bucket"], row["DecisionRule"], row["Reason"]

    force_consider = {normalize_filter_text(term) for term in overrides.get("force_consider_terms", []) or []}
    if keyword in force_consider:
        return "Consider Keywords", "user_override_force_consider", "Consider Keywords: Forced by user override"

    force_top30 = {normalize_filter_text(term) for term in overrides.get("force_top30_terms", []) or []}
    risk_limited = flags["is_risky_ip"] or flags["is_platform_risk"] or flags["is_ambiguous_brand"]
    if keyword in force_top30 and not risk_limited:
        return "Core Intent Final", "user_override_force_top30", "Core Intent Final: Forced by user override"
    return row["Bucket"], row["DecisionRule"], row["Reason"]
