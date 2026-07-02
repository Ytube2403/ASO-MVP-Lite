import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared import keyword_filter


def candidate(keyword, bucket, score, rel=0.7, volume=30, rule=""):
    return {
        "Keyword": keyword,
        "Bucket": bucket,
        "BalancedScore": score,
        "Rank_numeric": 100,
        "KEI": 10,
        "Difficulty": 20,
        "Volume": volume,
        "Max. Volume": volume,
        "VolumeN": 0.4,
        "MaximumReach": volume * 100,
        "RelevancyScore": rel,
        "DecisionRule": rule,
        "LanguageGroup": "PRIMARY",
        "NaturalnessFlag": "OK",
    }


class MainKeywordShortlistBuilderTests(unittest.TestCase):
    def test_builds_target_list_by_utility_not_hard_bucket_quota(self):
        rows = []
        rows.extend(candidate(f"core keyword {i}", "Core Intent Final", 0.9 - i / 100, rel=0.85, volume=60) for i in range(20))
        rows.extend(candidate(f"feature keyword {i}", "Feature Keywords", 0.95 - i / 100, rel=0.9, volume=70) for i in range(20))
        rows.extend(candidate(f"weak broad keyword {i}", "Broad Expansion", 0.25 - i / 100, rel=0.25, volume=10) for i in range(20))

        result = keyword_filter.build_main_keyword_shortlist(
            pd.DataFrame(rows),
            {"market": "US_EN", "metadata_selector": {"cluster_cap": 100}},
        )

        self.assertEqual(len(result.all_rows), 40)
        selected = {row["Keyword"] for row in result.all_rows}
        self.assertIn("feature keyword 0", selected)
        self.assertNotIn("weak broad keyword 0", selected)
        self.assertGreater(len(result.feature), 5)

    def test_quality_gate_excludes_risk_and_weak_rows_from_metadata(self):
        rows = [
            candidate("safe core", "Core Intent Final", 0.9, rel=0.8, volume=50),
            candidate("pokemon core", "Core Intent Final", 0.95, rel=0.9, volume=80, rule="risky_ip"),
            candidate("weak core", "Core Intent Final", 0.2, rel=0.2, volume=80),
            candidate("safe feature", "System Keywords", 0.8, rel=0.7, volume=50),
            candidate("safe broad", "Broad Expansion", 0.7, rel=0.7, volume=50),
            candidate("safe consider", "Consider Keywords", 0.6, rel=0.7, volume=50),
            candidate("pokemon consider", "Consider Keywords", 0.9, rel=0.9, volume=90, rule="risky_ip"),
        ]
        config = {
            "market": "US_EN",
            "keyword_quota": {
                "main_file": {
                    "core_intent": 2,
                    "core_feature": 1,
                    "broad_expansion": 1,
                    "consider": 2,
                }
            },
            "metadata_quality_gate": {
                "enabled": True,
                "exclude_risk_from_consider": True,
                "section_floors": {
                    "Core Intent Final": {"min_relevancy": 0.5, "min_balanced_score": 0.35},
                    "Feature Keywords": {"min_relevancy": 0.5, "min_balanced_score": 0.35},
                    "Broad Expansion": {"min_relevancy": 0.5, "min_balanced_score": 0.35},
                    "Consider Keywords": {"min_relevancy": 0.5, "min_balanced_score": 0.35},
                },
            },
        }

        result = keyword_filter.build_main_keyword_shortlist(pd.DataFrame(rows), config)
        selected = {row["Keyword"] for row in result.all_rows}

        self.assertIn("safe core", selected)
        self.assertIn("safe feature", selected)
        self.assertIn("safe broad", selected)
        self.assertIn("safe consider", selected)
        self.assertNotIn("pokemon core", selected)
        self.assertNotIn("pokemon consider", selected)
        self.assertNotIn("weak core", selected)

    def test_semantic_cluster_cap_prevents_crowding(self):
        rows = []
        rows.extend(candidate(f"retro game emulator {i}", "Core Intent Final", 0.95 - i / 100, rel=0.9, volume=80 - i) for i in range(10))
        rows.extend(candidate(f"save state emulator {i}", "Feature Keywords", 0.80 - i / 100, rel=0.8, volume=50 - i) for i in range(10))
        config = {"market": "US_EN", "metadata_selector": {"target_count": 8, "cluster_cap": 2}}

        result = keyword_filter.build_main_keyword_shortlist(pd.DataFrame(rows), config)

        retro_selected = [row for row in result.all_rows if str(row["Keyword"]).startswith("retro game emulator")]
        self.assertEqual(len(retro_selected), 2)
        self.assertTrue(any(entry["NotSelectedReason"] == "CLUSTER_CAP_REACHED" for entry in result.not_selected_log))

    def test_dedup_representative_uses_utility_before_volume(self):
        rows = [
            candidate("game emulator", "Core Intent Final", 0.95, rel=0.95, volume=10),
            candidate("games emulator", "Core Intent Final", 0.60, rel=0.55, volume=100),
        ]
        config = {"market": "US_EN", "metadata_selector": {"target_count": 1}}

        result = keyword_filter.build_main_keyword_shortlist(pd.DataFrame(rows), config)

        self.assertEqual(result.all_rows[0]["Keyword"], "game emulator")
        self.assertEqual(result.dedup_log[0]["KeptKeyword"], "game emulator")
        self.assertEqual(result.not_selected_log[0]["NotSelectedReason"], "DUPLICATE_REPRESENTATIVE_KEPT")

    def test_safe_only_backfill_marks_lower_utility_rows(self):
        rows = []
        rows.extend(candidate(f"strong keyword {i}", "Core Intent Final", 0.9 - i / 100, rel=0.8, volume=50) for i in range(3))
        rows.extend(candidate(f"safe weak keyword {i}", "Broad Expansion", 0.22, rel=0.35, volume=20) for i in range(3))
        config = {
            "market": "US_EN",
            "metadata_selector": {
                "target_count": 5,
                "cluster_cap": 3,
                "quality_min_utility": 0.55,
                "safe_backfill_min_utility": 0.25,
                "quality_min_balanced_score": 0.20,
                "quality_min_relevancy": 0.30,
            },
        }

        result = keyword_filter.build_main_keyword_shortlist(pd.DataFrame(rows), config)

        self.assertEqual(len(result.all_rows), 5)
        self.assertTrue(any(row["QuotaStatus"] == "SAFE_BACKFILL" for row in result.all_rows))

    def test_backfill_does_not_use_zero_reach_low_volume_rows(self):
        rows = []
        rows.extend(candidate(f"strong keyword {i}", "Core Intent Final", 0.8 - i / 100, rel=0.8, volume=20) for i in range(3))
        for i in range(5):
            row = candidate(f"low demand exact keyword {i}", "Core Intent Final", 0.55, rel=1.0, volume=5)
            row["MaximumReach"] = 0
            row["VolumeN"] = 0.0
            rows.append(row)
        config = {
            "market": "US_EN",
            "metadata_selector": {
                "target_count": 8,
                "cluster_cap": 100,
                "quality_min_utility": 0.45,
                "safe_backfill_min_utility": 0.25,
            },
        }

        result = keyword_filter.build_main_keyword_shortlist(pd.DataFrame(rows), config)
        selected = {row["Keyword"] for row in result.all_rows}

        self.assertEqual(len(result.all_rows), 3)
        self.assertFalse(any(keyword.startswith("low demand exact keyword") for keyword in selected))
        self.assertTrue(any(entry["NotSelectedReason"] == "BELOW_DEMAND_FLOOR" for entry in result.not_selected_log))

    def test_selector_handles_ai_rule_alias_and_blank_nan_values(self):
        rows = [
            {
                "Keyword": "safe emulator",
                "Bucket": "Core Intent Final",
                "BalancedScore": 0.7,
                "RelevancyScore": 0.8,
                "Volume": 30,
                "MaximumReach": 300,
                "AIDecisionRule": "",
                "LanguageGroup": float("nan"),
                "NaturalnessFlag": float("nan"),
            },
            {
                "Keyword": "pokemon emulator",
                "Bucket": "Core Intent Final",
                "BalancedScore": 0.9,
                "RelevancyScore": 0.9,
                "Volume": 60,
                "MaximumReach": 600,
                "AIDecisionRule": "risky_ip",
                "LanguageGroup": "PRIMARY",
                "NaturalnessFlag": "OK",
            },
            {
                "Keyword": "gb4 emulator",
                "Bucket": "Feature Keywords",
                "BalancedScore": 0.9,
                "RelevancyScore": 0.6,
                "Volume": 60,
                "MaximumReach": 600,
                "AIDecisionRule": "ai_feature_intent",
                "AIReason": "Targets specific console brand, model, or category (app_brand_gb4)",
                "LanguageGroup": "PRIMARY",
                "NaturalnessFlag": "OK",
            },
        ]

        result = keyword_filter.build_main_keyword_shortlist(
            pd.DataFrame(rows),
            {"market": "US_EN", "metadata_selector": {"target_count": 2}},
        )
        selected = {row["Keyword"] for row in result.all_rows}

        self.assertIn("safe emulator", selected)
        self.assertNotIn("pokemon emulator", selected)
        self.assertNotIn("gb4 emulator", selected)

    def test_generic_retro_and_classic_are_not_ambiguous_brand_blocked(self):
        rows = [
            candidate("retro games emulator", "Consider Keywords", 0.9, rel=0.9, volume=60, rule="ambiguous_brand"),
            candidate("delta game emulator", "Consider Keywords", 0.95, rel=0.9, volume=80, rule="ambiguous_brand"),
            candidate("safe game emulator", "Core Intent Final", 0.7, rel=0.7, volume=40),
        ]
        config = {
            "market": "US_EN",
            "ambiguous_brand_terms": ["retro", "classic", "delta"],
            "metadata_selector": {"target_count": 2, "cluster_cap": 2},
        }

        result = keyword_filter.build_main_keyword_shortlist(pd.DataFrame(rows), config)
        selected = {row["Keyword"] for row in result.all_rows}

        self.assertIn("retro games emulator", selected)
        self.assertNotIn("delta game emulator", selected)

    def test_mixed_language_row_is_selectable_when_bucket_already_allows_it(self):
        # For a non-English market, mixing the primary language with an English loanword
        # ("ds emulador") is normal search behavior. classify_keyword already encodes
        # whether the market allows it via Bucket (Manual Review if not, a normal bucket
        # if so) -- the selector must not re-block MIXED rows wholesale on top of that.
        rows = [
            candidate("ds emulador", "Core Intent Final", 0.6, rel=0.7, volume=25, rule="ai_core_intent"),
        ]
        rows[0]["LanguageGroup"] = "MIXED"
        config = {"market": "BR_PT", "metadata_selector": {"target_count": 1}}

        result = keyword_filter.build_main_keyword_shortlist(pd.DataFrame(rows), config)

        self.assertEqual([row["Keyword"] for row in result.all_rows], ["ds emulador"])

    def test_foreign_and_unknown_language_rows_stay_blocked_regardless_of_bucket(self):
        rows = [
            candidate("foreign keyword", "Core Intent Final", 0.9, rel=0.9, volume=50),
            candidate("unknown keyword", "Core Intent Final", 0.9, rel=0.9, volume=50),
        ]
        rows[0]["LanguageGroup"] = "FOREIGN"
        rows[1]["LanguageGroup"] = "UNKNOWN"
        config = {"market": "US_EN", "metadata_selector": {"target_count": 5}}

        result = keyword_filter.build_main_keyword_shortlist(pd.DataFrame(rows), config)

        self.assertEqual(result.all_rows, [])
        reasons = {entry["NotSelectedReason"] for entry in result.not_selected_log}
        self.assertEqual(reasons, {"BLOCKED_RISK"})


if __name__ == "__main__":
    unittest.main()
