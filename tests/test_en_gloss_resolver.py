import unittest

import pandas as pd

from shared.en_gloss_resolver import EnglishGlossError, resolve_dataframe


class EnglishGlossResolverTests(unittest.TestCase):
    def test_resolver_prefers_csv_en_then_agentic_gloss_then_not_required(self):
        frame = pd.DataFrame([
            {"Keyword": "prank", "DetectedLanguage": "en", "LanguageGroup": "PRIMARY", "AIEnglishGloss": ""},
            {"Keyword": "broma", "DetectedLanguage": "es", "LanguageGroup": "PRIMARY", "AIEnglishGloss": "prank"},
            {"Keyword": "sons", "DetectedLanguage": "pt", "LanguageGroup": "PRIMARY", "AIEnglishGloss": "sounds"},
        ])
        provided = pd.Series(["", "joke", ""])

        resolved = resolve_dataframe(frame, provided_en=provided)

        self.assertEqual(resolved["EN"].tolist(), ["prank", "joke", "sounds"])
        self.assertEqual(resolved["TranslationStatus"].tolist(), ["NOT_REQUIRED", "PROVIDED_EN", "AGENTIC_GLOSS"])

    def test_resolver_fails_for_non_english_keyword_missing_gloss(self):
        frame = pd.DataFrame([
            {"Keyword": "broma", "DetectedLanguage": "es", "LanguageGroup": "PRIMARY", "AIEnglishGloss": ""},
        ])

        with self.assertRaisesRegex(EnglishGlossError, "Agentic English gloss is missing"):
            resolve_dataframe(frame)

    def test_prefiltered_hard_risk_keyword_does_not_require_agentic_gloss(self):
        frame = pd.DataFrame([
            {
                "Keyword": "retroarch",
                "DetectedLanguage": "pt",
                "LanguageGroup": "PRIMARY",
                "PreAIAction": "skip_ai",
                "PreAIRule": "competitor_brand",
                "AIStatus": "AI_SKIPPED_PREFILTER",
                "AIEnglishGloss": "",
            },
        ])

        resolved = resolve_dataframe(frame)

        self.assertEqual(resolved["EN"].tolist(), ["retroarch"])
        self.assertEqual(resolved["TranslationStatus"].tolist(), ["PREFILTERED_NOT_REQUIRED"])


if __name__ == "__main__":
    unittest.main()
