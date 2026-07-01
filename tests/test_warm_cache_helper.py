import json
import os
import tempfile
import unittest

from shared.effective_config import resolve_effective_app
from tools import warm_cache_helper


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class WarmCacheHelperTests(unittest.TestCase):
    def test_game_emulator_effective_config_uses_agentic_classifier_and_filter_policy(self):
        _, _, config, _ = resolve_effective_app("Game_Emulator", PROJECT_ROOT, "MX_ES")

        classifier = config.get("agentic_keyword_classifier", {})
        self.assertEqual(classifier.get("provider"), "antigravity_subagent")
        self.assertTrue(classifier.get("cache_only"))
        self.assertIn("pokemon", config.get("risky_ip_terms", []))

    def test_prepare_batches_writes_contract_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            misses_path = os.path.join(temp_dir, "misses.json")
            output_dir = os.path.join(temp_dir, "batches")
            with open(misses_path, "w", encoding="utf-8") as misses_file:
                json.dump({
                    "app_id": "com.example",
                    "app_name": "Example",
                    "market": "MX_ES",
                    "context_hash": "ctx",
                    "missing_count": 2,
                    "missing_keywords": [
                        {"keyword": "uno", "volume": 1, "rank": ""},
                        {"keyword": "dos", "volume": 2, "rank": ""},
                    ],
                }, misses_file)

            warm_cache_helper.main([
                "prepare-batches",
                "--misses", misses_path,
                "--output-dir", output_dir,
                "--chunk-size", "1",
            ])

            batch_path = os.path.join(output_dir, "mx_es_batch_1.json")
            with open(batch_path, "r", encoding="utf-8") as batch_file:
                batch = json.load(batch_file)
            self.assertEqual(batch["batch_id"], "mx_es_batch_1")
            self.assertEqual(batch["context_hash"], "ctx")
            self.assertEqual(len(batch["keywords"]), 1)

    def test_validate_result_rejects_keyword_outside_batch(self):
        batch = {
            "batch_id": "mx_es_batch_1",
            "keywords": [{"keyword": "emulador", "volume": 1, "rank": ""}],
        }
        result = {
            "items": [{
                "keyword": "outside",
                "detected_language": "es",
                "language_group": "PRIMARY",
                "semantic_bucket": "Core Intent Final",
                "decision_rule": "agentic_core_intent",
                "reason": "Relevant.",
                "confidence": 0.9,
                "english_gloss": "emulator",
            }]
        }
        with self.assertRaisesRegex(ValueError, "not part of the batch"):
            warm_cache_helper._validate_result_items(result, batch)

    def test_validate_result_requires_english_gloss_for_non_english_keywords(self):
        batch = {
            "batch_id": "mx_es_batch_1",
            "keywords": [{"keyword": "emulador", "volume": 1, "rank": ""}],
        }
        result = {
            "items": [{
                "keyword": "emulador",
                "detected_language": "es",
                "language_group": "PRIMARY",
                "semantic_bucket": "Core Intent Final",
                "decision_rule": "agentic_core_intent",
                "reason": "Relevant.",
                "confidence": 0.9,
                "english_gloss": "",
            }]
        }
        with self.assertRaisesRegex(ValueError, "english_gloss is required"):
            warm_cache_helper._validate_result_items(result, batch)

    def test_validate_result_rejects_invalid_bucket(self):
        batch = {
            "batch_id": "mx_es_batch_1",
            "keywords": [{"keyword": "emulator", "volume": 1, "rank": ""}],
        }
        result = {
            "items": [{
                "keyword": "emulator",
                "detected_language": "en",
                "language_group": "PRIMARY",
                "semantic_bucket": "Not A Bucket",
                "decision_rule": "agentic_core_intent",
                "reason": "Relevant.",
                "confidence": 0.9,
                "english_gloss": "",
            }]
        }
        with self.assertRaisesRegex(ValueError, "Invalid semantic_bucket"):
            warm_cache_helper._validate_result_items(result, batch)


if __name__ == "__main__":
    unittest.main()
