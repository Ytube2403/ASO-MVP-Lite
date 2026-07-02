from dataclasses import dataclass, field
import re

from shared import text_dedup

from .matcher import normalize_filter_text
from .scoring import is_low_volume_tier, is_shortlist_volume_eligible, safe_reach_ceiling


DEFAULT_MAIN_QUOTA = {
    "core_intent": 25,
    "core_feature": 5,
    "broad_expansion": 5,
    "consider": 5,
}

DEFAULT_METADATA_SELECTOR = {
    "enabled": True,
    "target_count": 40,
    "cluster_cap": 3,
    "cluster_similarity_threshold": 0.5,
    "cluster_generic_token_ratio": 0.30,
    "quality_min_utility": 0.45,
    "safe_backfill_min_utility": 0.25,
    "quality_min_balanced_score": 0.40,
    "quality_min_relevancy": 0.45,
    "quality_min_volume": 6.0,
    "quality_min_reach": 1.0,
    "generic_safe_descriptors": ["retro", "classic"],
}

DEFAULT_SECTION_BUCKETS = {
    "Core Intent Final": ["Core Intent Final"],
    "Feature Keywords": ["Feature Keywords", "System Keywords"],
    "Broad Expansion": ["Broad Expansion", "Style Keywords", "Generic Style Reserve", "Game Keywords"],
    "Consider Keywords": ["Consider Keywords"],
}

DEFAULT_RISK_DECISION_RULES = {
    "competitor_brand",
    "risky_ip",
    "ambiguous_brand",
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
    "secondary_language_handling",
}

_CORE_DECLARED_RISK_OVERRIDE_RULES = {
    "risky_ip_core_override",
    "platform_risk_core_override",
    "platform_only_core_override",
}

BLOCKED_BUCKETS = {
    "Dropped",
    "Language Mismatch Audit",
    "Manual Review",
}

RESEARCH_ONLY_BUCKETS = {
    "Dropped",
    "Language Mismatch Audit",
    "Manual Review",
}

NOT_SELECTED_LOG_COLUMNS = [
    "Keyword",
    "EN",
    "Volume",
    "BalancedScore",
    "RelevancyScore",
    "Bucket",
    "Section",
    "DecisionRule",
    "Reason",
    "NotSelectedReason",
    "KeptKeyword",
    "UtilityScore",
    "ClusterId",
    "ClusterRank",
    "SelectionPhase",
]

QUALITY_LOG_COLUMNS = [
    "Level",
    "Code",
    "Message",
    "TargetCount",
    "SelectedCount",
]

_STOPWORDS = {
    "a",
    "an",
    "and",
    "app",
    "apps",
    "best",
    "download",
    "for",
    "free",
    "new",
    "of",
    "the",
    "to",
}

_TOKEN_SYNONYMS = {
    "apps": "app",
    "classic": "retro",
    "classics": "retro",
    "emulador": "emulator",
    "emuladores": "emulator",
    "emulators": "emulator",
    "emu": "emulator",
    "games": "game",
    "oldschool": "retro",
    "nostalgia": "retro",
    "nostalgic": "retro",
    "vintage": "retro",
}


@dataclass
class MainShortlistResult:
    core: list
    feature: list
    broad: list
    consider: list
    dedup_log: list
    selected_rows: list = field(default_factory=list)
    not_selected_log: list = field(default_factory=list)
    diversity_log: list = field(default_factory=list)
    quality_log: list = field(default_factory=list)

    @property
    def all_rows(self):
        if self.selected_rows:
            return self.selected_rows
        return self.core + self.feature + self.broad + self.consider

    def legacy_tuple(self, include_feature=True):
        if include_feature:
            return self.core, self.feature, self.broad, self.consider, self.dedup_log
        return self.core, self.broad, self.consider, self.dedup_log


