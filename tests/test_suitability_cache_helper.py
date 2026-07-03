import json
import os
import tempfile
import unittest

from shared.effective_config import resolve_effective_app
from shared.keyword_filter import suitability
from tools import suitability_cache_helper


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SuitabilityCacheHelperTests(unittest.TestCase):
    def test_validate_result_rejects_keyword_outside_batch(self):
        batch = {"batch_id": "b", "keywords": [{"keyword": "arcade"}]}
        result = {
            "items": [{
                "keyword": "outside",
                "suitability_bucket": "Research Only",
                "metadata_eligible": False,
                "ads_eligible": False,
                "research_only": True,
                "confidence": 0.9,
                "decision_rule": "single_token_too_broad",
                "reason": "Too broad",
            }]
        }
        with self.assertRaisesRegex(ValueError, "not part of the batch"):
            suitability_cache_helper._validate_result_items(result, batch)

    def test_validate_result_rejects_invalid_boolean_and_duplicate(self):
        batch = {"batch_id": "b", "keywords": [{"keyword": "arcade"}]}
        result = {
            "items": [
                {
                    "keyword": "arcade",
                    "suitability_bucket": "Research Only",
                    "metadata_eligible": "maybe",
                    "ads_eligible": False,
                    "research_only": True,
                    "confidence": 0.9,
                    "decision_rule": "single_token_too_broad",
                    "reason": "Too broad",
                },
                {
                    "keyword": "arcade",
                    "suitability_bucket": "Research Only",
                    "metadata_eligible": False,
                    "ads_eligible": False,
                    "research_only": True,
                    "confidence": 0.9,
                    "decision_rule": "single_token_too_broad",
                    "reason": "Too broad",
                },
            ]
        }
        with self.assertRaisesRegex(ValueError, "Invalid boolean value|Duplicate result keyword"):
            suitability_cache_helper._validate_result_items(result, batch)

    def test_find_misses_and_save_results_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "candidates_US_EN.csv")
            cache_path = os.path.join(temp_dir, "agentic.sqlite3")
            misses_path = os.path.join(temp_dir, "misses.json")
            batch_dir = os.path.join(temp_dir, "batches")
            with open(csv_path, "w", encoding="utf-8") as csv_file:
                csv_file.write("Keyword,Bucket,DecisionRule,Volume,LanguageGroup,NaturalnessFlag\n")
                csv_file.write("singleword,Feature Keywords,feature_keywords,50,PRIMARY,OK\n")

            suitability_cache_helper.main([
                "find-misses",
                "--app", "App_Template",
                "--csv", csv_path,
                "--market", "US_EN",
                "--cache-path", cache_path,
                "--output", misses_path,
            ])
            with open(misses_path, "r", encoding="utf-8") as misses_file:
                misses = json.load(misses_file)
            self.assertEqual(misses["missing_count"], 1)

            suitability_cache_helper.main([
                "prepare-batches",
                "--misses", misses_path,
                "--output-dir", batch_dir,
                "--chunk-size", "1",
            ])
            batch_path = os.path.join(batch_dir, "us_en_suitability_batch_1.json")
            result_path = os.path.join(batch_dir, "us_en_suitability_batch_1_result.json")
            with open(result_path, "w", encoding="utf-8") as result_file:
                json.dump({
                    "batch_id": "us_en_suitability_batch_1",
                    "items": [{
                        "keyword": "singleword",
                        "suitability_bucket": "Research Only",
                        "metadata_eligible": False,
                        "ads_eligible": False,
                        "research_only": True,
                        "confidence": 0.8,
                        "decision_rule": "subagent_too_broad",
                        "reason": "Single-word feature is too broad for metadata.",
                    }],
                }, result_file)

            suitability_cache_helper.main([
                "save-results",
                "--app", "App_Template",
                "--batch", batch_path,
                "--results", result_path,
                "--market", "US_EN",
                "--cache-path", cache_path,
            ])

            _, _, config, app_profile = resolve_effective_app("App_Template", PROJECT_ROOT, "US_EN")
            config["market"] = "US_EN"
            cache = suitability.SuitabilityCache(cache_path, config=config, app_profile=app_profile, market="US_EN")
            self.assertEqual(cache.get("singleword").decision_rule, "subagent_too_broad")

            suitability_cache_helper.main([
                "verify-cache",
                "--app", "App_Template",
                "--csv", csv_path,
                "--market", "US_EN",
                "--cache-path", cache_path,
            ])

    def test_save_results_rejects_context_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = os.path.join(temp_dir, "batch.json")
            result_path = os.path.join(temp_dir, "result.json")
            with open(batch_path, "w", encoding="utf-8") as batch_file:
                json.dump({
                    "batch_id": "b",
                    "market": "US_EN",
                    "context_hash": "wrong",
                    "keywords": [{"keyword": "singleword"}],
                }, batch_file)
            with open(result_path, "w", encoding="utf-8") as result_file:
                json.dump({"batch_id": "b", "items": []}, result_file)
            with self.assertRaisesRegex(ValueError, "context_hash"):
                suitability_cache_helper.main([
                    "save-results",
                    "--app", "App_Template",
                    "--batch", batch_path,
                    "--results", result_path,
                    "--market", "US_EN",
                    "--cache-path", os.path.join(temp_dir, "cache.sqlite3"),
                ])


if __name__ == "__main__":
    unittest.main()
