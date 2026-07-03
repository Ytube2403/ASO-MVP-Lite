import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared import keyword_filter


def row(keyword, **overrides):
    data = {
        "Keyword": keyword,
        "Bucket": "Feature Keywords",
        "DecisionRule": "feature_keywords",
        "LanguageGroup": "PRIMARY",
        "NaturalnessFlag": "OK",
        "Volume": 50,
        "MaximumReach": 500,
        "BalancedScore": 0.7,
        "RelevancyScore": 0.7,
    }
    data.update(overrides)
    return data


class MetadataSuitabilityTests(unittest.TestCase):
    def config(self):
        return {
            "market": "US_EN",
            "intent_core_terms": ["supernds"],
            "metadata_suitability": {
                "single_token_policy": {
                    "enabled": True,
                    "default_action": "research_only",
                    "keep_terms": ["nds", "ds", "gba"],
                    "block_terms": ["arcade", "pizza", "moonlight", "turbospeed"],
                }
            },
        }

    def test_atomic_single_tokens_are_metadata_and_ads_eligible(self):
        for keyword in ("nds", "ds", "gba", "supernds"):
            result = keyword_filter.evaluate_metadata_suitability(row(keyword), self.config())
            self.assertTrue(result["MetadataEligible"], keyword)
            self.assertTrue(result["AdsEligible"], keyword)
            self.assertFalse(result["ResearchOnly"], keyword)
            self.assertEqual(result["SuitabilityRule"], "single_token_keep")

    def test_broad_single_tokens_are_research_only(self):
        for keyword in ("arcade", "pizza", "moonlight", "turbospeed"):
            result = keyword_filter.evaluate_metadata_suitability(row(keyword), self.config())
            self.assertFalse(result["MetadataEligible"], keyword)
            self.assertFalse(result["AdsEligible"], keyword)
            self.assertTrue(result["ResearchOnly"], keyword)
            self.assertEqual(result["SuitabilityRule"], "single_token_too_broad")

    def test_multi_word_anchor_phrases_are_not_blocked_by_single_token_policy(self):
        for keyword in ("arcade emulator", "gba emulator", "nds roms"):
            result = keyword_filter.evaluate_metadata_suitability(row(keyword), self.config())
            self.assertTrue(result["MetadataEligible"], keyword)
            self.assertTrue(result["AdsEligible"], keyword)
            self.assertFalse(result["ResearchOnly"], keyword)

    def test_blocked_risk_wins_even_if_keyword_is_keep_term(self):
        result = keyword_filter.evaluate_metadata_suitability(
            row("nds", Bucket="Dropped", DecisionRule="risky_ip"),
            self.config(),
        )
        self.assertFalse(result["MetadataEligible"])
        self.assertFalse(result["AdsEligible"])
        self.assertTrue(result["ResearchOnly"])
        self.assertEqual(result["SuitabilityRule"], "blocked_risk")

    def test_shortlist_excludes_metadata_ineligible_rows_and_logs_reason(self):
        rows = [
            row("arcade", Bucket="Feature Keywords", DecisionRule="feature_keywords"),
            row("nds", Bucket="Feature Keywords", DecisionRule="feature_keywords"),
        ]
        result = keyword_filter.build_main_keyword_shortlist(
            pd.DataFrame(rows),
            {
                **self.config(),
                "metadata_selector": {"target_count": 2, "cluster_cap": 10},
            },
        )
        self.assertEqual([item["Keyword"] for item in result.all_rows], ["nds"])
        arcade_log = next(item for item in result.not_selected_log if item["Keyword"] == "arcade")
        self.assertEqual(arcade_log["NotSelectedReason"], "SINGLE_TOKEN_TOO_BROAD")
        self.assertEqual(arcade_log["SuitabilityRule"], "single_token_too_broad")


if __name__ == "__main__":
    unittest.main()