class MainKeywordShortlistBuilder:
    """Select metadata-safe keywords by utility and diversity behind one shared interface."""

    def __init__(self, config):
        self.config = config or {}
        self.selector_config = dict(DEFAULT_METADATA_SELECTOR)
        self.selector_config.update(self.config.get("metadata_selector", {}) or {})
        shortlist_config = self.config.get("main_shortlist_builder", {}) or {}
        self.section_buckets = dict(DEFAULT_SECTION_BUCKETS)
        self.section_buckets.update(shortlist_config.get("section_buckets", {}) or {})
        self.not_selected_log = []
        self.diversity_log = []
        self.quality_log = []

    def build(self, df_all):
        if df_all is None:
            raise ValueError("df_all is required")
        if not self.selector_config.get("enabled", True):
            return self._legacy_bucket_quota_build(df_all)

        target_count = int(self.selector_config.get("target_count") or sum(self._main_quotas().values()))
        cluster_cap = max(1, int(self.selector_config.get("cluster_cap") or 1))
        quality_min = _number(self.selector_config.get("quality_min_utility"), 0.45)
        safe_backfill_min = _number(self.selector_config.get("safe_backfill_min_utility"), 0.25)

        rows = self._candidate_records(df_all)
        if not rows:
            self._add_quality_warning("SAFE_POOL_EXHAUSTED", "No metadata-safe keyword candidates were available.", target_count, 0)
            return self._result_from_selected([], [])

        market_stats = self._market_stats(df_all)
        safe_rows = []
        for index, row in enumerate(rows):
            row["_SourceIndex"] = index
            row["Section"] = self._section_for_row(row)
            safe, reason = self._is_metadata_safe(row)
            row["UtilityScore"] = round(self._utility_score(row, market_stats), 4)
            row["ClusterId"] = self._cluster_key(_text_value(row, "Keyword"))
            row["SelectionReason"] = ""
            row["DiversityPenalty"] = 0.0
            row["ClusterRank"] = ""
            if safe:
                safe_rows.append(row)
            else:
                self._log_not_selected(row, reason)

        representatives, dedup_log = self._deduplicate_by_utility(safe_rows)
        selected, skipped_by_cluster = self._select_by_utility_and_diversity(
            representatives,
            target_count,
            cluster_cap,
            quality_min,
            safe_backfill_min,
        )
        for row in skipped_by_cluster:
            self._log_not_selected(row, "CLUSTER_CAP_REACHED")

        selected_keys = {self._row_identity(row) for row in selected}
        for row in representatives:
            if self._row_identity(row) in selected_keys:
                continue
            if _number(row.get("UtilityScore"), 0) < safe_backfill_min:
                self._log_not_selected(row, "BELOW_SAFE_BACKFILL_FLOOR")
            elif not self._quality_phase_score_eligible(row):
                self._log_not_selected(row, "BELOW_SCORE_FLOOR")
            elif not self._quality_phase_relevancy_eligible(row):
                self._log_not_selected(row, "BELOW_RELEVANCY_FLOOR")
            elif not self._quality_phase_demand_eligible(row):
                self._log_not_selected(row, "BELOW_DEMAND_FLOOR")
            else:
                self._log_not_selected(row, "LOW_METADATA_UTILITY")

        if len(selected) < target_count:
            self._add_quality_warning(
                "SAFE_POOL_EXHAUSTED",
                "Safe-only selector could not fill target count without using blocked or over-crowded keywords.",
                target_count,
                len(selected),
            )

        return self._result_from_selected(selected, dedup_log)

    def _candidate_records(self, df_all):
        if df_all is None or df_all.empty:
            return []
        return [dict(row) for row in df_all.to_dict("records")]

    def _deduplicate_by_utility(self, rows):
        groups = {}
        for row in rows:
            groups.setdefault(self._dedup_key(_text_value(row, "Keyword")), []).append(row)

        representatives = []
        dedup_log = []
        for cluster_number, group_rows in enumerate(groups.values(), start=1):
            winner = max(group_rows, key=self._utility_sort_key)
            variants = [row for row in group_rows if row is not winner]
            winner["MergedVariants"] = ", ".join(_text_value(row, "Keyword") for row in variants if _text_value(row, "Keyword"))
            representatives.append(winner)
            cluster_id = f"01_Main_Keyword_Shortlist:{cluster_number:04d}"
            for row in variants:
                dedup_log.append(
                    {
                        "Table": "01_Main_Keyword_Shortlist",
                        "Action": "PRUNED",
                        "ClusterId": cluster_id,
                        "DedupRule": "metadata_utility_key",
                        "Confidence": 0.95,
                        "RemovedKeyword": _text_value(row, "Keyword"),
                        "RemovedVolume": row.get("Volume", 0),
                        "KeptKeyword": _text_value(winner, "Keyword"),
                        "KeptVolume": winner.get("Volume", 0),
                        "OriginalSection": _text_value(row, "Bucket", "Section"),
                        "NormalizedKey": self._dedup_key(_text_value(row, "Keyword")),
                        "BalancedScore": row.get("BalancedScore", 0),
                        "Note": "DUPLICATE_REPRESENTATIVE_KEPT: utility-first representative kept in main metadata pool",
                    }
                )
                self._log_not_selected(row, "DUPLICATE_REPRESENTATIVE_KEPT", kept=winner)
        return representatives, dedup_log

    def _select_by_utility_and_diversity(self, rows, target_count, cluster_cap, quality_min, safe_backfill_min):
        ordered = sorted(rows, key=self._utility_sort_key, reverse=True)
        selected = []
        skipped_by_cluster = []
        cluster_counts = {}
        cluster_reps = {}
        cluster_threshold = _number(self.selector_config.get("cluster_similarity_threshold"), 0.5)
        generic_ratio = _number(self.selector_config.get("cluster_generic_token_ratio"), 0.30)

        # Tokens that show up in most candidates (e.g. "emulator", "game", "retro" for
        # an emulator app) carry almost no distinguishing power: two keywords sharing
        # only these words ("arcade games emulator" vs "n64 game emulator") would
        # otherwise look ~50% similar despite targeting completely different platforms.
        # Drop them before computing similarity so clustering keys off the words that
        # actually separate one keyword's intent from another's (n64, nes, gba, arcade...).
        token_doc_count = {}
        row_token_cache = {}
        for row in ordered:
            tokens = set(self._token_key(_text_value(row, "Keyword"), remove_digits=True).split())
            row_token_cache[id(row)] = tokens
            for token in tokens:
                token_doc_count[token] = token_doc_count.get(token, 0) + 1
        pool_size = max(len(ordered), 1)
        generic_tokens = {token for token, count in token_doc_count.items() if count / pool_size > generic_ratio}

        def distinguishing_tokens(row):
            tokens = row_token_cache.get(id(row))
            if tokens is None:
                tokens = set(self._token_key(_text_value(row, "Keyword"), remove_digits=True).split())
            filtered = tokens - generic_tokens
            return filtered or tokens

        def resolve_cluster(row):
            # Near-duplicate long-tail phrases rarely share an *identical* token set
            # (e.g. "console game emulator" vs "game emulator console gaming"), so an
            # exact-match cluster key never groups them and cluster_cap never triggers.
            # Group dynamically by Jaccard token overlap (on distinguishing tokens only)
            # against clusters seen so far.
            tokens = distinguishing_tokens(row)
            best_id, best_sim = None, 0.0
            for cluster_id, rep_tokens in cluster_reps.items():
                union = tokens | rep_tokens
                if not union:
                    continue
                sim = len(tokens & rep_tokens) / len(union)
                if sim > best_sim:
                    best_sim, best_id = sim, cluster_id
            if best_id is not None and best_sim >= cluster_threshold:
                return best_id
            new_id = f"C{len(cluster_reps) + 1:04d}"
            cluster_reps[new_id] = tokens
            return new_id

        def try_select(row, quota_status, phase):
            if len(selected) >= target_count:
                return False
            cluster_id = resolve_cluster(row)
            row["ClusterId"] = cluster_id
            if cluster_counts.get(cluster_id, 0) >= cluster_cap:
                skipped_by_cluster.append(row)
                self.diversity_log.append(
                    {
                        "Keyword": _text_value(row, "Keyword"),
                        "ClusterId": cluster_id,
                        "UtilityScore": row.get("UtilityScore", 0),
                        "Reason": "CLUSTER_CAP_REACHED",
                    }
                )
                return False
            cluster_rank = cluster_counts.get(cluster_id, 0) + 1
            cluster_counts[cluster_id] = cluster_rank
            row["ClusterRank"] = cluster_rank
            row["DiversityPenalty"] = round((cluster_rank - 1) * 0.10, 4)
            row["QuotaStatus"] = quota_status
            row["FillSource"] = ""
            row["FillReason"] = "" if quota_status == "EXACT" else phase
            row["SelectionReason"] = phase
            selected.append(row)
            return True

        for row in ordered:
            if (
                _number(row.get("UtilityScore"), 0) >= quality_min
                and self._quality_phase_score_eligible(row)
                and self._quality_phase_relevancy_eligible(row)
                and self._quality_phase_demand_eligible(row)
            ):
                try_select(row, "EXACT", "UTILITY_SELECTED")
            if len(selected) >= target_count:
                break

        if len(selected) < target_count:
            selected_ids = {self._row_identity(row) for row in selected}
            for row in ordered:
                if self._row_identity(row) in selected_ids:
                    continue
                if _number(row.get("UtilityScore"), 0) < safe_backfill_min:
                    continue
                if not self._quality_phase_score_eligible(row):
                    continue
                if not self._quality_phase_relevancy_eligible(row):
                    continue
                if not self._quality_phase_demand_eligible(row):
                    continue
                if try_select(row, "SAFE_BACKFILL", "SAFE_ONLY_BACKFILL"):
                    selected_ids.add(self._row_identity(row))
                if len(selected) >= target_count:
                    break

        return selected, skipped_by_cluster

    def _utility_score(self, row, market_stats):
        relevancy = _clamp01(row.get("RelevancyScore", 0))
        balanced = _clamp01(row.get("BalancedScore", 0))
        volume_n = _clamp01(row.get("VolumeN", 0))
        reach = _number(row.get("MaximumReach", 0))
        reach_n = _clamp01(reach / market_stats.get("max_reach", reach or 1)) if reach > 0 else 0.0
        volume_signal = max(volume_n, reach_n)
        rank_signal = _clamp01(row.get("CurrentRankN", 0))
        if rank_signal == 0:
            rank_signal = self._rank_signal(row)
        expansion = _clamp01(row.get("ExpansionValue", 0))

        utility = (
            relevancy * 0.40
            + balanced * 0.30
            + volume_signal * 0.20
            + rank_signal * 0.05
            + expansion * 0.05
        )
        utility -= self._intent_penalty(row)
        utility -= self._risk_penalty(row)
        return max(0.0, min(1.0, utility))

    def _intent_penalty(self, row):
        bucket = _text_value(row, "Bucket")
        if bucket == "Consider Keywords":
            return 0.04
        if bucket in {"Broad Expansion", "Style Keywords", "Generic Style Reserve"}:
            return 0.03
        return 0.0

    def _risk_penalty(self, row):
        decision_rule = _decision_rule(row)
        if decision_rule == "ambiguous_brand" and self._ambiguous_brand_is_generic_descriptor(row):
            return 0.02
        return 0.0

    def _rank_signal(self, row):
        rank = _number(row.get("Rank_numeric", row.get("Rank", 999)), 999)
        if rank <= 10:
            return 1.0
        if rank <= 25:
            return 0.8
        if rank <= 50:
            return 0.55
        if rank <= 100:
            return 0.30
        return 0.0

    def _quality_phase_demand_eligible(self, row):
        min_volume = _number(self.selector_config.get("quality_min_volume"), 6.0)
        min_reach = _number(self.selector_config.get("quality_min_reach"), 1.0)
        if _number(row.get("Volume"), 0) >= min_volume:
            return True
        if _number(row.get("MaximumReach"), 0) >= min_reach:
            return True
        return False

    def _quality_phase_score_eligible(self, row):
        min_score = _number(self.selector_config.get("quality_min_balanced_score"), 0.40)
        return _number(row.get("BalancedScore"), 0) >= min_score

    def _quality_phase_relevancy_eligible(self, row):
        min_relevancy = _number(self.selector_config.get("quality_min_relevancy"), 0.45)
        return _number(row.get("RelevancyScore"), 0) >= min_relevancy

    def _is_metadata_safe(self, row):
        bucket = _text_value(row, "Bucket")
        if bucket in BLOCKED_BUCKETS:
            return False, "BLOCKED_RISK"
        if _text_value(row, "LanguageGroup") in {"FOREIGN", "UNKNOWN"}:
            return False, "BLOCKED_RISK"
        # MIXED is deliberately NOT in the blanket block above. classify_keyword already
        # makes a market-aware decision for MIXED-language rows via get_market_language_policy's
        # mixed_allowed flag: Bucket="Manual Review" (already caught by BLOCKED_BUCKETS above)
        # when the market disallows it, or a normal eligible bucket ("Consider Keywords" via
        # mixed_language_consider, or whatever an earlier risk-flag/override branch decided)
        # when it's fine. For a non-English market, mixing the primary language with an English
        # loanword ("ds emulador", "arcade games emulator") is completely normal search behavior,
        # not a language-mismatch problem -- re-blocking it here regardless of that decision was
        # silently starving non-English markets' shortlists of otherwise-good keywords.
        naturalness = _text_value(row, "NaturalnessFlag", default="OK")
        if naturalness and naturalness != "OK":
            return False, "BLOCKED_RISK"

        decision_rule = _decision_rule(row)
        if decision_rule == "ambiguous_brand" and self._ambiguous_brand_is_generic_descriptor(row):
            return True, ""
        if decision_rule in _CORE_DECLARED_RISK_OVERRIDE_RULES:
            # classify_keyword already trusted the app's own intent_core_terms
            # declaration over an incidental brand/platform-name match (see
            # _core_declared_risk_terms in classifier.py). Don't re-derive risk from
            # the raw HardFilterRule audit flag below, which doesn't know about that
            # override and would otherwise block it again.
            return True, ""
        if decision_rule in self._blocked_rules():
            return False, "BLOCKED_RISK"
        if self._reason_indicates_metadata_risk(row):
            return False, "BLOCKED_RISK"
        if _text_value(row, "HardFilterRule"):
            return False, "BLOCKED_RISK"
        if not self._quality_eligible(row):
            return False, "BELOW_SAFE_BACKFILL_FLOOR"
        return True, ""

    def _blocked_rules(self):
        configured = set((self.config.get("metadata_selector", {}) or {}).get("blocked_decision_rules", []) or [])
        if configured:
            return configured
        return set(DEFAULT_RISK_DECISION_RULES)

    def _ambiguous_brand_is_generic_descriptor(self, row):
        keyword = normalize_filter_text(_text_value(row, "Keyword"))
        ambiguous_terms = self.config.get("ambiguous_brand_terms", []) or []
        generic = {
            normalize_filter_text(term)
            for term in self.selector_config.get("generic_safe_descriptors", []) or []
            if normalize_filter_text(term)
        }
        matched = [
            normalize_filter_text(term)
            for term in ambiguous_terms
            if normalize_filter_text(term) and re.search(r"\b" + re.escape(normalize_filter_text(term)) + r"\b", keyword)
        ]
        return bool(matched) and all(term in generic for term in matched)

    def _reason_indicates_metadata_risk(self, row):
        reason = " ".join(
            _text_value(row, key).lower()
            for key in ("Reason", "AIReason", "PreAIReason")
            if _text_value(row, key)
        )
        return any(
            marker in reason
            for marker in (
                "(app_brand_",
                "(brand_",
                "specific classic game title",
                "intellectual property",
            )
        )

    def _section_for_row(self, row):
        bucket = _text_value(row, "Bucket")
        for section, buckets in self.section_buckets.items():
            if bucket in buckets:
                return section
        if bucket in {"Style Keywords", "Generic Style Reserve", "Game Keywords"}:
            return "Broad Expansion"
        return "Consider Keywords"

    def _result_from_selected(self, selected, dedup_log):
        selected = sorted(selected, key=lambda row: int(row.get("_SelectionIndex", 0)) if "_SelectionIndex" in row else 0)
        if selected and all("_SelectionIndex" not in row for row in selected):
            selected = list(selected)

        core = []
        feature = []
        broad = []
        consider = []
        ordered = []
        for index, row in enumerate(selected, start=1):
            entry = dict(row)
            entry.pop("_SourceIndex", None)
            entry["_SelectionIndex"] = index
            section = entry.get("Section", self._section_for_row(entry))
            entry["Section"] = section
            ordered.append(entry)
            if section == "Core Intent Final":
                core.append(entry)
            elif section == "Feature Keywords":
                feature.append(entry)
            elif section == "Broad Expansion":
                broad.append(entry)
            else:
                consider.append(entry)

        return MainShortlistResult(
            core,
            feature,
            broad,
            consider,
            dedup_log,
            selected_rows=ordered,
            not_selected_log=self.not_selected_log,
            diversity_log=self.diversity_log,
            quality_log=self.quality_log,
        )

    def _log_not_selected(self, row, reason, kept=None):
        self.not_selected_log.append(
            {
                "Keyword": _text_value(row, "Keyword"),
                "EN": _text_value(row, "EN"),
                "Volume": row.get("Volume", ""),
                "BalancedScore": row.get("BalancedScore", ""),
                "RelevancyScore": row.get("RelevancyScore", ""),
                "Bucket": _text_value(row, "Bucket"),
                "Section": row.get("Section", self._section_for_row(row)),
                "DecisionRule": _decision_rule(row),
                "Reason": _text_value(row, "Reason", "AIReason", "PreAIReason"),
                "NotSelectedReason": reason,
                "KeptKeyword": _text_value(kept or {}, "Keyword"),
                "UtilityScore": row.get("UtilityScore", ""),
                "ClusterId": row.get("ClusterId", ""),
                "ClusterRank": row.get("ClusterRank", ""),
                "SelectionPhase": row.get("SelectionReason", ""),
            }
        )

    def _add_quality_warning(self, code, message, target_count, selected_count):
        self.quality_log.append(
            {
                "Level": "WARNING",
                "Code": code,
                "Message": message,
                "TargetCount": target_count,
                "SelectedCount": selected_count,
            }
        )

    def _market_stats(self, df_all):
        # Delegate to the same safe_reach_ceiling used for VolumeN normalization in
        # run_pipeline.py, instead of maintaining a second, differently-scoped "safe
        # pool" definition here (this used to exclude by Bucket/BLOCKED_BUCKETS while
        # safe_reach_ceiling excludes by is_competitor/is_irrelevant -- two reach
        # ceilings computed with two different exclusion rules for what should be one
        # consistent reach scale across VolumeN and UtilityScore's reach_n term).
        return {"max_reach": safe_reach_ceiling(df_all, self.config)}

    def _dedup_key(self, keyword):
        norm = text_dedup.normalize_text(keyword)
        bag = self._token_key(keyword, remove_digits=False)
        return bag or norm

    def _cluster_key(self, keyword):
        return self._token_key(keyword, remove_digits=True) or text_dedup.normalize_text(keyword)

    def _token_key(self, keyword, remove_digits):
        tokens = []
        for token in normalize_filter_text(keyword).split():
            if token in _STOPWORDS or (remove_digits and token.isdigit()):
                continue
            token = _TOKEN_SYNONYMS.get(token, token)
            if len(token) > 3 and token.endswith("s"):
                token = token[:-1]
            tokens.append(token)
        tokens = sorted(set(tokens))
        return " ".join(tokens)

    def _quality_gate(self):
        gate = {
            "enabled": False,
            "section_floors": {},
        }
        gate.update(self.config.get("metadata_quality_gate", {}) or {})
        return gate

    def _quality_eligible(self, row):
        gate = self._quality_gate()
        if not gate.get("enabled", False):
            return True
        floors = (gate.get("section_floors", {}) or {}).get(row.get("Section", self._section_for_row(row)), {}) or {}
        if _number(row.get("RelevancyScore", 0)) < _number(floors.get("min_relevancy"), 0):
            return False
        if _number(row.get("BalancedScore", 0)) < _number(floors.get("min_balanced_score"), 0):
            return False
        if _number(row.get("Volume", 0)) < _number(floors.get("min_volume"), 0):
            return False
        if _number(row.get("MaximumReach", 0)) < _number(floors.get("min_reach"), 0):
            return False
        return True

    def _row_identity(self, row):
        return (_text_value(row, "Keyword").lower(), int(_number(row.get("_SourceIndex"), -1)))

    def _utility_sort_key(self, row):
        return (
            _number(row.get("UtilityScore"), 0),
            _number(row.get("RelevancyScore"), 0),
            _number(row.get("BalancedScore"), 0),
            _number(row.get("Volume"), 0),
            -_number(row.get("Rank_numeric", row.get("Rank", 999)), 999),
            -_number(row.get("_SourceIndex"), 0),
        )

    def _main_quotas(self):
        main_quota = ((self.config.get("keyword_quota", {}) or {}).get("main_file", {}) or {})
        return {
            key: int(main_quota.get(key, default) if main_quota.get(key) is not None else default)
            for key, default in DEFAULT_MAIN_QUOTA.items()
        }

    def _legacy_bucket_quota_build(self, df_all):
        # Compatibility escape hatch for historical configs. New apps should use metadata_selector.enabled=True.
        rows = self._candidate_records(df_all)
        rows = sorted(rows, key=self._utility_sort_key, reverse=True)
        target_count = sum(self._main_quotas().values())
        selected = rows[:target_count]
        for row in selected:
            row["Section"] = self._section_for_row(row)
            row["QuotaStatus"] = "EXACT"
            row["FillSource"] = ""
            row["FillReason"] = ""
        return self._result_from_selected(selected, [])


def build_main_keyword_shortlist(df_all, config):
    return MainKeywordShortlistBuilder(config).build(df_all)


def _number(value, default=0.0):
    try:
        if _is_blank(value):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp01(value):
    return max(0.0, min(1.0, _number(value, 0.0)))


def _is_blank(value):
    if value is None:
        return True
    try:
        if value != value:
            return True
    except TypeError:
        pass
    return str(value).strip() == ""


def _text_value(row, *keys, default=""):
    for key in keys:
        if key in row and not _is_blank(row.get(key)):
            return str(row.get(key)).strip()
    return default


def _decision_rule(row):
    return _text_value(row, "DecisionRule", "AIDecisionRule", "PreAIRule")
