FILTER_POLICY = {
    "semantic_mode": "ar_filter",
    "keyword_quota": {
        "main_file": {
            "core_intent": 25,
            "core_feature": 5,
            "broad_expansion": 5,
            "consider": 5,
        },
    },
    "risky_ip_terms": [],
    # "doggy" (double-g spelling variant) used to be appended to intent_core_terms/style_terms
    # via a standalone Python statement in run_ar_filter_v4_3.py, AFTER the FILTER_POLICY merge.
    # shared/effective_config.py (used by tools/warm_cache_helper.py's find-misses/prepare-batches/
    # save-results/verify-cache) only reads the literal `config = {...}` block plus this
    # FILTER_POLICY dict -- it does not execute arbitrary further statements in the runner. That
    # standalone mutation was invisible to it, so it computed a different context_hash than the
    # live pipeline, silently orphaning any cache entries saved via the CLI tool. Moved here so
    # both paths see the identical final config.
    "intent_core_terms": ["doggy filter", "doggy filters", "ar doggy filter"],
    "style_terms": ["doggy"],
    "ambiguous_brand_terms": ["snow"],
    "platform_affiliation_terms": ["official snapchat", "official tiktok", "official instagram", "snapchat filter"],
    "truncation_policy": {
        "enabled": True,
        "min_prefix_length": 2,
        "allowed_partial_terms": [],
        "protect_complete_tokens": True,
        "ignore_inflection_prefix": True,
        "low_confidence_action": "manual_review",
        "dangling_action": "manual_review",
    },
    "risk_policy": {
        "competitor_brand_action": "drop",
        "ambiguous_brand_action": "consider",
        "risky_ip_action": "consider",
        "platform_context_action": "consider",
        "platform_only_action": "drop",
        "platform_affiliation_action": "drop",
        "style_only_action": "reserve",
        "core_intent_override": True,
    },
}
