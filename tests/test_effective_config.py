import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.effective_config import deep_merge_config


class DeepMergeConfigTests(unittest.TestCase):
    def test_list_values_union_instead_of_replace(self):
        # Reproduces the exact Game_Emulator bug: inline risky_ip_terms had
        # mario/zelda, FILTER_POLICY's shorter list silently discarded them
        # under plain dict.update().
        base = {"risky_ip_terms": ["pokemon", "mario", "zelda", "nintendo", "playstation"]}
        override = {"risky_ip_terms": ["nintendo", "pokemon", "playstation", "sony", "xbox"]}
        merged = deep_merge_config(base, override)
        self.assertEqual(
            merged["risky_ip_terms"],
            ["pokemon", "mario", "zelda", "nintendo", "playstation", "sony", "xbox"],
        )

    def test_nested_dict_merges_key_by_key(self):
        base = {"risk_policy": {"competitor_brand_action": "drop", "risky_ip_action": "consider"}}
        override = {"risk_policy": {"risky_ip_action": "drop"}}
        merged = deep_merge_config(base, override)
        self.assertEqual(
            merged["risk_policy"],
            {"competitor_brand_action": "drop", "risky_ip_action": "drop"},
        )

    def test_scalar_override_wins(self):
        base = {"market": "US_EN", "target_count": 40}
        override = {"market": "BR_PT"}
        merged = deep_merge_config(base, override)
        self.assertEqual(merged["market"], "BR_PT")
        self.assertEqual(merged["target_count"], 40)

    def test_key_only_in_override_is_added(self):
        base = {"a": 1}
        override = {"b": 2}
        merged = deep_merge_config(base, override)
        self.assertEqual(merged, {"a": 1, "b": 2})

    def test_does_not_mutate_inputs(self):
        base = {"risky_ip_terms": ["mario"]}
        override = {"risky_ip_terms": ["nintendo"]}
        deep_merge_config(base, override)
        self.assertEqual(base["risky_ip_terms"], ["mario"])
        self.assertEqual(override["risky_ip_terms"], ["nintendo"])


if __name__ == "__main__":
    unittest.main()
