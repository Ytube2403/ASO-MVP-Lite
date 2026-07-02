import argparse
import json
import os
import sys

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared import agentic_keyword_classifier
from shared.agentic_keyword_classifier import (
    AIKeywordAnalysis,
    AIKeywordClassifier,
    LANGUAGE_GROUPS,
    SEMANTIC_BUCKETS,
)
from shared.app_registry import registered_aliases
from shared.effective_config import resolve_effective_app
from shared.language_detector import detect_keyword_language
from shared.locale_parser import extract_locale_from_filename


DEFAULT_BATCH_SIZE = 200
DEFAULT_BATCH_DIR = os.path.join(PROJECT_ROOT, ".cache", "agentic_batches")

# Case-insensitive lookup from a subagent-provided bucket label to the canonical
# name expected by the cache. Also folds legacy "Visual*" labels into Feature.
_CANONICAL_BUCKETS = {bucket.lower(): bucket for bucket in SEMANTIC_BUCKETS}
_BUCKET_ALIASES = {
    "visual keywords": "Feature Keywords",
    "visual": "Feature Keywords",
    "visuals": "Feature Keywords",
    "ui keywords": "Feature Keywords",
}


def _canonical_semantic_bucket(raw_value):
    """Return the canonical bucket name for a subagent label, or None if unknown."""
    key = str(raw_value or "").strip().lower()
    if not key:
        return None
    if key in _BUCKET_ALIASES:
        return _BUCKET_ALIASES[key]
    return _CANONICAL_BUCKETS.get(key)


def _read_csv(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    if "Keyword" not in frame.columns:
        raise ValueError("Input CSV must contain a Keyword column")
    if "Volume" not in frame.columns:
        frame["Volume"] = 0
    if "Rank" not in frame.columns:
        frame["Rank"] = ""
    return frame


def _resolve_app_context(app_alias, market):
    try:
        return resolve_effective_app(app_alias, PROJECT_ROOT, market)
    except KeyError as exc:
        aliases = ", ".join(registered_aliases())
        raise SystemExit(f"{exc}\nKnown aliases: {aliases}") from exc


def _resolve_cache_path(config, explicit_cache_path=""):
    if explicit_cache_path:
        cache_path = explicit_cache_path
    else:
        classifier_config = agentic_keyword_classifier._classifier_config(config)
        cache_path = classifier_config.get("cache_path") or ".cache/agentic_keyword_analysis.sqlite3"
    if not os.path.isabs(cache_path):
        cache_path = os.path.join(PROJECT_ROOT, cache_path)
    return cache_path


def _context_hash(config, app_profile):
    return agentic_keyword_classifier._context_hash(config, app_profile)


def _scan_misses(app_alias, csv_path, market, cache_path=""):
    _, _, config, app_profile = _resolve_app_context(app_alias, market)
    market = market or config.get("market", "") or extract_locale_from_filename(csv_path, "")
    if market:
        config["market"] = market
    frame = _read_csv(csv_path)
    resolved_cache_path = _resolve_cache_path(config, cache_path)
    service = AIKeywordClassifier(resolved_cache_path, config=config, app_profile=app_profile, market=market)
    classifier_config = agentic_keyword_classifier._classifier_config(config)

    rows = [row.to_dict() for _, row in frame.iterrows()]
    pre_ai_items = agentic_keyword_classifier._build_pre_ai_items(rows, config, classifier_config)

    missing = []
    for item in pre_ai_items:
        cached = service._get_cached(item.keyword)
        provided_en = str(item.row.get("EN", "") or "").strip()
        if cached is None:
            detected_language, _ = detect_keyword_language(item.keyword, market, config)
            requires_cache = item.needs_ai or (not provided_en and detected_language != "en")
            if not requires_cache:
                continue
            missing.append({
                "keyword": item.keyword,
                "volume": int(item.row.get("Volume", 0) or 0),
                "rank": str(item.row.get("Rank", "") or ""),
                "reason": "missing_agentic_cache",
            })
            continue
        if cached.detected_language.lower() != "en" and not str(cached.english_gloss or "").strip():
            missing.append({
                "keyword": item.keyword,
                "volume": int(item.row.get("Volume", 0) or 0),
                "rank": str(item.row.get("Rank", "") or ""),
                "reason": "missing_english_gloss",
            })

    return {
        "app_id": config.get("app_id", ""),
        "app_name": config.get("app_name", ""),
        "market": market,
        "context_hash": _context_hash(config, app_profile),
        "missing_count": len(missing),
        "missing_keywords": missing,
    }


def _write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2)


