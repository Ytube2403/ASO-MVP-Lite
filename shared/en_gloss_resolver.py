class EnglishGlossError(RuntimeError):
    pass


TARGET_LANGUAGE = "en"
GLOSS_COLUMNS = ["EN", "TranslationStatus", "TranslationError"]


def _provided_value(provided_en, index):
    if provided_en is None:
        return ""
    try:
        return str(provided_en.get(index, "") or "").strip()
    except AttributeError:
        try:
            return str(provided_en[index] or "").strip()
        except (IndexError, KeyError, TypeError):
            return ""


def _is_english(row):
    detected = str(row.get("DetectedLanguage", "") or "").strip().lower()
    group = str(row.get("LanguageGroup", "") or "").strip().upper()
    keyword = str(row.get("Keyword", "") or "")
    if detected == TARGET_LANGUAGE:
        return True
    if detected == "unknown" and group in {"PRIMARY", "SECONDARY"} and keyword.isascii():
        return True
    return False


def _needs_gloss(row):
    if _is_english(row):
        return False
    detected = str(row.get("DetectedLanguage", "") or "").strip().lower()
    group = str(row.get("LanguageGroup", "") or "").strip().upper()
    return detected not in {"", TARGET_LANGUAGE} or group in {"PRIMARY", "SECONDARY", "MIXED", "FOREIGN", "UNKNOWN"}


def resolve_dataframe(df, provided_en=None):
    import pandas as pd

    rows = []
    missing = []
    for index, row in df.iterrows():
        supplied = _provided_value(provided_en, index)
        keyword = str(row.get("Keyword", "") or "")
        gloss = str(row.get("AIEnglishGloss", "") or "").strip()
        if supplied:
            rows.append((supplied, "PROVIDED_EN", ""))
        elif _is_english(row):
            rows.append((keyword, "NOT_REQUIRED", ""))
        elif gloss:
            rows.append((gloss, "AGENTIC_GLOSS", ""))
        elif _needs_gloss(row):
            missing.append(keyword)
            rows.append(("", "MISSING_GLOSS", "Missing agentic english_gloss"))
        else:
            rows.append((keyword, "NOT_REQUIRED", ""))

    if missing:
        sample = ", ".join(missing[:5])
        raise EnglishGlossError(
            "Agentic English gloss is missing for "
            f"{len(missing)} non-English keyword(s). "
            "Run tools/warm_cache_helper.py and save subagent results first. "
            f"Sample misses: {sample}"
        )

    return pd.DataFrame(
        {
            "EN": [row[0] for row in rows],
            "TranslationStatus": [row[1] for row in rows],
            "TranslationError": [row[2] for row in rows],
        },
        index=df.index,
    )
