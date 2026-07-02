import copy
import os
import sys
import tempfile
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.agentic_keyword_classifier import (  # noqa: E402
    AIKeywordAnalysis,
    AIKeywordClassifier,
    AIKeywordClassifierError,
    analyze_dataframe,
)


BASE_CONFIG = {
    "app_id": "com.example.app",
    "app_name": "Example App",
    "category": "Personalization",
    "market": "VN_VI",
    "market_language_policy": {
        "primary_languages": ["vi"],
        "secondary_languages": ["en"],
        "mixed_language_action": "manual_review",
    },
    "intent_core_terms": ["pin emoji", "thanh trang thai"],
    "feature_terms": ["phim tat"],
    "style_terms": ["de thuong"],
    "visual_terms": [],
    "irrelevant_intent_terms": ["recipe"],
    "noise_terms": ["free"],
    "agentic_keyword_classifier": {
        "enabled": True,
        "provider": "antigravity_subagent",
        "model": "subagent-cache-v1",
        "prompt_version": "test-agentic-v1",
        "cache_only": True,
        "pre_filter": {
            "enabled": True,
            "duplicate_strategy": "canonical_reuse",
            "preserve_if_matches_intent": True,
            "allow_possible_truncated_to_ai": True,
        },
    },
}


def analysis(keyword, language="vi", gloss="battery status", bucket="Core Intent Final"):
    return AIKeywordAnalysis(
        keyword=keyword,
        detected_language=language,
        language_group="PRIMARY" if language != "en" else "SECONDARY",
        semantic_bucket=bucket,
        decision_rule="agentic_core_intent",
        reason="Relevant local-market ASO keyword.",
        confidence=0.91,
        english_gloss=gloss,
    )


class AgenticKeywordClassifierTests(unittest.TestCase):
    def test_analyze_dataframe_reuses_agentic_cache_without_network(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = os.path.join(temp_dir, "agentic.sqlite3")
            service = AIKeywordClassifier(cache_path, BASE_CONFIG, market="VN_VI")
            for keyword in ["phim tat", "thanh trang thai", "pin de thuong"]:
                service._store_cached(analysis(keyword), {"source": "test"})

            df = pd.DataFrame({
                "Keyword": ["phim tat", "thanh trang thai", "pin de thuong"],
                "Volume": [1, 2, 3],
                "Rank": ["", "", ""],
            })
            result = analyze_dataframe(df, BASE_CONFIG, cache_path=cache_path, market="VN_VI")

        self.assertEqual(result["AISemanticBucket"].tolist(), ["Core Intent Final"] * 3)
        self.assertEqual(result["AIStatus"].tolist(), ["AI_CACHE_HIT"] * 3)

    def test_cache_only_fails_before_network_for_uncached_keywords(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            calls = []

            def opener(*args, **kwargs):
                calls.append(1)
                raise AssertionError("network must not be used")

            df = pd.DataFrame({"Keyword": ["cache only miss"], "Volume": [1], "Rank": [""]})
            service = AIKeywordClassifier(
                os.path.join(temp_dir, "agentic.sqlite3"),
                BASE_CONFIG,
                market="VN_VI",
                opener=opener,
            )
            with self.assertRaisesRegex(AIKeywordClassifierError, "cache-only"):
                analyze_dataframe(df, BASE_CONFIG, cache_path=service.cache_path, market="VN_VI", service=service)
            self.assertEqual(calls, [])

    def test_cache_only_fails_when_non_english_cache_lacks_gloss(self):
        config = copy.deepcopy(BASE_CONFIG)
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = os.path.join(temp_dir, "agentic.sqlite3")
            service = AIKeywordClassifier(cache_path, config, market="VN_VI")
            service._store_cached(analysis("phim tat", gloss=""), {"source": "test"})
            df = pd.DataFrame({"Keyword": ["phim tat"], "Volume": [1], "Rank": [""]})

            with self.assertRaisesRegex(AIKeywordClassifierError, "english_gloss"):
                analyze_dataframe(df, config, cache_path=cache_path, market="VN_VI")

    def test_pre_ai_filter_skips_waste_and_reuses_duplicates(self):
        config = copy.deepcopy(BASE_CONFIG)
        config.update({
            "intent_core_terms": ["pin", "battery"],
            "intent_core_words": ["pin", "battery"],
            "feature_terms": ["status bar", "battery status"],
            "style_terms": ["cute"],
            "visual_terms": ["theme", "icon"],
            "competitor_brands": ["duolingo"],
            "typo_blacklist": ["batterry"],
            "irrelevant_intent_terms": ["recipe"],
            "noise_terms": ["free"],
            "truncation_policy": {
                "enabled": True,
                "min_prefix_length": 2,
                "low_confidence_action": "manual_review",
            },
        })
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = os.path.join(temp_dir, "agentic.sqlite3")
            service = AIKeywordClassifier(cache_path, config, market="US_EN")
            for keyword in ["theme pin", "phone personalization", "cute sta"]:
                service._store_cached(analysis(keyword, language="en", gloss=keyword, bucket="Broad Expansion"), {"source": "test"})

            rows = [
                "theme pin",
                "phone personalization",
                "free",
                "duolingo battery",
                "batterry",
                "battery sta",
                "recipe maker",
                "theme pin",
                "cute sta",
                "",
            ]
            df = pd.DataFrame({"Keyword": rows, "Volume": [1] * len(rows), "Rank": [""] * len(rows)})
            output = analyze_dataframe(df, config, cache_path=cache_path, market="US_EN", service=service)

        self.assertEqual(output["AIStatus"].tolist(), [
            "AI_CACHE_HIT",
            "AI_CACHE_HIT",
            "AI_SKIPPED_PREFILTER",
            "AI_SKIPPED_PREFILTER",
            "AI_SKIPPED_PREFILTER",
            "AI_SKIPPED_PREFILTER",
            "AI_SKIPPED_PREFILTER",
            "AI_REUSED_CANONICAL",
            "AI_CACHE_HIT",
            "AI_SKIPPED_PREFILTER",
        ])
        self.assertEqual(output.loc[7, "AISemanticBucket"], "Broad Expansion")
        self.assertEqual(output.loc[8, "PreAIRule"], "needs_agentic_cache")


if __name__ == "__main__":
    unittest.main()