def _load_json(path):
    with open(path, "r", encoding="utf-8") as input_file:
        return json.load(input_file)


def _iter_missing_markets(payload):
    if "missing_keywords" in payload:
        yield payload
        return
    for market, market_payload in payload.items():
        if isinstance(market_payload, dict):
            item = dict(market_payload)
            item.setdefault("market", market)
            yield item


def _keyword_value(item):
    if isinstance(item, dict):
        return str(item.get("keyword", "") or "").strip()
    return str(item or "").strip()


def _batch_payload(missing_payload, chunk, batch_index, total_batches):
    market = str(missing_payload.get("market", "") or "")
    batch_id = f"{market.lower()}_batch_{batch_index}"
    return {
        "app_id": missing_payload.get("app_id", ""),
        "app_name": missing_payload.get("app_name", ""),
        "market": market,
        "context_hash": missing_payload.get("context_hash", ""),
        "batch_id": batch_id,
        "batch_index": batch_index,
        "total_batches": total_batches,
        "keywords": chunk,
    }


def _result_path_for_batch(batch_path):
    stem, ext = os.path.splitext(batch_path)
    return f"{stem}_result{ext or '.json'}"


def _remaining_path_for_batch(batch_path):
    stem, ext = os.path.splitext(batch_path)
    return f"{stem}_remaining{ext or '.json'}"


def _validate_result_items(result_payload, batch_payload, partial=False):
    """Validate subagent results against the batch.

    Returns ``(validated_items, errors)``. Per-item and coverage problems are
    collected instead of aborting on the first one, so a single bad keyword no
    longer forces a re-spawn of the whole batch. When ``partial`` is False the
    collected errors are raised together (preserving the original fail-fast
    contract); when True the caller decides what to do with the valid subset.
    Structural problems (no items[] list, batch_id mismatch) still raise
    immediately since nothing can be salvaged.
    """
    items = result_payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Result JSON must contain an items[] list")

    if result_payload.get("batch_id") and result_payload["batch_id"] != batch_payload.get("batch_id"):
        raise ValueError("Result batch_id does not match batch input")

    expected_keywords = {_keyword_value(item) for item in batch_payload.get("keywords", [])}
    expected_keywords.discard("")
    seen_keywords = set()
    validated = []
    errors = []

    for item in items:
        if not isinstance(item, dict):
            errors.append("Every result item must be an object")
            continue
        keyword = str(item.get("keyword", "") or "").strip()
        if keyword not in expected_keywords:
            errors.append(f"Result keyword is not part of the batch: {keyword!r}")
            continue
        if keyword in seen_keywords:
            errors.append(f"Duplicate result keyword: {keyword!r}")
            continue
        seen_keywords.add(keyword)

        item_errors = []

        language_group = str(item.get("language_group", "") or "").strip().upper()
        if language_group not in LANGUAGE_GROUPS:
            item_errors.append(f"Invalid language_group for {keyword!r}: {language_group!r}")

        canonical_bucket = _canonical_semantic_bucket(item.get("semantic_bucket", ""))
        if canonical_bucket is None:
            raw_bucket = str(item.get("semantic_bucket", "") or "").strip()
            item_errors.append(f"Invalid semantic_bucket for {keyword!r}: {raw_bucket!r}")

        try:
            confidence = float(item.get("confidence", ""))
            if not 0.0 <= confidence <= 1.0:
                item_errors.append(f"Confidence must be between 0 and 1 for {keyword!r}")
        except (TypeError, ValueError):
            item_errors.append(f"Invalid confidence for {keyword!r}")

        detected_language = str(item.get("detected_language", "") or "").strip().lower()
        english_gloss = str(item.get("english_gloss", "") or "").strip()
        if detected_language != "en" and not english_gloss:
            item_errors.append(f"english_gloss is required for non-English keyword {keyword!r}")

        for field in ("decision_rule", "reason"):
            if not str(item.get(field, "") or "").strip():
                item_errors.append(f"Missing {field} for {keyword!r}")

        if item_errors:
            errors.extend(item_errors)
            continue

        normalized = dict(item)
        normalized["semantic_bucket"] = canonical_bucket
        normalized["language_group"] = language_group
        validated.append(normalized)

    validated_keywords = {str(item["keyword"]).strip() for item in validated}
    missing_results = expected_keywords - validated_keywords
    if missing_results and not partial:
        sample = ", ".join(sorted(missing_results)[:5])
        errors.append(f"Result JSON is missing {len(missing_results)} batch keyword(s): {sample}")

    if errors and not partial:
        raise ValueError("; ".join(errors))

    return validated, errors


