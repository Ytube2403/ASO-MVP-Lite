import os
import unittest

from shared.app_registry import APP_REGISTRY
from shared.effective_config import resolve_effective_app

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUNNER_PATHS = [
    "apps/App_Template/run_pipeline.py",
    "apps/AR_Filter/run_ar_filter_v4_3.py",
    "apps/Control_Widget/run_control_widget_v4_3.py",
    "apps/Game_Emulator/run_game_emulator_v4_4.py",
    "apps/Emoji_Battery_Icon_Customize/run_pipeline.py",
    "apps/Prank_Sounds/run_pipeline.py",
    "apps/FunVid/run_pipeline.py",
    "apps/ElectricGun/run_pipeline.py",
    "apps/NDS_Emulator/run_pipeline.py",
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
    "_shared_keyword_filter.build_main_keyword_shortlist(df, config)",
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
                self.assertIn("from shared import agentic_keyword_classifier as _shared_ai_keyword_classifier", source)
                self.assertIn("agentic_keyword_analysis.sqlite3", source)
                self.assertNotIn('"ai_keyword' + '_analysis.sqlite3"', source)
                self.assertIn("from shared import en_gloss_resolver as _shared_en_gloss_resolver", source)
                self.assertIn("_shared_en_gloss_resolver.resolve_dataframe(", source)
                self.assertNotIn("translation" + "_service", source)
                self.assertNotIn("translate_dataframe(", source)
                self.assertNotIn("DEE" + "PSEEK", source)
                self.assertNotIn("deep" + "seek", source.lower())
                self.assertIn('market=config.get("market", "")', source)
                self.assertIn("_shared_profile_service.get_app_profile(", source)
                self.assertNotIn("def build_shortlist(df_all, config):", source)
                self.assertEqual(source.count("_shared_text_dedup.prepare_dataframe("), 0)
                self.assertNotIn("ReviewVariants", source)
                self.assertIn(
                    "cols_shortlist = ['Keyword', 'EN', 'Volume', 'Max. Volume', 'Difficulty', 'KEI', 'Rank', 'BalancedScore'",
                    source,
                )

    def test_all_runners_use_shared_shortlist_builder_contract(self):
        for relative_path in RUNNER_PATHS:
            absolute_path = os.path.join(PROJECT_ROOT, *relative_path.split("/"))
            with self.subTest(runner=relative_path):
                with open(absolute_path, "r", encoding="utf-8") as runner_file:
                    source = runner_file.read()

                self.assertIn("_shared_keyword_filter.build_main_keyword_shortlist(df, config)", source)
                self.assertNotIn("def build_shortlist(df_all, config):", source)
                self.assertIn("selected_core_feature", source)
                self.assertIn("shortlist_result.feature", source)
                self.assertIn("selected_core + selected_core_feature + selected_broad + selected_consider", source)

        shared_path = os.path.join(PROJECT_ROOT, "shared", "keyword_filter", "shortlist.py")
        with open(shared_path, "r", encoding="utf-8") as shared_file:
            shared_source = shared_file.read()
        self.assertIn('"core_intent": 25', shared_source)
        self.assertIn('"core_feature": 5', shared_source)
        self.assertIn('"broad_expansion": 5', shared_source)
        self.assertIn('"consider": 5', shared_source)
        self.assertIn('"Feature Keywords": ["Feature Keywords", "System Keywords"]', shared_source)
        self.assertIn('"target_count": 40', shared_source)

    def test_all_registered_apps_default_to_new_main_shortlist_quota(self):
        for app_key in APP_REGISTRY:
            with self.subTest(app=app_key):
                _, _, config, _ = resolve_effective_app(app_key, PROJECT_ROOT, "US_EN")
                main_file = (config.get("keyword_quota", {}) or {}).get("main_file", {}) or {}
                self.assertEqual(main_file.get("core_intent"), 25)
                self.assertEqual(main_file.get("core_feature"), 5)
                self.assertEqual(main_file.get("broad_expansion"), 5)
                self.assertEqual(main_file.get("consider"), 5)

    def test_game_emulator_runner_is_registered_as_v4_4(self):
        registry_path = os.path.join(PROJECT_ROOT, "shared", "app_registry.py")
        with open(registry_path, "r", encoding="utf-8") as registry_file:
            source = registry_file.read()

        self.assertIn('"runner": "apps/Game_Emulator/run_game_emulator_v4_4.py"', source)
        self.assertNotIn('"runner": "apps/Game_Emulator/run_game_emulator_v4_3.py"', source)

    def test_all_registered_apps_use_agentic_cache_only_config(self):
        for app_key in APP_REGISTRY:
            with self.subTest(app=app_key):
                _, _, config, _ = resolve_effective_app(app_key, PROJECT_ROOT, "US_EN")
                classifier = config.get("agentic_keyword_classifier", {})
                self.assertEqual(classifier.get("provider"), "antigravity_subagent")
                self.assertTrue(classifier.get("cache_only"))
                self.assertEqual(classifier.get("cache_path"), ".cache/agentic_keyword_analysis.sqlite3")
                self.assertNotIn("ai_keyword_classifier", config)


if __name__ == "__main__":
    unittest.main()
