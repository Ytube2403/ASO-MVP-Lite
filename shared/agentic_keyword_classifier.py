import json
import os
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass

from shared.keyword_filter.cache import config_hash
from shared.keyword_filter.hard_filters import evaluate_hard_filters
from shared.keyword_filter.matcher import has_any_term, normalize_filter_text, tokenize
from shared.keyword_filter.scoring import has_core_intent, has_feature_intent, has_style_intent
from shared.language_detector import detect_keyword_language


class AIKeywordClassifierError(RuntimeError):
    pass


AGENTIC_PROVIDER = "antigravity_subagent"
DEFAULT_MODEL = "subagent-cache-v1"
DEFAULT_PROMPT_VERSION = "agentic-keyword-classifier-v1"
DEFAULT_CACHE_PATH = ".cache/agentic_keyword_analysis.sqlite3"
DEFAULT_BATCH_SIZE = 200
DEFAULT_PRE_FILTER_CONFIG = {
    "enabled": True,
    "duplicate_strategy": "canonical_reuse",
    "preserve_if_matches_intent": True,
    "allow_possible_truncated_to_ai": True,
    "skip_rules": [
        "empty_keyword",
        "duplicate_keyword",
        "competitor_brand",
        "typo_blacklist",
        "truncated_keyword",
        "irrelevant_intent",
        "noise_only",
        "platform_affiliation",
        "platform_only",
    ],
}

LANGUAGE_GROUPS = {"PRIMARY", "SECONDARY", "MIXED", "FOREIGN", "UNKNOWN"}
SEMANTIC_BUCKETS = {
    "Core Intent Final",
    "Broad Expansion",
    "Feature Keywords",
    "Style Keywords",
    "Consider Keywords",
    "Generic Style Reserve",
    "Language Mismatch Audit",
    "Manual Review",
    "Dropped",
}

OUTPUT_COLUMNS = [
    "NeedsAI",
    "PreAIAction",
    "PreAIRule",
    "PreAIReason",
    "CanonicalKeyword",
    "DetectedLanguage",
    "LanguageGroup",
    "AISemanticBucket",
    "AIDecisionRule",
    "AIReason",
    "AIConfidence",
    "AIEnglishGloss",
    "AIStatus",
]


@dataclass(frozen=True)
class AIKeywordAnalysis:
    keyword: str
    detected_language: str
    language_group: str
    semantic_bucket: str
    decision_rule: str
    reason: str
    confidence: float
    english_gloss: str
    status: str = "AI_CLASSIFIED"


@dataclass
class PreAIItem:
    position: int
    row: dict
    keyword: str
    canonical_keyword: str
    needs_ai: bool
    action: str
    rule: str
    reason: str
    canonical_position: int | None = None


def enabled(config):
    return bool(_configured_classifier(config).get("enabled", False))


def _configured_classifier(config):
    config = config or {}
    return config.get("agentic_keyword_classifier", {}) or {}


