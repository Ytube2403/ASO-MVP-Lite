from dataclasses import dataclass
from contextlib import closing
import json
import os
import sqlite3
import time

import pandas as pd

from shared import agentic_keyword_classifier

from .cache import config_hash
from .matcher import normalize_filter_text, tokenize


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SUITABILITY_COLUMNS = [
    "MetadataEligible",
    "AdsEligible",
    "ResearchOnly",
    "SuitabilityBucket",
    "SuitabilityRule",
    "SuitabilityReason",
    "SuitabilityConfidence",
    "SuitabilitySource",
]

DEFAULT_METADATA_SUITABILITY = {
    "enabled": True,
    "cache_path": ".cache/agentic_keyword_analysis.sqlite3",
    "provider": "antigravity_subagent",
    "model": "metadata_suitability_v1",
    "prompt_version": "metadata_suitability_v1",
    "single_token_policy": {
        "enabled": True,
        "default_action": "research_only",
        "keep_terms": [],
        "block_terms": [],
    },
    "audit_min_volume": 20,
}

BLOCKED_BUCKETS = {
    "Dropped",
    "Language Mismatch Audit",
    "Manual Review",
}

BLOCKED_DECISION_RULES = {
    "competitor_brand",
    "risky_ip",
    "ai_classic_ip",
    "platform_style_risk",
    "platform_affiliation",
    "platform_only",
    "irrelevant_intent",
    "noise_only",
    "typo_truncated_broken",
    "truncated_keyword",
    "unnatural",
    "foreign_language_mismatch",
    "manual_review",
}

SINGLE_TOKEN_TOO_BROAD = "single_token_too_broad"
SUITABILITY_RESEARCH_ONLY = "suitability_research_only"


@dataclass
class SuitabilityAnalysis:
    keyword: str
    metadata_eligible: bool
    ads_eligible: bool
    research_only: bool
    suitability_bucket: str
    decision_rule: str
    reason: str
    confidence: float
    source: str = "subagent"


def suitability_policy(config=None):
    config = config or {}
    policy = dict(DEFAULT_METADATA_SUITABILITY)
    override = dict(config.get("metadata_suitability", {}) or {})
    policy.update(override)
    single = dict(DEFAULT_METADATA_SUITABILITY["single_token_policy"])
    single.update((override.get("single_token_policy", {}) or {}))
    policy["single_token_policy"] = single
    return policy