def _save_validated_results(args):
    batch_payload = _load_json(args.batch)
    result_payload = _load_json(args.results)
    market = args.market or batch_payload.get("market", "")
    _, _, config, app_profile = _resolve_app_context(args.app, market)
    config["market"] = market
    expected_context_hash = _context_hash(config, app_profile)
    if batch_payload.get("context_hash") != expected_context_hash:
        raise ValueError(
            "Batch context_hash does not match current app config. "
            "Regenerate misses and batches before saving results."
        )

    partial = getattr(args, "partial", False)
    items, errors = _validate_result_items(result_payload, batch_payload, partial=partial)
    cache_path = _resolve_cache_path(config, args.cache_path)
    service = AIKeywordClassifier(cache_path, config=config, app_profile=app_profile, market=market)

    reason_by_keyword = {
        _keyword_value(entry): str((entry or {}).get("reason", "") or "").strip()
        for entry in batch_payload.get("keywords", [])
        if isinstance(entry, dict)
    }

    source = getattr(args, "source", "") or os.environ.get("AGENTIC_SUBAGENT_SOURCE", "antigravity_subagent")

    saved_count = 0
    gloss_updated = 0
    for item in items:
        keyword = str(item["keyword"])
        # Gloss-only misses were already classified; only fill the gloss so we
        # never clobber a good semantic_bucket/confidence with a fresh guess.
        if reason_by_keyword.get(keyword) == "missing_english_gloss":
            gloss = str(item.get("english_gloss", "") or "").strip()
            if gloss and service._update_english_gloss(keyword, gloss):
                gloss_updated += 1
                continue
            # No existing row to patch (unexpected) -> fall back to a full store.
        analysis = AIKeywordAnalysis(
            keyword=keyword,
            detected_language=str(item.get("detected_language", "unknown")).strip().lower(),
            language_group=str(item.get("language_group", "UNKNOWN")).strip().upper(),
            semantic_bucket=str(item.get("semantic_bucket", "")).strip(),
            decision_rule=str(item.get("decision_rule", "agentic_semantic_classification")),
            reason=str(item.get("reason", "Agentic semantic classification")),
            confidence=float(item.get("confidence", 0.0)),
            english_gloss=str(item.get("english_gloss", "")),
        )
        service._store_cached(analysis, {
            "batch": batch_payload,
            "item": item,
            "source": source,
        })
        saved_count += 1

    remaining_path = ""
    saved_keywords = {str(item["keyword"]).strip() for item in items}
    remaining_keywords = [
        entry for entry in batch_payload.get("keywords", [])
        if _keyword_value(entry) not in saved_keywords
    ]
    if partial and (remaining_keywords or errors):
        remaining_path = getattr(args, "remaining_output", "") or _remaining_path_for_batch(args.batch)
        _write_json(remaining_path, {
            "app_id": batch_payload.get("app_id", ""),
            "app_name": batch_payload.get("app_name", ""),
            "market": market,
            "context_hash": batch_payload.get("context_hash", ""),
            "missing_count": len(remaining_keywords),
            "missing_keywords": remaining_keywords,
            "errors": errors,
        })

    return {
        "saved_count": saved_count,
        "gloss_updated": gloss_updated,
        "cache_path": cache_path,
        "errors": errors,
        "remaining_count": len(remaining_keywords),
        "remaining_path": remaining_path,
    }


