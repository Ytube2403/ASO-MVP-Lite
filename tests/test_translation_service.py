import json
import os
import sqlite3
import ssl
import tempfile
import unittest
from contextlib import closing
from urllib.parse import parse_qs, urlparse

import pandas as pd

from shared.translation_service import (
    PROVIDER,
    TranslationService,
    TranslationUnavailableError,
    normalize_source_language,
    translate_dataframe,
)


class FakeResponse:
    def __init__(self, translated):
        self.payload = json.dumps([[[translated]]]).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class TranslationServiceTests(unittest.TestCase):
    def test_translate_uses_verified_tls_gtx_and_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contexts = []
            requests = []

            def opener(request, timeout, context):
                contexts.append(context)
                requests.append(request)
                return FakeResponse("funny sounds")

            service = TranslationService(
                os.path.join(temp_dir, "translations.sqlite3"),
                opener=opener,
                sleep=lambda _: None,
                requests_per_second=1000,
            )
            first = service.translate("sonidos divertidos", "es")
            second = service.translate("sonidos divertidos", "es")
            self.assertEqual(first.status, "TRANSLATED")
            self.assertEqual(second.status, "CACHE_HIT")
            self.assertEqual(PROVIDER, "google_gtx")
            self.assertEqual(len(contexts), 1)
            self.assertNotEqual(contexts[0].verify_mode, ssl.CERT_NONE)
            self.assertIn("translate.googleapis.com", requests[0].full_url)
            query = parse_qs(urlparse(requests[0].full_url).query)
            self.assertEqual(query["client"], ["gtx"])
            self.assertEqual(query["sl"], ["es"])
            self.assertEqual(query["tl"], ["en"])

    def test_failed_translation_stops_lite_pipeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            calls = []

            def opener(*args, **kwargs):
                calls.append(1)
                raise OSError("offline")

            service = TranslationService(
                os.path.join(temp_dir, "translations.sqlite3"),
                opener=opener,
                sleep=lambda _: None,
                retries=3,
                requests_per_second=1000,
            )
            with self.assertRaises(TranslationUnavailableError):
                service.translate("broma", "es")
            self.assertEqual(len(calls), 3)

    def test_mixed_and_unknown_sources_use_auto(self):
        self.assertEqual(normalize_source_language("fil+en"), "auto")
        self.assertEqual(normalize_source_language("pt+en"), "auto")
        self.assertEqual(normalize_source_language("unknown"), "auto")
        self.assertEqual(normalize_source_language(""), "auto")
        self.assertEqual(normalize_source_language("es"), "es")

    def test_legacy_mixed_cache_is_reused_before_gtx_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = os.path.join(temp_dir, "translations.sqlite3")
            calls = []

            def opener(*args, **kwargs):
                calls.append(1)
                raise OSError("network should not be used")

            service = TranslationService(cache_path, opener=opener)
            with closing(sqlite3.connect(cache_path)) as connection:
                connection.execute(
                    """
                    INSERT INTO translations (
                        provider, source_language, target_language, normalized_keyword, translated_text, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    ("google_gtx", "pt+en", "en", "sons prank", "prank sounds", 1.0),
                )
                connection.commit()
            result = service.translate("sons prank", "pt+en")
            self.assertEqual(result.text, "prank sounds")
            self.assertEqual(result.status, "CACHE_HIT")
            self.assertEqual(calls, [])

    def test_dataframe_records_provided_and_not_required(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            frame = pd.DataFrame([
                {"Keyword": "prank", "DetectedLanguage": "en"},
                {"Keyword": "broma", "DetectedLanguage": "es"},
            ])
            translated = translate_dataframe(
                frame,
                provided_en=pd.Series(["", "prank"]),
                cache_path=os.path.join(temp_dir, "translations.sqlite3"),
            )
            self.assertEqual(list(translated["TranslationStatus"]), ["NOT_REQUIRED", "PROVIDED_EN"])

    def test_rate_limit_reserves_global_request_slots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sleeps = []
            service = TranslationService(
                os.path.join(temp_dir, "translations.sqlite3"),
                sleep=sleeps.append,
                clock=lambda: 100.0,
                requests_per_second=2,
            )
            service._reserve_request()
            service._reserve_request()
            self.assertEqual(sleeps, [0.5])


if __name__ == "__main__":
    unittest.main()
