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

    def test_find_misses_supports_input_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = os.path.join(temp_dir, "Input")
            os.makedirs(input_dir)
            csv_path = os.path.join(input_dir, "App_Template_US_EN.csv")
            cache_path = os.path.join(temp_dir, "agentic.sqlite3")
            output_path = os.path.join(temp_dir, "missing.json")
            with open(csv_path, "w", encoding="utf-8") as csv_file:
                csv_file.write("Keyword,Volume,Rank\nphoto editor,10,\n")

            warm_cache_helper.main([
                "find-misses",
                "--app", "App_Template",
                "--input-dir", input_dir,
                "--cache-path", cache_path,
                "--output", output_path,
            ])

            with open(output_path, "r", encoding="utf-8") as output_file:
                payload = json.load(output_file)
            self.assertIn("US_EN", payload)
            self.assertEqual(payload["US_EN"]["missing_count"], 1)

    def test_verify_cache_returns_nonzero_when_intent_cache_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "App_Template_US_EN.csv")
            cache_path = os.path.join(temp_dir, "agentic.sqlite3")
            with open(csv_path, "w", encoding="utf-8") as csv_file:
                csv_file.write("Keyword,Volume,Rank\nphoto editor,10,\n")

            with self.assertRaises(SystemExit) as raised:
                warm_cache_helper.main([
                    "verify-cache",
                    "--app", "App_Template",
                    "--csv", csv_path,
                    "--market", "US_EN",
                    "--cache-path", cache_path,
                ])

            self.assertEqual(raised.exception.code, 1)

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

    def test_canonical_semantic_bucket_normalizes_case_and_aliases(self):
        self.assertEqual(
            warm_cache_helper._canonical_semantic_bucket("core intent final"),
            "Core Intent Final",
        )
        self.assertEqual(
            warm_cache_helper._canonical_semantic_bucket("FEATURE KEYWORDS"),
            "Feature Keywords",
        )
        self.assertEqual(
            warm_cache_helper._canonical_semantic_bucket("Visual Keywords"),
            "Feature Keywords",
        )
        self.assertIsNone(warm_cache_helper._canonical_semantic_bucket("Not A Bucket"))
        self.assertIsNone(warm_cache_helper._canonical_semantic_bucket(""))

    def test_validate_accepts_lowercase_bucket_and_normalizes_output(self):
        batch = {
            "batch_id": "mx_es_batch_1",
            "keywords": [{"keyword": "emulador", "reason": "missing_agentic_cache"}],
        }
        result = {
            "items": [{
                "keyword": "emulador",
                "detected_language": "es",
                "language_group": "primary",
                "semantic_bucket": "core intent final",
                "decision_rule": "ai_core",
                "reason": "Relevant.",
                "confidence": 0.9,
                "english_gloss": "emulator",
            }]
        }
        validated, errors = warm_cache_helper._validate_result_items(result, batch)
        self.assertEqual(errors, [])
        self.assertEqual(validated[0]["semantic_bucket"], "Core Intent Final")
        self.assertEqual(validated[0]["language_group"], "PRIMARY")

    def test_validate_partial_collects_errors_and_keeps_valid_items(self):
        batch = {
            "batch_id": "b",
            "keywords": [
                {"keyword": "good"},
                {"keyword": "badbucket"},
                {"keyword": "noconf"},
            ],
        }
        result = {
            "items": [
                {
                    "keyword": "good", "detected_language": "en", "language_group": "PRIMARY",
                    "semantic_bucket": "Feature Keywords", "decision_rule": "r", "reason": "x",
                    "confidence": 0.8, "english_gloss": "",
                },
                {
                    "keyword": "badbucket", "detected_language": "en", "language_group": "PRIMARY",
                    "semantic_bucket": "Nope", "decision_rule": "r", "reason": "x",
                    "confidence": 0.8, "english_gloss": "",
                },
                {
                    "keyword": "noconf", "detected_language": "en", "language_group": "PRIMARY",
                    "semantic_bucket": "Feature Keywords", "decision_rule": "r", "reason": "x",
                    "confidence": "abc", "english_gloss": "",
                },
            ]
        }
        validated, errors = warm_cache_helper._validate_result_items(result, batch, partial=True)
        self.assertEqual([item["keyword"] for item in validated], ["good"])
        self.assertEqual(len(errors), 2)

    def test_update_english_gloss_preserves_existing_classification(self):
        from shared.agentic_keyword_classifier import AIKeywordAnalysis, AIKeywordClassifier

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = os.path.join(temp_dir, "agentic.sqlite3")
            _, _, config, app_profile = resolve_effective_app("App_Template", PROJECT_ROOT, "MX_ES")
            config["market"] = "MX_ES"
            service = AIKeywordClassifier(
                cache_path, config=config, app_profile=app_profile, market="MX_ES"
            )
            service._store_cached(
                AIKeywordAnalysis(
                    keyword="emulador",
                    detected_language="es",
                    language_group="PRIMARY",
                    semantic_bucket="Core Intent Final",
                    decision_rule="ai_core_intent",
                    reason="core",
                    confidence=0.9,
                    english_gloss="",
                ),
                {"source": "seed"},
            )

            self.assertTrue(service._update_english_gloss("emulador", "emulator"))
            cached = service._get_cached("emulador")
            self.assertEqual(cached.english_gloss, "emulator")
            # classification fields must be untouched by a gloss-only fill
            self.assertEqual(cached.semantic_bucket, "Core Intent Final")
            self.assertEqual(cached.confidence, 0.9)
            self.assertEqual(cached.decision_rule, "ai_core_intent")

            # no matching row -> reports nothing updated
            self.assertFalse(service._update_english_gloss("missing", "x"))


if __name__ == "__main__":
    unittest.main()
