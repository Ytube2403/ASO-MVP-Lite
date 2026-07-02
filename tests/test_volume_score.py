import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared import keyword_filter


class VolumeScoreTests(unittest.TestCase):
    def test_search_popularity_uses_absolute_exponential_curve(self):
        low = keyword_filter.calculate_volume_score(5, 5)
        medium = keyword_filter.calculate_volume_score(21, 21)
        high = keyword_filter.calculate_volume_score(60, 60)
        top = keyword_filter.calculate_volume_score(67, 67)

        self.assertEqual(low, 0.0)
        self.assertLess(low, medium)
        self.assertLess(medium, high)
        self.assertLess(high, top)
        self.assertGreater(top, medium * 5)

    def test_low_tier_is_capped_even_with_strong_historical_peak(self):
        self.assertLessEqual(keyword_filter.calculate_volume_score(5, 100), 0.05)

    def test_historical_peak_is_a_secondary_signal(self):
        current_only = keyword_filter.calculate_volume_score(21, 21)
        with_peak = keyword_filter.calculate_volume_score(21, 67)
        top = keyword_filter.calculate_volume_score(67, 67)

        self.assertGreater(with_peak, current_only)
        self.assertLess(with_peak, top)

    def test_maximum_reach_preserves_exponential_traffic_gap(self):
        # Log-reach keeps higher reach ranked higher, but no longer crushes mid-tier reach
        # to ~0 (that linear behavior was the bug this replaced).
        top = keyword_filter.calculate_volume_score(67, 67, 130506, 130506)
        high = keyword_filter.calculate_volume_score(60, 60, 34122, 130506)
        medium = keyword_filter.calculate_volume_score(21, 21, 5846, 130506)

        self.assertGreater(top, high)
        self.assertGreater(high, medium)
        self.assertGreater(medium, 0.5)  # mid-tier reach is meaningful, not crushed to ~0

    def test_maximum_reach_overrides_search_popularity_when_available(self):
        # Real reach drives the score even when the popularity index disagrees.
        low_vol_real_reach = keyword_filter.calculate_volume_score(21, 21, 900, 1000)
        high_vol_low_reach = keyword_filter.calculate_volume_score(90, 90, 100, 1000)

        self.assertGreater(low_vol_real_reach, high_vol_low_reach)
        self.assertGreater(low_vol_real_reach, 0.5)
        self.assertLess(high_vol_low_reach, 0.5)

    def test_low_tier_can_fill_metadata_quota_by_default_in_v4_1(self):
        row = {"Volume": 5}
        self.assertTrue(keyword_filter.is_shortlist_volume_eligible(row, "Core Intent Final"))
        self.assertTrue(keyword_filter.is_shortlist_volume_eligible(row, "Broad Expansion"))
        self.assertTrue(keyword_filter.is_shortlist_volume_eligible(row, "Consider Keywords", 998))
        self.assertFalse(keyword_filter.is_shortlist_volume_eligible(row, "Consider Keywords", 999))
        self.assertTrue(keyword_filter.is_shortlist_volume_eligible({"Volume": 6}, "Core Intent Final"))

    def test_low_tier_v4_0_quota_can_still_be_configured_explicitly(self):
        config = {
            "volume_score_policy": {
                "exclude_low_tier_from_metadata_shortlist": True,
                "max_low_tier_consider_keywords": 3,
            }
        }
        row = {"Volume": 5}
        self.assertFalse(keyword_filter.is_shortlist_volume_eligible(row, "Core Intent Final", config=config))
        self.assertFalse(keyword_filter.is_shortlist_volume_eligible(row, "Broad Expansion", config=config))
        self.assertTrue(keyword_filter.is_shortlist_volume_eligible(row, "Consider Keywords", 2, config=config))
        self.assertFalse(keyword_filter.is_shortlist_volume_eligible(row, "Consider Keywords", 3, config=config))

    def test_safe_reach_ceiling_excludes_competitor_outlier(self):
        df = pd.DataFrame([
            {"MaximumReach": 353967, "is_competitor": True, "is_irrelevant": False},
            {"MaximumReach": 50, "is_competitor": False, "is_irrelevant": False},
            {"MaximumReach": 172, "is_competitor": False, "is_irrelevant": False},
            {"MaximumReach": 14, "is_competitor": False, "is_irrelevant": False},
        ])
        ceiling = keyword_filter.safe_reach_ceiling(df)
        self.assertLess(ceiling, 1000)
        self.assertGreater(ceiling, 0)

    def test_safe_reach_ceiling_falls_back_when_all_rows_are_unsafe(self):
        df = pd.DataFrame([
            {"MaximumReach": 100, "is_competitor": True, "is_irrelevant": False},
            {"MaximumReach": 200, "is_competitor": True, "is_irrelevant": False},
        ])
        ceiling = keyword_filter.safe_reach_ceiling(df)
        self.assertGreater(ceiling, 0)

    def test_safe_reach_ceiling_handles_missing_columns(self):
        df = pd.DataFrame([{"Keyword": "x"}])
        self.assertEqual(keyword_filter.safe_reach_ceiling(df), 0.0)


if __name__ == "__main__":
    unittest.main()
