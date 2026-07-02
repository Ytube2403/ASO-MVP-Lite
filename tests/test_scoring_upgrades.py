import math
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.keyword_filter import scoring


REF = 100000.0
LOG_CFG = {"volume_score_policy": {"mode": "log_reach", "reach_reference": REF}}


class LogReachVolumeTests(unittest.TestCase):
    def test_log_reach_gives_meaningful_spread_for_midtier(self):
        # Real data: vol10 ~ reach 280, vol57 ~ reach 31642. Linear crushes both to ~0;
        # log must keep them well separated and non-trivial.
        s280 = scoring.calculate_volume_score(50, 50, 280, 0, LOG_CFG)
        s31642 = scoring.calculate_volume_score(50, 50, 31642, 0, LOG_CFG)
        self.assertAlmostEqual(s280, math.log1p(280) / math.log1p(REF), places=4)
        self.assertAlmostEqual(s31642, math.log1p(31642) / math.log1p(REF), places=4)
        self.assertGreater(s280, 0.45)      # 280 real users is NOT worthless
        self.assertGreater(s31642, s280)
        self.assertGreater(s31642, 0.85)

    def test_linear_mode_crushes_midtier(self):
        cfg = {"volume_score_policy": {"mode": "reach_linear", "reach_reference": REF}}
        s280 = scoring.calculate_volume_score(50, 50, 280, 0, cfg)
        self.assertAlmostEqual(s280, 280 / REF, places=6)
        self.assertLess(s280, 0.01)          # this is exactly the problem log fixes

    def test_reach_at_or_above_reference_saturates_to_one(self):
        s = scoring.calculate_volume_score(80, 80, 500000, 0, LOG_CFG)
        self.assertAlmostEqual(s, 1.0, places=6)

    def test_low_tier_volume_still_capped(self):
        # Volume <= low_tier_threshold(5) is capped regardless of mode.
        s = scoring.calculate_volume_score(5, 5, 0, 0, LOG_CFG)
        self.assertLessEqual(s, 0.05)

    def test_reference_zero_falls_back_to_dataset_ceiling(self):
        cfg = {"volume_score_policy": {"mode": "log_reach", "reach_reference": 0}}
        s = scoring.calculate_volume_score(50, 50, 280, 31642, cfg)
        self.assertAlmostEqual(s, math.log1p(280) / math.log1p(31642), places=4)


class BalancedWeightsTests(unittest.TestCase):
    def test_legacy_kein_config_is_migrated(self):
        legacy = {"balanced_weights": {
            "VolumeN": 0.35, "DifficultyN": 0.10, "KEIN": 0.10,
            "RelevancyScore": 0.25, "CurrentRankN": 0.10, "ExpansionValue": 0.10,
        }}
        w = scoring.resolve_balanced_weights(legacy)
        self.assertEqual(w["KEIN"], 0.0)
        self.assertEqual(w["RelevancyScore"], 0.30)
        self.assertEqual(w["DifficultyN"], 0.15)
        self.assertAlmostEqual(sum(w.values()), 1.0, places=6)

    def test_empty_config_uses_new_defaults(self):
        w = scoring.resolve_balanced_weights({})
        self.assertEqual(w, scoring.DEFAULT_BALANCED_WEIGHTS)

    def test_new_scheme_without_kein_is_respected(self):
        cfg = {"balanced_weights": {
            "VolumeN": 0.40, "DifficultyN": 0.10, "RelevancyScore": 0.30,
            "CurrentRankN": 0.10, "ExpansionValue": 0.10,
        }}
        w = scoring.resolve_balanced_weights(cfg)
        self.assertEqual(w["VolumeN"], 0.40)
        self.assertEqual(w["KEIN"], 0.0)  # always present so bw['KEIN'] never KeyErrors


class RubricRelevancyTests(unittest.TestCase):
    def _row(self, bucket, lang="PRIMARY", conf=1.0, rule="ai_core"):
        return {"AISemanticBucket": bucket, "LanguageGroup": lang,
                "AIConfidence": conf, "AIDecisionRule": rule}

    def test_core_primary_high_confidence_is_090(self):
        self.assertAlmostEqual(
            scoring.calculate_rubric_relevancy(self._row("Core Intent Final"), {}), 0.90, places=4
        )

    def test_secondary_language_drops_005(self):
        self.assertAlmostEqual(
            scoring.calculate_rubric_relevancy(self._row("Core Intent Final", lang="SECONDARY"), {}),
            0.85, places=4,
        )

    def test_low_confidence_reduces_by_span(self):
        # conf 0.6667 -> 0.90 - (1-0.6667)*0.15 = 0.85
        self.assertAlmostEqual(
            scoring.calculate_rubric_relevancy(self._row("Core Intent Final", conf=2/3), {}),
            0.85, places=3,
        )

    def test_feature_and_broad_bases(self):
        self.assertAlmostEqual(scoring.calculate_rubric_relevancy(self._row("Feature Keywords"), {}), 0.70, places=4)
        self.assertAlmostEqual(scoring.calculate_rubric_relevancy(self._row("Broad Expansion"), {}), 0.55, places=4)

    def test_foreign_and_dropped_and_unclassified_are_zero(self):
        self.assertEqual(scoring.calculate_rubric_relevancy(self._row("Core Intent Final", lang="FOREIGN"), {}), 0.0)
        self.assertEqual(scoring.calculate_rubric_relevancy(self._row("Dropped"), {}), 0.0)
        self.assertEqual(scoring.calculate_rubric_relevancy(self._row(""), {}), 0.0)

    def test_config_override_bucket_base(self):
        cfg = {"relevancy_rubric": {"bucket_base": {"feature keywords": 0.80}}}
        self.assertAlmostEqual(scoring.calculate_rubric_relevancy(self._row("Feature Keywords"), cfg), 0.80, places=4)
        # unspecified buckets keep their default
        self.assertAlmostEqual(scoring.calculate_rubric_relevancy(self._row("Core Intent Final"), cfg), 0.90, places=4)


if __name__ == "__main__":
    unittest.main()
