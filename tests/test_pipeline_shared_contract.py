import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUNNER_PATHS = [
    "apps/App_Template/run_pipeline.py",
    "apps/AR_Filter/run_ar_filter_v4_3.py",
    "apps/Control_Widget/run_control_widget_v4_3.py",
    "apps/Game_Emulator/run_game_emulator_v4_4.py",
    "apps/Emoji_Battery_Icon_Customize/run_pipeline.py",
    "apps/Prank_Sounds/run_pipeline.py",
    "apps/FunVid/run_pipeline.py",
]

ROW_AWARE_SHARED_CALLS = [
    "from shared import keyword_filter as _shared_keyword_filter",
    "_shared_keyword_filter.validate_filter_config(config)",
    "_shared_keyword_filter.build_filter_runtime(config)",
    "_shared_keyword_filter.evaluate_hard_filters(row, _filter_runtime)",
    "for column in _shared_keyword_filter.HARD_FILTER_COLUMNS:",
    "_shared_keyword_filter.check_naturalness(r, config)",
    "shared_relevancy = df.apply(lambda r: _shared_keyword_filter.calculate_relevancy(r, config), axis=1)",
    "_shared_keyword_filter.calculate_volume_score(",
    "_shared_keyword_filter.is_shortlist_volume_eligible(",
    "_shared_keyword_filter.selection_cache_path(",
    "_shared_keyword_filter.atomic_write_json(",
]


class PipelineSharedContractTests(unittest.TestCase):
    def test_all_runners_use_row_aware_shared_keyword_logic(self):
        for relative_path in RUNNER_PATHS:
            absolute_path = os.path.join(PROJECT_ROOT, *relative_path.split("/"))
            with self.subTest(runner=relative_path):
                with open(absolute_path, "r", encoding="utf-8") as runner_file:
                    source = runner_file.read()
                for expected_call in ROW_AWARE_SHARED_CALLS:
                    self.assertIn(expected_call, source)
                self.assertNotIn("Falling back to legacy filter logic", source)
                self.assertNotIn("ssl.CERT_NONE", source)
                self.assertNotIn("_create_unverified_context", source)
                self.assertIn("_shared_translation_service.translate_dataframe(", source)
                self.assertIn('market=config.get("market", "")', source)
                self.assertIn("_shared_profile_service.get_app_profile(", source)
                self.assertEqual(source.count("_shared_text_dedup.prepare_dataframe("), 1)
                self.assertNotIn("ReviewVariants", source)
                self.assertIn(
                    "cols_shortlist = ['Keyword', 'EN', 'Volume', 'Max. Volume', 'Difficulty', 'KEI', 'Rank', 'BalancedScore'",
                    source,
                )

    def test_game_emulator_shortlist_quotas_do_not_mix_candidate_buckets(self):
        runner_path = os.path.join(PROJECT_ROOT, "apps", "Game_Emulator", "run_game_emulator_v4_4.py")
        with open(runner_path, "r", encoding="utf-8") as runner_file:
            source = runner_file.read()

        self.assertIn("entry['Section'] = section", source)
        self.assertNotIn("def apply_volume_penalty", source)
        self.assertIn("core_candidates = df_sorted[df_sorted['Bucket'] == 'Core Intent Final']", source)
        self.assertIn("broad_candidates = df_sorted[df_sorted['Bucket'] == 'Broad Expansion']", source)
        self.assertIn("consider_candidates = df_sorted[df_sorted['Bucket'] == 'Consider Keywords'].copy()", source)
        self.assertNotIn("core_candidates = df_sorted[df_sorted['Bucket'].isin(eligible_buckets)]", source)
        self.assertNotIn("broad_candidates = df_sorted[df_sorted['Bucket'].isin(eligible_buckets)]", source)
        self.assertNotIn("consider_candidates = df_sorted[df_sorted['Bucket'].isin(eligible_buckets)].copy()", source)

    def test_game_emulator_runner_is_registered_as_v4_4(self):
        registry_path = os.path.join(PROJECT_ROOT, "shared", "app_registry.py")
        with open(registry_path, "r", encoding="utf-8") as registry_file:
            source = registry_file.read()

        self.assertIn('"runner": "apps/Game_Emulator/run_game_emulator_v4_4.py"', source)
        self.assertNotIn('"runner": "apps/Game_Emulator/run_game_emulator_v4_3.py"', source)


if __name__ == "__main__":
    unittest.main()