def cmd_find_misses(args):
    if args.input_dir:
        payload = {}
        total_missing = 0
        for filename in sorted(os.listdir(args.input_dir)):
            if not filename.lower().endswith(".csv"):
                continue
            csv_path = os.path.join(args.input_dir, filename)
            market = extract_locale_from_filename(filename, "")
            market_payload = _scan_misses(args.app, csv_path, market, args.cache_path)
            payload[market_payload["market"]] = market_payload
            total_missing += market_payload["missing_count"]
        output_path = args.output or os.path.join(PROJECT_ROOT, ".cache", f"{args.app}_missing.json")
        _write_json(output_path, payload)
        print(f"Found {total_missing} missing keywords/gloss entries across {len(payload)} market(s).")
        print(f"Details saved to: {output_path}")
        return

    if not args.csv:
        raise SystemExit("find-misses requires either --csv or --input-dir")
    market = args.market or extract_locale_from_filename(args.csv, "")
    payload = _scan_misses(args.app, args.csv, market, args.cache_path)
    output_path = args.output
    if not output_path:
        clean_market = (payload["market"] or "default").replace("_", "-").lower()
        output_path = os.path.join(PROJECT_ROOT, ".cache", f"{args.app}_{clean_market}_missing.json")
    _write_json(output_path, payload)
    print(f"Found {payload['missing_count']} missing keywords/gloss entries.")
    print(f"Details saved to: {output_path}")


def cmd_prepare_batches(args):
    payload = _load_json(args.misses)
    output_dir = args.output_dir or DEFAULT_BATCH_DIR
    os.makedirs(output_dir, exist_ok=True)

    recipe = []
    chunk_size = max(1, int(args.chunk_size or DEFAULT_BATCH_SIZE))
    for missing_payload in _iter_missing_markets(payload):
        keywords = list(missing_payload.get("missing_keywords", []) or [])
        chunks = [keywords[index:index + chunk_size] for index in range(0, len(keywords), chunk_size)]
        total_batches = len(chunks)
        for batch_index, chunk in enumerate(chunks, 1):
            batch = _batch_payload(missing_payload, chunk, batch_index, total_batches)
            batch_path = os.path.join(output_dir, f"{batch['batch_id']}.json")
            _write_json(batch_path, batch)
            recipe.append({
                "market": batch["market"],
                "batch_id": batch["batch_id"],
                "batch_path": batch_path,
                "result_path": _result_path_for_batch(batch_path),
                "keywords_count": len(chunk),
            })

    print(f"Prepared {len(recipe)} batch file(s) in {output_dir}")
    print(json.dumps({"batches": recipe}, ensure_ascii=False, indent=2))


def cmd_save_results(args):
    outcome = _save_validated_results(args)
    total = outcome["saved_count"] + outcome["gloss_updated"]
    print(
        f"Successfully saved {total} keyword(s) to SQLite cache at: {outcome['cache_path']} "
        f"({outcome['saved_count']} classified, {outcome['gloss_updated']} gloss-only)"
    )
    if outcome["errors"]:
        print(f"Skipped {len(outcome['errors'])} invalid item(s):")
        for message in outcome["errors"]:
            print(f"  - {message}")
    if outcome["remaining_path"]:
        print(
            f"{outcome['remaining_count']} keyword(s) still missing. "
            f"Re-batch from: {outcome['remaining_path']}"
        )