def _classifier_config(config):
    configured = dict(_configured_classifier(config) or {})
    pre_filter_config = dict(DEFAULT_PRE_FILTER_CONFIG)
    pre_filter_config.update(dict(configured.get("pre_filter", {}) or {}))
    return {
        "provider": AGENTIC_PROVIDER,
        "model": str(configured.get("model", DEFAULT_MODEL) or DEFAULT_MODEL),
        "prompt_version": str(configured.get("prompt_version", DEFAULT_PROMPT_VERSION) or DEFAULT_PROMPT_VERSION),
        "batch_size": int(configured.get("batch_size", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE),
        "cache_path": str(configured.get("cache_path", DEFAULT_CACHE_PATH) or DEFAULT_CACHE_PATH),
        "cache_only": True,
        "fail_on_api_error": True,
        "min_confidence": float(configured.get("min_confidence", 0.55) or 0.55),
        "pre_filter": pre_filter_config,
    }


def _context_hash(config, app_profile=None):
    relevant = {
        "app_id": (config or {}).get("app_id", ""),
        "app_name": (config or {}).get("app_name", ""),
        "category": (config or {}).get("category", ""),
        "market": (config or {}).get("market", ""),
        "semantic_mode": (config or {}).get("semantic_mode", ""),
        "market_language_policy": (config or {}).get("market_language_policy", {}),
        "intent_core_terms": (config or {}).get("intent_core_terms", []),
        "intent_core_words": (config or {}).get("intent_core_words", []),
        "feature_terms": (config or {}).get("feature_terms", []),
        "style_terms": (config or {}).get("style_terms", []),
        "visual_terms": (config or {}).get("visual_terms", []),
        "noise_terms": (config or {}).get("noise_terms", []),
        "irrelevant_intent_terms": (config or {}).get("irrelevant_intent_terms", []),
        "profile_summary": (app_profile or {}).get("live_store_metadata", {}),
    }
    return config_hash(relevant)


def _cache_key(keyword, config, market, app_profile=None, classifier_config=None):
    classifier_config = classifier_config or _classifier_config(config)
    return (
        classifier_config["provider"],
        classifier_config["model"],
        classifier_config["prompt_version"],
        str((config or {}).get("app_id", "")),
        str(market or (config or {}).get("market", "")),
        _context_hash(config, app_profile),
        normalize_filter_text(keyword),
    )


def _pre_filter_config(classifier_config):
    configured = dict(classifier_config.get("pre_filter", {}) or {})
    merged = dict(DEFAULT_PRE_FILTER_CONFIG)
    merged.update(configured)
    merged["skip_rules"] = {
        str(rule or "").strip()
        for rule in (merged.get("skip_rules") or [])
        if str(rule or "").strip()
    }
    return merged


def _has_visual_intent(value, config):
    return has_any_term(value, (config or {}).get("visual_terms", []))


def _has_preserved_intent(value, config):
    return (
        has_core_intent(value, config)
        or has_feature_intent(value, config)
        or has_style_intent(value, config)
        or _has_visual_intent(value, config)
    )


def _pre_ai_skip_reason(row, config, pre_filter):
    keyword = str(row.get("Keyword", "") or "")
    canonical = normalize_filter_text(keyword)
    tokens = tokenize(keyword)
    skip_rules = pre_filter["skip_rules"]
    if "empty_keyword" in skip_rules and (not canonical or not tokens):
        return "empty_keyword", "Empty or invalid keyword"

    hard = evaluate_hard_filters(row, config)
    rule = str(hard.get("HardFilterRule", "") or "")
    if rule == "possible_truncated_keyword" and pre_filter.get("allow_possible_truncated_to_ai", True):
        return "", ""
    if not rule or rule not in skip_rules:
        return "", ""

    protected_rules = {"irrelevant_intent", "noise_only", "platform_affiliation", "platform_only"}
    if (
        bool(pre_filter.get("preserve_if_matches_intent", True))
        and rule in protected_rules
        and _has_preserved_intent(row, config)
    ):
        return "", ""

    term = str(hard.get("HardFilterTerm", "") or "")
    if rule == "competitor_brand":
        reason = f"Competitor brand match: {term}" if term else "Competitor brand match"
    elif rule == "typo_blacklist":
        reason = f"Typo blacklist match: {term}" if term else "Typo blacklist match"
    elif rule == "truncated_keyword":
        reason = f"Hard truncated keyword: {term}" if term else "Hard truncated keyword"
    elif rule == "irrelevant_intent":
        reason = f"Clearly irrelevant intent: {term}" if term else "Clearly irrelevant intent"
    elif rule == "noise_only":
        reason = f"Noise-only keyword: {term}" if term else "Noise-only keyword"
    elif rule == "platform_affiliation":
        reason = f"Platform affiliation without app intent: {term}" if term else "Platform affiliation without app intent"
    elif rule == "platform_only":
        reason = f"Platform-only keyword without app intent: {term}" if term else "Platform-only keyword without app intent"
    else:
        reason = f"Pre-AI hard filter match: {rule}"
    return rule, reason


def _build_pre_ai_items(rows, config, classifier_config):
    pre_filter = _pre_filter_config(classifier_config)
    if not bool(pre_filter.get("enabled", True)):
        return [
            PreAIItem(
                position=index,
                row=row,
                keyword=str(row.get("Keyword", "") or ""),
                canonical_keyword=normalize_filter_text(row.get("Keyword", "")),
                needs_ai=True,
                action="send_to_agentic_cache",
                rule="pre_filter_disabled",
                reason="Pre-AI filter disabled",
            )
            for index, row in enumerate(rows)
        ]

    items = []
    canonical_first = {}
    duplicate_strategy = str(pre_filter.get("duplicate_strategy", "canonical_reuse") or "canonical_reuse").strip().lower()
    skip_duplicates = duplicate_strategy == "canonical_reuse" and "duplicate_keyword" in pre_filter["skip_rules"]

    for index, row in enumerate(rows):
        keyword = str(row.get("Keyword", "") or "")
        canonical = normalize_filter_text(keyword)
        rule, reason = _pre_ai_skip_reason(row, config, pre_filter)
        if rule:
            item = PreAIItem(
                position=index,
                row=row,
                keyword=keyword,
                canonical_keyword=canonical,
                needs_ai=False,
                action="skip_ai",
                rule=rule,
                reason=reason,
            )
            items.append(item)
            if canonical and canonical not in canonical_first:
                canonical_first[canonical] = index
            continue

        if canonical and skip_duplicates and canonical in canonical_first:
            canonical_position = canonical_first[canonical]
            items.append(PreAIItem(
                position=index,
                row=row,
                keyword=keyword,
                canonical_keyword=canonical,
                needs_ai=False,
                action="reuse_canonical",
                rule="duplicate_keyword",
                reason=f"Duplicate normalized keyword; reused row {canonical_position + 1}",
                canonical_position=canonical_position,
            ))
            continue

        items.append(PreAIItem(
            position=index,
            row=row,
            keyword=keyword,
            canonical_keyword=canonical,
            needs_ai=True,
            action="read_agentic_cache",
            rule="needs_agentic_cache",
            reason="Eligible for agentic cache lookup",
        ))
        if canonical and canonical not in canonical_first:
            canonical_first[canonical] = index
    return items


def _empty_analysis(keyword, status, decision_rule="", reason="", config=None, market="", english_vocab=None):
    detected, group = detect_keyword_language(keyword, market or (config or {}).get("market", "US_EN"), config or {}, english_vocab=english_vocab)
    return AIKeywordAnalysis(
        keyword=keyword,
        detected_language=detected,
        language_group=group,
        semantic_bucket="",
        decision_rule=decision_rule,
        reason=reason,
        confidence=0.0,
        english_gloss="",
        status=status,
    )


class AIKeywordClassifier:
    def __init__(
        self,
        cache_path,
        config=None,
        app_profile=None,
        market="",
        api_key=None,
        base_url=None,
        opener=None,
        sleep=None,
        clock=None,
    ):
        self.config = config or {}
        self.classifier_config = _classifier_config(self.config)
        self.app_profile = app_profile or {}
        self.market = str(market or self.config.get("market", ""))
        self.cache_path = os.path.abspath(cache_path)
        self.api_keys = []
        self.api_key = ""
        self.base_url = ""
        self.opener = opener
        self.sleep = sleep
        self.clock = clock or time.time
        self.stats = {}
        self._initialize_cache()

    def _reset_stats(self, total_rows=0):
        self.stats = {
            "total_rows": int(total_rows),
            "cache_hit": 0,
            "api_candidates": 0,
            "api_batches": 0,
            "key_pool_size": 0,
            "max_workers": 0,
            "batch_seconds": [],
            "retries": 0,
            "rate_limit_errors": 0,
            "timeout_errors": 0,
            "failed_batches": 0,
            "total_ai_seconds": 0.0,
        }

    def _connect(self):
        connection = sqlite3.connect(self.cache_path, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize_cache(self):
        directory = os.path.dirname(self.cache_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_keyword_analysis (
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    market TEXT NOT NULL,
                    context_hash TEXT NOT NULL,
                    normalized_keyword TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    detected_language TEXT NOT NULL,
                    language_group TEXT NOT NULL,
                    semantic_bucket TEXT NOT NULL,
                    decision_rule TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    english_gloss TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (
                        provider, model, prompt_version, app_id, market,
                        context_hash, normalized_keyword
                    )
                )
                """
            )
            connection.commit()

    def _get_cached(self, keyword):
        key = _cache_key(keyword, self.config, self.market, self.app_profile, self.classifier_config)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT keyword, detected_language, language_group, semantic_bucket,
                       decision_rule, reason, confidence, english_gloss
                FROM ai_keyword_analysis
                WHERE provider = ? AND model = ? AND prompt_version = ?
                  AND app_id = ? AND market = ? AND context_hash = ?
                  AND normalized_keyword = ?
                """,
                key,
            ).fetchone()
        if not row:
            return None
        return AIKeywordAnalysis(
            keyword=row[0],
            detected_language=row[1],
            language_group=row[2],
            semantic_bucket=row[3],
            decision_rule=row[4],
            reason=row[5],
            confidence=float(row[6]),
            english_gloss=row[7],
            status="AI_CACHE_HIT",
        )

    def _store_cached(self, result, raw_json):
        key = _cache_key(result.keyword, self.config, self.market, self.app_profile, self.classifier_config)
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO ai_keyword_analysis (
                    provider, model, prompt_version, app_id, market, context_hash,
                    normalized_keyword, keyword, detected_language, language_group,
                    semantic_bucket, decision_rule, reason, confidence, english_gloss,
                    raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, model, prompt_version, app_id, market, context_hash, normalized_keyword)
                DO UPDATE SET
                    keyword = excluded.keyword,
                    detected_language = excluded.detected_language,
                    language_group = excluded.language_group,
                    semantic_bucket = excluded.semantic_bucket,
                    decision_rule = excluded.decision_rule,
                    reason = excluded.reason,
                    confidence = excluded.confidence,
                    english_gloss = excluded.english_gloss,
                    raw_json = excluded.raw_json,
                    updated_at = excluded.updated_at
                """,
                (
                    *key,
                    result.keyword,
                    result.detected_language,
                    result.language_group,
                    result.semantic_bucket,
                    result.decision_rule,
                    result.reason,
                    result.confidence,
                    result.english_gloss,
                    json.dumps(raw_json, ensure_ascii=False, sort_keys=True),
                    self.clock(),
                ),
            )
            connection.commit()

    def _update_english_gloss(self, keyword, english_gloss):
        """Update only the english_gloss of an existing cache row.

        Used when warming a ``missing_english_gloss`` keyword: the row was
        already classified, so we must not overwrite its semantic_bucket /
        confidence / decision_rule with a fresh guess. Returns True when an
        existing row was updated, False when no row matched.
        """
        key = _cache_key(keyword, self.config, self.market, self.app_profile, self.classifier_config)
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE ai_keyword_analysis
                SET english_gloss = ?, updated_at = ?
                WHERE provider = ? AND model = ? AND prompt_version = ?
                  AND app_id = ? AND market = ? AND context_hash = ?
                  AND normalized_keyword = ?
                """,
                (english_gloss, self.clock(), *key),
            )
            connection.commit()
            return cursor.rowcount > 0

    def analyze_rows(self, keyword_rows):
        started_at = self.clock()
        self._reset_stats(total_rows=len(keyword_rows))
        results = {}
        missing = []
        missing_gloss = []
        for row in keyword_rows:
            keyword = str(row.get("Keyword", "") or "")
            cached = self._get_cached(keyword)
            if cached is None:
                missing.append(row)
                continue
            results[keyword] = cached
            self.stats["cache_hit"] += 1
            if cached.detected_language.lower() != "en" and not str(cached.english_gloss or "").strip():
                missing_gloss.append(keyword)
        self.stats["api_candidates"] = len(missing)
        self.stats["total_ai_seconds"] = self.clock() - started_at
        if missing or missing_gloss:
            parts = []
            if missing:
                sample = ", ".join(str(row.get("Keyword", "") or "") for row in missing[:5])
                parts.append(f"{len(missing)} uncached keyword(s); sample: {sample}")
            if missing_gloss:
                sample = ", ".join(missing_gloss[:5])
                parts.append(f"{len(missing_gloss)} cached keyword(s) missing english_gloss; sample: {sample}")
            raise AIKeywordClassifierError(
                "Agentic keyword classifier is cache-only. "
                "Run tools/warm_cache_helper.py find-misses/prepare-batches/save-results first. "
                + " ".join(parts)
            )
        return results


def _fallback_dataframe(df, config, english_vocab=None, market=""):
    import pandas as pd

    rows = []
    for _, row in df.iterrows():
        lang, group = detect_keyword_language(row.get("Keyword", ""), market or config.get("market", "US_EN"), config, english_vocab=english_vocab)
        rows.append({
            "NeedsAI": False,
            "PreAIAction": "agentic_disabled",
            "PreAIRule": "agentic_disabled",
            "PreAIReason": "Agentic classifier disabled; used heuristic language detector",
            "CanonicalKeyword": normalize_filter_text(row.get("Keyword", "")),
            "DetectedLanguage": lang,
            "LanguageGroup": group,
            "AISemanticBucket": "",
            "AIDecisionRule": "",
            "AIReason": "",
            "AIConfidence": 0.0,
            "AIEnglishGloss": "",
            "AIStatus": "AI_DISABLED_HEURISTIC",
        })
    return pd.DataFrame(rows, index=df.index)


def analyze_dataframe(df, config, app_profile=None, cache_path=None, market="", english_vocab=None, service=None):
    import pandas as pd

    if not enabled(config):
        return _fallback_dataframe(df, config, english_vocab=english_vocab, market=market)
    classifier_config = _classifier_config(config)
    if cache_path is None:
        configured_path = classifier_config["cache_path"]
        cache_path = configured_path if os.path.isabs(configured_path) else os.path.join(os.getcwd(), configured_path)
    service = service or AIKeywordClassifier(cache_path, config=config, app_profile=app_profile, market=market)
    rows = [row.to_dict() for _, row in df.iterrows()]
    pre_ai_items = _build_pre_ai_items(rows, config, classifier_config)
    cache_rows = [item.row for item in pre_ai_items if item.needs_ai]
    result_by_keyword = service.analyze_rows(cache_rows) if cache_rows else {}

    result_by_position = {}
    for item in pre_ai_items:
        cached = service._get_cached(item.keyword)
        if item.needs_ai:
            result = result_by_keyword.get(item.keyword) or cached
            if result is None:
                raise AIKeywordClassifierError(f"Missing agentic cache result for {item.keyword!r}")
            result_by_position[item.position] = result
        elif item.action == "skip_ai":
            result_by_position[item.position] = cached or _empty_analysis(
                item.keyword,
                "AI_SKIPPED_PREFILTER",
                decision_rule=item.rule,
                reason=item.reason,
                config=config,
                market=market,
                english_vocab=english_vocab,
            )

    for item in pre_ai_items:
        if item.action != "reuse_canonical":
            continue
        canonical_result = result_by_position.get(item.canonical_position)
        if canonical_result is None:
            raise AIKeywordClassifierError(f"Missing canonical agentic cache result for {item.keyword!r}")
        result_by_position[item.position] = AIKeywordAnalysis(
            keyword=item.keyword,
            detected_language=canonical_result.detected_language,
            language_group=canonical_result.language_group,
            semantic_bucket=canonical_result.semantic_bucket,
            decision_rule=canonical_result.decision_rule,
            reason=canonical_result.reason,
            confidence=canonical_result.confidence,
            english_gloss=canonical_result.english_gloss,
            status="AI_REUSED_CANONICAL",
        )

    output = []
    for item in pre_ai_items:
        result = result_by_position.get(item.position)
        if result is None:
            raise AIKeywordClassifierError(f"Missing agentic cache result for {item.keyword!r}")
        output.append({
            "NeedsAI": item.needs_ai,
            "PreAIAction": item.action,
            "PreAIRule": item.rule,
            "PreAIReason": item.reason,
            "CanonicalKeyword": item.canonical_keyword,
            "DetectedLanguage": result.detected_language,
            "LanguageGroup": result.language_group,
            "AISemanticBucket": result.semantic_bucket,
            "AIDecisionRule": result.decision_rule,
            "AIReason": result.reason,
            "AIConfidence": result.confidence,
            "AIEnglishGloss": result.english_gloss,
            "AIStatus": result.status,
        })
    frame = pd.DataFrame(output, index=df.index)
    status_counts = frame["AIStatus"].value_counts().to_dict()
    stats = getattr(service, "stats", {}) or {}
    print(
        "AI keyword classification summary: "
        f"provider={classifier_config['provider']}, model={classifier_config['model']}, "
        f"total_rows={len(df)}, "
        f"cache_hit={status_counts.get('AI_CACHE_HIT', 0)}, "
        f"classified=0, "
        f"reused={status_counts.get('AI_REUSED_CANONICAL', 0)}, "
        f"pre_skipped={status_counts.get('AI_SKIPPED_PREFILTER', 0)}, "
        f"api_candidates={stats.get('api_candidates', 0)}, "
        "api_batches=0, key_pool_size=0, max_workers=0, "
        "avg_batch_seconds=0.00, slowest_batch_seconds=0.00, "
        "retries=0, rate_limit_errors=0, timeout_errors=0, "
        f"total_ai_seconds={stats.get('total_ai_seconds', 0.0):.2f}"
    )
    return frame
