import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.consolidate_shortlists import get_first


class ConsolidateShortlistsTests(unittest.TestCase):
    def test_get_first_uses_later_keys_as_real_fallbacks(self):
        row_data = {
            "#": 7,
            "group": "Broad Expansion",
            "decisionreason": "Fallback reason",
        }

        self.assertEqual(get_first(row_data, "rank", "#"), 7)
        self.assertEqual(get_first(row_data, "bucket", "group"), "Broad Expansion")
        self.assertEqual(get_first(row_data, "reason", "decisionreason"), "Fallback reason")


if __name__ == "__main__":
    unittest.main()
