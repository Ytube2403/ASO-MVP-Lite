import json
import os
import sqlite3
import ssl
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass

from shared.keyword_filter.matcher import normalize_filter_text


PROVIDER = "google_gtx"
TARGET_LANGUAGE = "en"
TRANSLATION_COLUMNS = ["TranslationStatus", "TranslationError"]
DEFAULT_REQUESTS_PER_SECOND = 5
DEFAULT_MAX_WORKERS = 10


def normalize_source_language(source_language, market="", target_language=TARGET_LANGUAGE):
    language = str(source_language or "").strip().lower().replace("_", "-")
    if not language or language == "unknown" or "+" in language:
        return "auto"
    return language


@dataclass(frozen=True)
class TranslationResult:
    text: str
    status: str
    error: str = ""


class TranslationUnavailableError(RuntimeError):
    pass


class TranslationService:
    def __init__(
        self,
        cache_path,
        requests_per_second=None,
        retries=3,
        timeout=5,
        opener=None,
        sleep=None,
        clock=None,
        market="",
        cache_only=False,
    ):
        self.cache_path = os.path.abspath(cache_path)
        configured_rps = (
            requests_per_second
            if requests_per_second is not None
            else os.environ.get("ASO_TRANSLATION_RPS", DEFAULT_REQUESTS_PER_SECOND)
        )
        self.requests_per_second = max(float(configured_rps), 0.1)
        self.retries = max(int(retries), 1)
        self.timeout = float(timeout)
        self.opener = opener or urllib.request.urlopen
        self.sleep = sleep or time.sleep
        self.clock = clock or time.time
        self.market = str(market or "")
        self.cache_only = bool(cache_only)
        self._initialize_cache()

    def _connect(self):
        connection = sqlite3.connect(self.cache_path, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize_cache(self):
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS translations (
                    provider TEXT NOT NULL,
                    source_language TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    normalized_keyword TEXT NOT NULL,
                    translated_text TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (provider, source_language, target_language, normalized_keyword)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_limit (
                    provider TEXT PRIMARY KEY,
                    next_request_at REAL NOT NULL
                )
                """
            )
            connection.commit()

    def _cache_key(self, keyword, source_language, target_language, normalize_source=True):
        source = (
            normalize_source_language(source_language, self.market, target_language)
            if normalize_source
            else str(source_language or "auto").strip().lower()
        )
        return (
            PROVIDER,
            source,
            str(target_language or TARGET_LANGUAGE).lower(),
            normalize_filter_text(keyword),
        )

    def _get_cached(self, keyword, source_language, target_language):
        normalized_key = self._cache_key(keyword, source_language, target_language)
        legacy_key = self._cache_key(keyword, source_language, target_language, normalize_source=False)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT translated_text FROM translations
                WHERE provider = ? AND source_language = ? AND target_language = ? AND normalized_keyword = ?
                """,
                normalized_key,
            ).fetchone()
            if row is None and legacy_key != normalized_key:
                row = connection.execute(
                    """
                    SELECT translated_text FROM translations
                    WHERE provider = ? AND source_language = ? AND target_language = ? AND normalized_keyword = ?
                    """,
                    legacy_key,
                ).fetchone()
        return row[0] if row else None

    def _store_cached(self, keyword, source_language, target_language, translated_text):
        key = self._cache_key(keyword, source_language, target_language)
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO translations (
                    provider, source_language, target_language, normalized_keyword, translated_text, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, source_language, target_language, normalized_keyword)
                DO UPDATE SET translated_text = excluded.translated_text, updated_at = excluded.updated_at
                """,
                (*key, str(translated_text), self.clock()),
            )
            connection.commit()

    def _reserve_request(self):
        interval = 1.0 / self.requests_per_second
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT next_request_at FROM rate_limit WHERE provider = ?",
                (PROVIDER,),
            ).fetchone()
            now = self.clock()
            request_at = max(now, row[0] if row else now)
            connection.execute(
                """
                INSERT INTO rate_limit(provider, next_request_at) VALUES (?, ?)
                ON CONFLICT(provider) DO UPDATE SET next_request_at = excluded.next_request_at
                """,
                (PROVIDER, request_at + interval),
            )
            connection.commit()
        wait_time = request_at - self.clock()
        if wait_time > 0:
            self.sleep(wait_time)

    def _fetch(self, keyword, source_language, target_language):
        self._reserve_request()
        query = urllib.parse.urlencode({
            "client": "gtx",
            "sl": normalize_source_language(source_language, self.market, target_language),
            "tl": str(target_language or TARGET_LANGUAGE).lower(),
            "dt": "t",
            "q": str(keyword),
        })
        request = urllib.request.Request(
            f"https://translate.googleapis.com/translate_a/single?{query}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        context = ssl.create_default_context()
        with self.opener(request, timeout=self.timeout, context=context) as response:
            data = json.loads(response.read().decode("utf-8"))
        translated = "".join(part[0] for part in data[0] if part and part[0])
        if not translated:
            raise ValueError("Google GTX returned an empty response")
        return translated

    def translate(self, keyword, source_language="auto", target_language=TARGET_LANGUAGE, market=""):
        keyword = str(keyword or "")
        if market:
            self.market = str(market)
        if normalize_source_language(source_language, self.market, target_language) == target_language.lower():
            return TranslationResult(keyword, "NOT_REQUIRED")
        cached = self._get_cached(keyword, source_language, target_language)
        if cached is not None:
            return TranslationResult(cached, "CACHE_HIT")
        if self.cache_only:
            raise TranslationUnavailableError(
                "Translation service is running in cache_only mode, but this keyword "
                f"is missing an English gloss/cache entry: {keyword!r}"
            )
        errors = []
        for attempt in range(self.retries):
            try:
                translated = self._fetch(keyword, source_language, target_language)
                self._store_cached(keyword, source_language, target_language, translated)
                return TranslationResult(translated, "TRANSLATED")
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
                if attempt + 1 < self.retries:
                    self.sleep(0.5 * (2 ** attempt))
        raise TranslationUnavailableError(
            "Google GTX translation failed after retries. "
            "Lite uses a free unofficial endpoint, so retry later or use ASO-MVP-Max. "
            f"Details: {' | '.join(errors)[-1000:]}"
        )


def translate_dataframe(df, provided_en=None, cache_path=None, max_workers=None, service=None, market="", cache_only=False):
    import pandas as pd

    if cache_path is None:
        cache_path = os.path.join(os.getcwd(), ".cache", "translations.sqlite3")
    service = service or TranslationService(cache_path, market=market, cache_only=cache_only)
    if market:
        service.market = str(market)
    service.cache_only = bool(cache_only)
    configured_workers = (
        max_workers
        if max_workers is not None
        else os.environ.get("ASO_TRANSLATION_MAX_WORKERS", DEFAULT_MAX_WORKERS)
    )
    provided = provided_en if provided_en is not None else pd.Series("", index=df.index)
    tasks = {}
    results = {}
    for index, row in df.iterrows():
        keyword = str(row.get("Keyword", "") or "")
        source_language = str(row.get("DetectedLanguage", "auto") or "auto").lower()
        supplied = str(provided.get(index, "") or "").strip()
        if supplied:
            results[index] = TranslationResult(supplied, "PROVIDED_EN")
        elif source_language == TARGET_LANGUAGE:
            results[index] = TranslationResult(keyword, "NOT_REQUIRED")
        else:
            tasks.setdefault((keyword, source_language), []).append(index)

    def worker(task):
        keyword, source_language = task
        return task, service.translate(keyword, source_language)

    with ThreadPoolExecutor(max_workers=max(1, int(configured_workers))) as executor:
        for task, result in executor.map(worker, tasks):
            for index in tasks[task]:
                results[index] = result
    ordered = [results[index] for index in df.index]
    status_counts = {}
    for result in ordered:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1
    if tasks:
        print(
            "Translation summary: "
            f"provider={PROVIDER}, cache_hit={status_counts.get('CACHE_HIT', 0)}, "
            f"translated={status_counts.get('TRANSLATED', 0)}"
        )
    return pd.DataFrame(
        {
            "EN": [result.text for result in ordered],
            "TranslationStatus": [result.status for result in ordered],
            "TranslationError": [result.error for result in ordered],
        },
        index=df.index,
    )
