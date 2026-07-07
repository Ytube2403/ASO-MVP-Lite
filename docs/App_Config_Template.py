# -*- coding: utf-8 -*-
"""
ASO Keyword Planner - App Configuration Template
Version: 4.5
Purpose: Template configuration for deploying ASO Keyword Planner on a new application.
"""

APP_CONFIG = {
    # ==========================================
    # 1. IDENTITY & META
    # ==========================================
    "app_id": "com.example.yourapp",  # App bundle/package ID
    "app_name": "Your App Name",      # Full app name
    "category": "Widget",             # App category (Widget, Emulator, AR Filter, VPN...)
    "category_slug": "widget",        # URL/path slug: lowercase ASCII, underscore-separated
    "market": "US_EN",                # Default target market (US_EN, VN_VI, BR_PT, IN_EN...)
    "platform_mode": "google_play",   # Platform: 'google_play' or 'app_store'

    "semantic_mode": "personalization_widget",

    # ==========================================
    # 2. MARKET LANGUAGE POLICY
    # ==========================================
    "market_language_policy": {
        "enabled": True,
        "required": True,
        "primary_languages": ["en"],              # Primary languages allowed in the core shortlist
        "secondary_languages": ["es", "es-MX"],   # Secondary languages, for example US Spanish, kept for Consider
        "optional_secondary_languages": [],       # Other optional secondary languages

        "primary_language_action": "keep",
        "secondary_language_action": "consider",
        "optional_secondary_action": "audit_or_consider",
        "foreign_language_action": "drop_to_audit",  # Drop keywords outside the language policy into audit

        "allow_secondary_in_top25_core": False,
        "allow_secondary_in_broad_expansion": False,
        "secondary_max_quota_in_broad": 0,
        "secondary_max_quota_in_consider": 3,
        "allow_secondary_in_feature_file": False,
        "allow_secondary_in_style_file": False,

        "mixed_language_action": "manual_review",
        "unknown_language_action": "manual_review_if_high_score"
    },

    # ==========================================
    # 2.5 AGENTIC KEYWORD CLASSIFIER (cache-only + pre-filter)
    # ==========================================
    "agentic_keyword_classifier": {
        "enabled": True,
        "provider": "antigravity_subagent",
        "model": "subagent-cache-v1",
        "cache_only": True,
        "batch_size": 200,
        "prompt_version": "agentic-keyword-classifier-v1",
        "fail_on_api_error": True,
        "min_confidence": 0.55,
        "cache_path": ".cache/agentic_keyword_analysis.sqlite3",
        "pre_filter": {
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
                "platform_only"
            ]
        }
    },

    # Optional manual invalidation knob for agentic cache semantic buckets.
    # Brand/risk lists are deterministic and take effect every run WITHOUT re-warming.
    # Bump this only when the AI classification prompt/ruleset changes and old
    # AISemanticBucket/AIDecisionRule values should stop matching the cache.
    # "ruleset_version": "agentic-keyword-classifier-v2",

    # ==========================================
    # 3. SEMANTIC GROUPS
    # ==========================================
    "intent_core_terms": [
        # Core keywords that express the main app-search intent.
        # Example: "control panel", "control center" for Control Widget.
        "core term 1", "core term 2"
    ],

    "feature_terms": [
        # Keywords that describe specific app features or functions.
        # Example: "brightness", "volume", "wifi toggle".
        "feature 1", "feature 2"
    ],

    "style_terms": [
        # Keywords that describe style, UI, IP, or visual/aesthetic themes.
        # Example: "aesthetic", "cute", "anime", "neon".
        # NOTE: style_terms are allocated only to Full Description, not Title/Subtitle, to reduce IP risk.
        "style 1", "style 2"
    ],

    "visual_terms": [
        # Keywords that describe supporting UI or visual effects.
        "visual 1", "visual 2"
    ],

    # ==========================================
    # 4. FILTERS & BLACKLIST
    # ==========================================
    "competitor_brands": [
        # Competitor brand names. Keywords containing competitor brands are blocked from primary metadata.
        "competitor brand 1", "competitor brand 2"
    ],

    "noise_terms": [
        # Generic terms that are too broad and do not express specific app-search intent.
        # Example: "app", "free", "download", "android".
        "app", "free", "download", "android", "new", "best"
    ],

    "typo_blacklist": [
        # Common misspellings or meaningless auto-suggest noise.
        "typo 1", "typo 2"
    ],

    "irrelevant_intent_terms": [
        # Keywords from a different category that are unrelated to this app.
        "calculator", "weather"
    ],

    # PHAN BIET risky_ip_terms vs risky_platform_terms (quan trong):
    # - risky_ip_terms: specific characters, game titles, or creative products
    #   (for example Mario, Pokemon, Zelda). These imply that the app offers or plays
    #   the exact protected product, so copyright risk is high and the default is hard drop.
    # - risky_platform_terms: manufacturer, console, or hardware names
    #   (for example Nintendo, Sony, Sega, Microsoft, PlayStation, Xbox). These can be
    #   necessary functional vocabulary for emulator/accessory apps, so the default is
    #   Consider Keywords through platform_context_action instead of hard drop.
    # KHONG dat ten hang/he may vao risky_ip_terms - se bi Drop oan ngay ca khi do la platform
    # supported by the app (see section 36 in ASO_Keyword_Planner_v4_5.md).
    # Override guardrail:
    # - matched risky/platform term must be declared-safe in core/feature vocabulary;
    # - keyword must also carry a distinctive functional anchor (emulator, rom, console, gba, nds...);
    # - generic tokens like game/games/play/app/free never count as anchors.
    "risky_ip_terms": [
        # Keywords containing sensitive IP or copyright terms that must be restricted.
        "brandname"
    ],

    "risky_platform_terms": ["iphone", "ios", "ipad", "apple", "android", "tiktok", "snapchat", "instagram"],
    "ambiguous_brand_terms": [],
    # Explicit affiliation/official/brand-claim phrases. These have NO
    # core_intent_override because claiming affiliation is risky even when a plain
    # platform mention would be functional context.
    "platform_affiliation_terms": ["official tiktok", "official snapchat", "official instagram"],
    "truncation_policy": {
        "enabled": True,
        "min_prefix_length": 2,
        "allowed_partial_terms": [],
        "protect_complete_tokens": True,
        "ignore_inflection_prefix": True,
        "low_confidence_action": "manual_review",
        "dangling_action": "manual_review"
    },

    # ==========================================
    # 5. RISK HANDLING & PRECEDENCE
    # ==========================================
    "risk_policy": {
        "competitor_brand_action": "drop",
        "ambiguous_brand_action": "consider",
        "risky_ip_action": "consider",
        "platform_context_action": "consider",
        "platform_only_action": "drop",
        "platform_affiliation_action": "drop",
        "style_only_action": "reserve",
        # Guardrail: this only rescues declared-safe platform/IP terms when the row
        # also has a distinctive functional anchor. It does NOT rescue
        # platform_affiliation_terms, and it does NOT rescue AI-recognized classic
        # game IP unless explicitly declared.
        "core_intent_override": True  # If strong core intent is present, do not auto-drop for minor risk matches
    },

    # ==========================================
    # 6. KEYWORD QUOTA
    # ==========================================
    "keyword_quota": {
        "main_file": {
            "core_intent": 25,       # So luong keyword core chinh (Top 25)
            "core_feature": 5,       # So luong keyword feature (Top 5)
            "broad_expansion": 5,    # Number of broader expansion keywords
            "consider": 5,          # Number of Consider keywords
        },
        "feature_file": {
            "max_keywords": 30,
            "core_feature": 20,
            "feature_expansion": 5,
            "feature_test": 5
        },
        "style_file": {
            "max_keywords": 30,
            "intent_linked_style": 15,
            "broad_style": 10,
            "platform_style_consider": 5
        },
        "fallback_policy": {
            "allow_under_quota": True,
            "fill_from_next_best_eligible_bucket": True,
            "do_not_force_weak_keywords": True,
            "min_relevancy_for_fill": 0.45,
            "add_fill_reason_column": True
        }
    },

    "metadata_selector": {
        "enabled": True,
        "target_count": 40,
        "cluster_cap": 3,                        # Max 3 keywords per semantic cluster (Jaccard similarity, see shortlist.py)
        "cluster_similarity_threshold": 0.5,      # Jaccard threshold for treating two keywords as one cluster
        "cluster_generic_token_ratio": 0.30,      # Tokens appearing in >30% of the pool are ignored in cluster comparison
        "quality_min_balanced_score": 0.40,
        "quality_min_relevancy": 0.45,
        "quality_min_volume": 6.0,
        "quality_min_reach": 1.0,
        "generic_safe_descriptors": ["retro", "classic"],
    },

    # Post-candidate metadata/ads suitability gate. This is separate from
    # relevancy/classification: a keyword can be related to the app but still too
    # broad or too weak as Play Store acquisition traffic when it stands alone.
    "metadata_suitability": {
        "enabled": True,
        "audit_min_volume": 5,
        "fail_on_missing_audit": True,
        "single_token_policy": {
            "enabled": True,
            "default_action": "research_only",
            # Atomic app/platform intent terms that are meaningful even as one token.
            "keep_terms": [],
            # Feature/style/marketing terms that are too broad as one-token queries.
            "block_terms": [],
        },
    },

    # VolumeN/utility reach ceiling: shared/keyword_filter/scoring.py::safe_reach_ceiling
    # Computes percentile 95 over non-competitor/non-irrelevant rows by default
    # instead of absolute max(), avoiding one brand outlier skewing the whole pool.

    # RelevancyScore stacking dampener: shared/keyword_filter/scoring.py::dampen_stacked_relevancy
    # Enabled by default; can be overridden through "relevancy_stacking_dampener".
    "relevancy_stacking_dampener": {
        "enabled": True,
        "min_category_hits": 2,     # Dampen only when >=2 intent groups match at once
        "max_volume": 10.0,         # Dampen only when Volume <= this threshold
        "max_reach": 5.0,           # Dampen only when MaximumReach <= this threshold
        "score_cap": 0.65,          # Tran RelevancyScore sau khi dampen
    },

    # ==========================================
    # 7. LANGUAGE NATURALNESS
    # ==========================================
    "language_naturalness": {
        "enabled": True,
        "penalty_unnatural": -0.35,      # Penalty for unnatural phrases
        "auto_drop_score_below": 0.15,   # Auto-drop if Relevancy after penalty is below this threshold
        "rules": {
            "grammar_violation": {
                "patterns": [
                    r"\b(app app|widget widget|theme theme)\b",
                    r"\b(what is|how to|why do|when is|where is)\b"
                ],
                "flag": "UNNATURAL"
            },
            "redundancy": {
                "max_word_repeat_ratio": 0.5,
                "flag": "STUFFING"
            },
            "length_anomaly": {
                "max_natural_words": 6,
                "exception_if_contains_core": True,
                "flag": "TOO_LONG"
            },
            "cross_language_bleed": {
                "note": "Legacy note only. From v3.5, script/language mismatch is handled by shared/language_detector.py; naturalness must not hard-drop non-Latin text as LANGUAGE_BLEED.",
                "forbidden_foreign_in_market": {},
                "flag": "LANGUAGE_BLEED"
            }
        }
    },

    # ==========================================
    # 8. SCORING WEIGHTS
    # ==========================================
    # Current shared calculate_relevancy reads only "base"; the remaining lexical
    # bonuses/penalties are deterministic in shared/keyword_filter/scoring.py:
    # +0.35 core, +0.20 feature, +0.15 style, -0.20 competitor,
    # -0.25 irrelevant, -0.30 FOREIGN, +CompetitorBoost.
    "relevancy_weights": {
        "base": 0.30
    },

    # KEIN is removed from BalancedScore weighting because KEI is derived from
    # Volume and Difficulty. Legacy configs with KEIN > 0 are auto-migrated by
    # shared/keyword_filter/scoring.py::resolve_balanced_weights.
    "balanced_weights": {
        "VolumeN": 0.35,
        "DifficultyN": 0.15,
        "RelevancyScore": 0.30,
        "CurrentRankN": 0.10,
        "ExpansionValue": 0.10
    },

    "scoring_normalization": {
        "volume": "maximum_reach_or_exponential_search_popularity",
        "difficulty": "inverse_0_100",
        "kei": "log_minmax",
        "rank": "tiered_rank_score",
        "unranked_rank_score": 0.0
    },

    "volume_score_policy": {
        "mode": "log_reach",
        "reach_reference": 100000.0,
        "search_popularity_floor": 5.0,
        "search_popularity_ceiling": 100.0,
        "exponential_curve_factor": 4.0,
        "current_volume_weight": 0.85,
        "historical_max_volume_weight": 0.15,
        "low_tier_threshold": 5.0,
        "low_tier_score_cap": 0.05,
        "exclude_low_tier_from_metadata_shortlist": False,
        "max_low_tier_consider_keywords": 999
    },

    # Optional: deterministic rubric used after lexical relevancy when an AI cache
    # classification is available. Defaults live in shared/keyword_filter/scoring.py.
    # "relevancy_rubric": {"bucket_base": {"feature keywords": 0.75}, "confidence_span": 0.15},

    # ==========================================
    # 9. METADATA SLOTS & OUTPUT
    # ==========================================
    "metadata_slots": {
        "google_play": {
            "Title": 2,
            "Short Description": 7,
            "Full Description": 21
        },
        "app_store": {
            "Title": 2,
            "Subtitle": 5,
            "Keyword Field": 15,
            "Promotional Text": 5
        }
    },

    "max_word_overlap": 0.5,  # Max word-overlap ratio between Top N keywords
    "dedup_policy": {
        "auto_merge_token_bag": False,
        "review_overlap_threshold": 0.80,
        "accent_fold_auto_merge_locales": [],
        "enable_review_log": True,
    },
    "output_prefix": "ASO_Keyword_Planner",
    "output_mode": "excel_workbook",
    "output_workbook": {
        "enabled": True,
        "filename_pattern": "ASO_Keyword_Planner_{app_name}_{market}.xlsx",
        "export_csv_package": False,
        "export_markdown_report": False,
        "include_all_candidates_sheet": True,
        "include_optional_audit_sheets": True,
        "freeze_header_rows": True,
        "enable_filters": True,
        "format_as_tables": True,
        "wrap_text_columns": ["Keyword", "Reason", "DecisionReason", "LanguageReason", "FillReason"],
        "required_sheets": [
            "00_README_CONFIG",
            "01_Main_Keyword_Shortlist",
            "02_Feature_Keywords",
            "03_Style_Keywords",
            "04_Dropped_Audit",
            "05_Report_Summary",
            "06_All_Candidates",
            "13_Top_By_Volume"
        ],
        "optional_sheets": [
            "07_Language_Mismatch",
            "08_Generic_Style_Reserve",
            "09_Manual_Review",
            "10_Top_By_Score",
            "11_Secondary_Language"
        ]
    },

    # ==========================================
    # 10. USER OVERRIDES
    # ==========================================
    "user_overrides": {
        "do_not_auto_drop_terms": [],
        "force_consider_terms": [],
        # Exact phrases that should bypass metadata/ads suitability audit after
        # deterministic risk/language gates pass. Use sparingly for owner-approved
        # acquisition terms, not as a broad rescue list.
        "suitability_keep_terms": [],
        "force_drop_terms": [],
        "force_top30_terms": [],
        "notes": []
    }
}