def cmd_verify_cache(args):
    checks = []
    if args.input_dir:
        for filename in sorted(os.listdir(args.input_dir)):
            if not filename.lower().endswith(".csv"):
                continue
            csv_path = os.path.join(args.input_dir, filename)
            market = extract_locale_from_filename(filename, "")
            checks.append((csv_path, market))
    else:
        if not args.csv:
            raise SystemExit("verify-cache requires either --csv or --input-dir")
        checks.append((args.csv, args.market or extract_locale_from_filename(args.csv, "")))

    results = {}
    total_missing = 0
    for csv_path, market in checks:
        payload = _scan_misses(args.app, csv_path, market, args.cache_path)
        results[payload["market"]] = {
            "csv": csv_path,
            "missing_count": payload["missing_count"],
            "context_hash": payload["context_hash"],
        }
        total_missing += payload["missing_count"]
        status = "PASS" if payload["missing_count"] == 0 else "FAIL"
        print(f"{status} {payload['market']}: {payload['missing_count']} missing")

    if args.output:
        _write_json(args.output, results)
    if total_missing:
        raise SystemExit(1)


def _build_parser():
    parser = argparse.ArgumentParser(description="ASO agentic keyword cache helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_find = subparsers.add_parser("find-misses", help="Find keywords missing from the agentic cache")
    p_find.add_argument("--app", required=True, help="App alias, e.g. Game_Emulator")
    p_find.add_argument("--csv", default="", help="Input CSV path")
    p_find.add_argument("--input-dir", default="", help="Directory of CSV files to scan")
    p_find.add_argument("--market", default="", help="Optional market override")
    p_find.add_argument("--cache-path", default="", help="Optional SQLite cache override")
    p_find.add_argument("--output", default="", help="Optional JSON output path")

    p_prepare = subparsers.add_parser("prepare-batches", help="Create subagent batch JSON files from misses")
    p_prepare.add_argument("--misses", required=True, help="Misses JSON from find-misses")
    p_prepare.add_argument("--output-dir", default=DEFAULT_BATCH_DIR, help="Directory for batch JSON files")
    p_prepare.add_argument("--chunk-size", type=int, default=DEFAULT_BATCH_SIZE, help="Keywords per batch")

    p_save = subparsers.add_parser("save-results", help="Validate and save subagent results to SQLite cache")
    p_save.add_argument("--app", required=True, help="App alias, e.g. Game_Emulator")
    p_save.add_argument("--batch", required=True, help="Batch JSON file used by the subagent")
    p_save.add_argument("--results", required=True, help="Subagent result JSON file")
    p_save.add_argument("--market", default="", help="Optional market override")
    p_save.add_argument("--cache-path", default="", help="Optional SQLite cache override")
    p_save.add_argument(
        "--partial",
        action="store_true",
        help="Save valid items instead of aborting on the first bad one; "
             "write the still-missing keywords to a remaining JSON for re-spawning",
    )
    p_save.add_argument(
        "--remaining-output",
        default="",
        help="Where to write the still-missing keywords when --partial is set "
             "(defaults to <batch>_remaining.json)",
    )
    p_save.add_argument(
        "--source",
        default="",
        help="Source label stored with each cache row "
             "(defaults to $AGENTIC_SUBAGENT_SOURCE or antigravity_subagent)",
    )

    p_verify = subparsers.add_parser("verify-cache", help="Verify cache coverage before running the pipeline")
    p_verify.add_argument("--app", required=True, help="App alias, e.g. Game_Emulator")
    p_verify.add_argument("--csv", default="", help="Single CSV path to verify")
    p_verify.add_argument("--input-dir", default="", help="Directory of CSV files to verify")
    p_verify.add_argument("--market", default="", help="Optional market override for --csv")
    p_verify.add_argument("--cache-path", default="", help="Optional SQLite cache override")
    p_verify.add_argument("--output", default="", help="Optional JSON report path")

    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    commands = {
        "find-misses": cmd_find_misses,
        "prepare-batches": cmd_prepare_batches,
        "save-results": cmd_save_results,
        "verify-cache": cmd_verify_cache,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