def _bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _decision_rule(row):
    for key in ("DecisionRule", "AIDecisionRule", "HardFilterRule"):
        value = str(row.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _text(row, key, default=""):
    value = row.get(key, default)
    if pd.isna(value):
        return default
    return str(value or default).strip()


def _is_blocked(row):
    bucket = _text(row, "Bucket")
    if bucket in BLOCKED_BUCKETS:
        return True
    if _text(row, "LanguageGroup").upper() in {"FOREIGN", "UNKNOWN"}:
        return True
    naturalness = _text(row, "NaturalnessFlag", "OK")
    if naturalness and naturalness != "OK":
        return True
    rule = _decision_rule(row)
    if rule in BLOCKED_DECISION_RULES:
        return True
    if str(row.get("HardFilterRule", "") or "").strip():
        return True
    return False


def _single_token_keep_terms(config, policy):
    terms = set()
    single = policy.get("single_token_policy", {}) or {}
    for key in ("intent_core_terms", "intent_core_words"):
        for term in (config or {}).get(key, []) or []:
            parts = tokenize(term)
            if len(parts) == 1:
                terms.add(parts[0])
    for term in single.get("keep_terms", []) or []:
        normalized = normalize_filter_text(term)
        if normalized:
            terms.add(normalized)
    for term in ((config or {}).get("metadata_selector", {}) or {}).get("single_token_keep", []) or []:
        normalized = normalize_filter_text(term)
        if normalized:
            terms.add(normalized)
    return terms


def _single_token_block_terms(policy):
    return {
        normalize_filter_text(term)
        for term in (policy.get("single_token_policy", {}) or {}).get("block_terms", []) or []
        if normalize_filter_text(term)
    }


def _result(metadata, ads, research, bucket, rule, reason, confidence=1.0, source="deterministic"):
    return {
        "MetadataEligible": bool(metadata),
        "AdsEligible": bool(ads),
        "ResearchOnly": bool(research),
        "SuitabilityBucket": bucket,
        "SuitabilityRule": rule,
        "SuitabilityReason": reason,
        "SuitabilityConfidence": round(float(confidence), 4),
        "SuitabilitySource": source,
    }


def _from_analysis(analysis):
    return _result(
        analysis.metadata_eligible,
        analysis.ads_eligible,
        analysis.research_only,
        analysis.suitability_bucket,
        analysis.decision_rule,
        analysis.reason,
        analysis.confidence,
        analysis.source or "subagent_cache",
    )


def evaluate_metadata_suitability(row, config=None, cached_analysis=None):
    policy = suitability_policy(config)
    if not policy.get("enabled", True):
        return _result(True, True, False, "Eligible", "suitability_disabled", "Metadata suitability gate disabled")

    if _is_blocked(row):
        return _result(False, False, True, "Research Only", "blocked_risk", "Blocked by risk/language/manual-review gate")

    keyword = str(row.get("Keyword", "") or "")
    tokens = tokenize(keyword)
    single_policy = policy.get("single_token_policy", {}) or {}
    if single_policy.get("enabled", True) and len(tokens) == 1:
        token = tokens[0]
        if token in _single_token_keep_terms(config or {}, policy):
            return _result(True, True, False, "Eligible", "single_token_keep", "Single-token atomic app/platform intent")
        if token in _single_token_block_terms(policy):
            return _result(False, False, True, "Research Only", SINGLE_TOKEN_TOO_BROAD, "Single-token feature/style term is too broad for metadata or ads")
        if cached_analysis:
            return _from_analysis(cached_analysis)
        if ((config or {}).get("metadata_selector", {}) or {}).get("exclude_single_token_from_main", False):
            return _result(False, False, True, "Research Only", SUITABILITY_RESEARCH_ONLY, "Legacy single-token metadata selector policy keeps this keyword out of metadata")
        if str(single_policy.get("default_action", "research_only")).strip().lower() == "eligible":
            return _result(True, True, False, "Eligible", "single_token_default_eligible", "Single-token keyword allowed by default policy")
        return _result(False, False, True, "Research Only", SUITABILITY_RESEARCH_ONLY, "Single-token keyword needs suitability audit before metadata or ads")

    if cached_analysis:
        return _from_analysis(cached_analysis)
    return _result(True, True, False, "Eligible", "suitability_default_eligible", "Keyword passed deterministic suitability gate")


def needs_suitability_audit(row, config=None):
    policy = suitability_policy(config)
    if not policy.get("enabled", True) or _is_blocked(row):
        return False
    tokens = tokenize(str(row.get("Keyword", "") or ""))
    if not tokens:
        return False
    if len(tokens) == 1:
        token = tokens[0]
        if token in _single_token_keep_terms(config or {}, policy):
            return False
        if token in _single_token_block_terms(policy):
            return False
        return True
    bucket = str(row.get("Bucket", "") or "").strip()
    if bucket in {"Feature Keywords", "System Keywords"} and _number(row.get("Volume"), 0) >= _number(policy.get("audit_min_volume"), 20):
        return True
    return False


def _context_hash(config, app_profile=None):
    relevant = {
        "app_context": agentic_keyword_classifier._context_hash(config or {}, app_profile or {}),
        "metadata_suitability": (config or {}).get("metadata_suitability", {}),
        "app_id": (config or {}).get("app_id", ""),
        "market": (config or {}).get("market", ""),
    }
    return config_hash(relevant)


def _cache_key(keyword, config, market, app_profile=None):
    policy = suitability_policy(config)
    return (
        str(policy.get("provider", "antigravity_subagent")),
        str(policy.get("model", "metadata_suitability_v1")),
        str(policy.get("prompt_version", "metadata_suitability_v1")),
        str((config or {}).get("app_id", "")),
        str(market or (config or {}).get("market", "")),
        _context_hash(config or {}, app_profile or {}),
        normalize_filter_text(keyword),
    )


class SuitabilityCache:
    def __init__(self, cache_path, config=None, app_profile=None, market="", clock=None):
        self.cache_path = cache_path
        self.config = config or {}
        self.app_profile = app_profile or {}
        self.market = market or self.config.get("market", "")
        self.clock = clock or time.time
        self._initialize_cache()

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
                CREATE TABLE IF NOT EXISTS keyword_suitability_analysis (
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    market TEXT NOT NULL,
                    context_hash TEXT NOT NULL,
                    normalized_keyword TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    metadata_eligible INTEGER NOT NULL,
                    ads_eligible INTEGER NOT NULL,
                    research_only INTEGER NOT NULL,
                    suitability_bucket TEXT NOT NULL,
                    decision_rule TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
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

    def get(self, keyword):
        key = _cache_key(keyword, self.config, self.market, self.app_profile)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT keyword, metadata_eligible, ads_eligible, research_only,
                       suitability_bucket, decision_rule, reason, confidence, source
                FROM keyword_suitability_analysis
                WHERE provider = ? AND model = ? AND prompt_version = ?
                  AND app_id = ? AND market = ? AND context_hash = ?
                  AND normalized_keyword = ?
                """,
                key,
            ).fetchone()
        if not row:
            return None
        return SuitabilityAnalysis(
            keyword=row[0],
            metadata_eligible=bool(row[1]),
            ads_eligible=bool(row[2]),
            research_only=bool(row[3]),
            suitability_bucket=row[4],
            decision_rule=row[5],
            reason=row[6],
            confidence=float(row[7]),
            source=row[8],
        )

    def store(self, analysis, raw_json):
        key = _cache_key(analysis.keyword, self.config, self.market, self.app_profile)
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO keyword_suitability_analysis (
                    provider, model, prompt_version, app_id, market, context_hash,
                    normalized_keyword, keyword, metadata_eligible, ads_eligible,
                    research_only, suitability_bucket, decision_rule, reason,
                    confidence, source, raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, model, prompt_version, app_id, market, context_hash, normalized_keyword)
                DO UPDATE SET
                    keyword = excluded.keyword,
                    metadata_eligible = excluded.metadata_eligible,
                    ads_eligible = excluded.ads_eligible,
                    research_only = excluded.research_only,
                    suitability_bucket = excluded.suitability_bucket,
                    decision_rule = excluded.decision_rule,
                    reason = excluded.reason,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    raw_json = excluded.raw_json,
                    updated_at = excluded.updated_at
                """,
                (
                    *key,
                    analysis.keyword,
                    int(bool(analysis.metadata_eligible)),
                    int(bool(analysis.ads_eligible)),
                    int(bool(analysis.research_only)),
                    analysis.suitability_bucket,
                    analysis.decision_rule,
                    analysis.reason,
                    float(analysis.confidence),
                    analysis.source or "subagent",
                    json.dumps(raw_json, ensure_ascii=False, sort_keys=True),
                    self.clock(),
                ),
            )
            connection.commit()


def apply_metadata_suitability(df, config=None, app_profile=None, market="", cache_path=""):
    if df is None:
        return df
    frame = df.copy()
    policy = suitability_policy(config)
    cache = None
    if policy.get("enabled", True):
        resolved_cache = cache_path or policy.get("cache_path") or ".cache/agentic_keyword_analysis.sqlite3"
        if not os.path.isabs(resolved_cache):
            resolved_cache = os.path.join(PROJECT_ROOT, resolved_cache)
        cache = SuitabilityCache(resolved_cache, config=config, app_profile=app_profile, market=market or (config or {}).get("market", ""))

    results = []
    for _, row in frame.iterrows():
        row_dict = row.to_dict()
        cached = cache.get(row_dict.get("Keyword", "")) if cache else None
        results.append(evaluate_metadata_suitability(row_dict, config, cached))
    for column in SUITABILITY_COLUMNS:
        frame[column] = [result[column] for result in results]
    return frame
