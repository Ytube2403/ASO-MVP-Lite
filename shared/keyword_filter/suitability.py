from dataclasses import dataclass
from contextlib import closing
import json
import os
import re
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
    "audit_min_volume": 5,
    # Mirrors agentic_keyword_classifier's fail_on_api_error: this module is cache-only
    # for keywords needing a subagent audit, so a missing entry must be a loud error
    # -- not a silent "Eligible" default -- or the audit step is a no-op and nothing
    # ever prompts a subagent to actually run (tools/suitability_cache_helper.py).
    "fail_on_missing_audit": True,
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
SUITABILITY_PENDING_AUDIT = "suitability_pending_audit"


class SuitabilityAuditError(RuntimeError):
    pass


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
        # Use _text (NaN-safe) rather than `row.get(key, "") or ""`: pandas round-trips
        # an empty string through CSV (to_csv -> read_csv) as float NaN, and
        # `bool(float("nan"))` is True in Python, so a raw `x or default` pattern keeps
        # the NaN and str()s it into the literal string "nan" instead of falling back.
        value = _text(row, key)
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
    # NaN-safe (see _decision_rule): a raw `row.get(...) or ""` here would treat every
    # CSV-round-tripped empty HardFilterRule as the literal truthy string "nan" and
    # block every keyword -- this previously made tools/suitability_cache_helper.py's
    # find-misses (which reads the exported CSV) silently disagree with the live
    # in-process pipeline run (which never round-trips through CSV).
    if _text(row, "HardFilterRule"):
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
    normalized_kw = normalize_filter_text(keyword)
    suitability_config = config.get("metadata_suitability", {}) if config else {}
    keep_terms = {normalize_filter_text(term) for term in suitability_config.get("keep_terms", []) or [] if normalize_filter_text(term)}
    overrides = (config or {}).get("user_overrides", {}) or {}
    keep_terms.update({normalize_filter_text(term) for term in overrides.get("suitability_keep_terms", []) or [] if normalize_filter_text(term)})
    if normalized_kw in keep_terms:
        return _result(True, True, False, "Eligible", "user_override_keep", "Keyword explicitly allowed by user suitability configuration")
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
    # A multi-word keyword the deterministic gates didn't already resolve (blocked/
    # single-token) still needs a real subagent verdict if it matches
    # needs_suitability_audit's own criteria (audited buckets above min volume).
    # Defaulting this to "Eligible" when uncached would make the whole audit step a
    # silent no-op -- nothing would ever surface that a subagent run is needed. Return
    # a distinguishable pending state instead; apply_metadata_suitability decides
    # whether to fail loud on it.
    if needs_suitability_audit(row, config):
        return _result(
            False, False, True, "Pending Audit", SUITABILITY_PENDING_AUDIT,
            "Keyword requires subagent suitability audit before metadata/ads eligibility",
            confidence=0.0, source="pending",
        )
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
    eligible_buckets = {
        "Feature Keywords",
        "System Keywords",
        "Broad Expansion",
        "Consider Keywords",
        "Style Keywords",
        "Generic Style Reserve",
        "Game Keywords"
    }
    if bucket not in eligible_buckets:
        return False

    if _number(row.get("Volume"), 0) < _number(policy.get("audit_min_volume"), 5):
        return False

    decision_rule = _decision_rule(row).strip().lower()

    # AI-bucketed terms always get audited
    if decision_rule.startswith("ai_"):
        return True

    # Explicitly declared feature/core terms skip audit to prevent blocking legitimate
    # app specifics. They usually land in Feature/System with deterministic rules
    # (e.g. "feature_keywords", "intent_core_terms").
    # If it landed in a non-feature bucket (Broad, Consider), it's not a core feature
    # and should be audited.
    if bucket not in {"Feature Keywords", "System Keywords", "Core Intent Final"}:
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


def _write_candidate_pool_csv(frame, config, market):
    # tools/suitability_cache_helper.py's find-misses needs a POST-classification CSV
    # (Keyword/Bucket/DecisionRule/Volume) to know which keywords need an audit -- the
    # raw input CSV doesn't have those columns yet. Without this, a pipeline failure
    # here leaves nothing to feed into find-misses. Export deterministically so the
    # error message can point straight at a ready-to-use file.
    app_id = str((config or {}).get("app_id", "") or "app")
    safe_app_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", app_id).strip("_") or "app"
    safe_market = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(market or (config or {}).get("market", "")) or "default")
    directory = os.path.join(PROJECT_ROOT, ".cache", "candidate_pools")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{safe_app_id}_{safe_market}_candidates.csv")
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


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
    pending_keywords = []
    for _, row in frame.iterrows():
        row_dict = row.to_dict()
        cached = cache.get(row_dict.get("Keyword", "")) if cache else None
        result = evaluate_metadata_suitability(row_dict, config, cached)
        if result["SuitabilityRule"] == SUITABILITY_PENDING_AUDIT:
            pending_keywords.append(str(row_dict.get("Keyword", "")))
        results.append(result)

    if pending_keywords and policy.get("fail_on_missing_audit", True):
        candidate_pool_path = _write_candidate_pool_csv(frame, config, market)
        sample = ", ".join(pending_keywords[:10])
        more = f" (+{len(pending_keywords) - 10} more)" if len(pending_keywords) > 10 else ""
        raise SuitabilityAuditError(
            f"Metadata suitability audit is cache-only: {len(pending_keywords)} keyword(s) need a "
            "subagent suitability review before this pipeline can run. "
            f"Candidate pool exported to {candidate_pool_path} -- run "
            f"'python tools/suitability_cache_helper.py find-misses --app <alias> --csv {candidate_pool_path} "
            "--market <MARKET>' then prepare-batches/save-results/verify-cache "
            f"(see .agents/skills/warm-suitability-cache/SKILL.md). Pending: {sample}{more}"
        )

    for column in SUITABILITY_COLUMNS:
        frame[column] = [result[column] for result in results]
    return frame
