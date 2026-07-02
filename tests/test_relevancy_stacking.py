import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared import keyword_filter


CONFIG = {
    "intent_core_terms": ["retro emulator", "nds emulator", "nintendo ds emulator"],
    "feature_terms": ["gba emulator"],
    "style_terms": ["retro", "classic"],
}


class RelevancyStackingTests(unittest.TestCase):
    def test_caps_score_for_stuffed_low_demand_keyword(self):
        row = {
            "Keyword": "retro emulator save state",
            "EN": "retro emulator save state",
            "Volume": 5,
            "MaximumReach": 0,
            "RelevancyScore": 1.0,
        }
        self.assertEqual(keyword_filter.dampen_stacked_relevancy(row, CONFIG), 0.65)

    def test_caps_score_for_small_nonzero_reach(self):
        # MaximumReach is a raw AppTweak count, not a 0-1 score -- a threshold of exactly
        # 0.0 would only exempt literally-zero reach, letting small-but-negligible reach
        # (e.g. 3) escape dampening entirely even though it carries no real demand signal.
        row = {
            "Keyword": "retro emulator save state",
            "EN": "retro emulator save state",
            "Volume": 5,
            "MaximumReach": 3,
            "RelevancyScore": 1.0,
        }
        self.assertEqual(keyword_filter.dampen_stacked_relevancy(row, CONFIG), 0.65)

    def test_leaves_high_demand_keyword_untouched(self):
        row = {
            "Keyword": "retro emulator save state",
            "EN": "retro emulator save state",
            "Volume": 40,
            "MaximumReach": 500,
            "RelevancyScore": 1.0,
        }
        self.assertEqual(keyword_filter.dampen_stacked_relevancy(row, CONFIG), 1.0)

    def test_leaves_single_category_match_untouched(self):
        row = {
            "Keyword": "retro emulator",
            "EN": "retro emulator",
            "Volume": 5,
            "MaximumReach": 0,
            "RelevancyScore": 0.65,
        }
        self.assertEqual(keyword_filter.dampen_stacked_relevancy(row, CONFIG), 0.65)

    def test_checks_both_keyword_and_en_gloss(self):
        # The core-intent hit only shows up in the raw Keyword ("nds emulator"), while
        # the style hit only shows up in the AI-generated EN gloss ("...retro games.").
        # The dampener must combine hits across both fields, not just one.
        row = {
            "Keyword": "nds emulator",
            "EN": "Emulator to play Nintendo DS retro games.",
            "Volume": 5,
            "MaximumReach": 0,
            "RelevancyScore": 1.0,
        }
        self.assertEqual(keyword_filter.dampen_stacked_relevancy(row, CONFIG), 0.65)

    def test_disabled_policy_is_a_no_op(self):
        row = {
            "Keyword": "retro emulator save state",
            "EN": "retro emulator save state",
            "Volume": 5,
            "MaximumReach": 0,
            "RelevancyScore": 1.0,
        }
        config = dict(CONFIG, relevancy_stacking_dampener={"enabled": False})
        self.assertEqual(keyword_filter.dampen_stacked_relevancy(row, config), 1.0)


if __name__ == "__main__":
    unittest.main()
