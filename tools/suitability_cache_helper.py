import argparse
import json
import os
import sys

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.app_registry import registered_aliases
from shared.effective_config import resolve_effective_app
from shared.keyword_filter import suitability
from shared.locale_parser import extract_locale_from_filename


DEFAULT_BATCH_SIZE = 200
DEFAULT_BATCH_DIR = os.path.join(PROJECT_ROOT, ".cache", "suitability_batches")


def _read_candidates(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    if "Keyword" not in frame.columns:
        raise ValueError("Candidate CSV must contain a Keyword column")
    return frame


def _write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2)


def _load_json(path):
    with open(path, "r", encoding="utf-8") as input_file:
        return json.load(input_file)


def _resolve_app_context(app_alias, market):
    try:
        return resolve_effective_app(app_alias, PROJECT_ROOT, market)
    except KeyError as exc:
        aliases = ", ".join(registered_aliases())
        raise SystemExit(f"{exc}\nKnown aliases: {aliases}") from exc


def _resolve_cache_path(config, explicit_cache_path=""):
    cache_path = explicit_cache_path or suitability.suitability_policy(config).get("cache_path") or ".cache/agentic_keyword_analysis.sqlite3"
    if not os.path.isabs(cache_path):
        cache_path = os.path.join(PROJECT_ROOT, cache_path)
    return cache_path


def _keyword_value(item):
    if isinstance(item, dict):
        return str(item.get("keyword", "") or "").strip()
    return str(item or "").strip()


def _scan_misses(app_alias, candidates_path, market, cache_path=""):
    _, _, config, app_profile = _resolve_app_context(app_alias, market)
    market = market or config.get("market", "") or extract_locale_from_filename(candidates_path, "")
    if market:
        config["market"] = market
    frame = _read_candidates(candidates_path)
    service = suitability.SuitabilityCache(
        _resolve_cache_path(config, cache_path),
        config=config,
        app_profile=app_profile,
        market=market,
    )

    missing = []
    for row in frame.to_dict("records"):
        keyword = str(row.get("Keyword", "") or "").strip()
        if not keyword or not suitability.needs_suitability_audit(row, config):
            continue
        if service.get(keyword) is not None:
            continue
        missing.append({
            "keyword": keyword,
            "volume": int(float(row.get("Volume", 0) or 0)),
            "bucket": str(row.get("Bucket", "") or ""),
            "decision_rule": str(row.get("DecisionRule", "") or row.get("AIDecisionRule", "") or ""),
            "reason": "missing_suitability_cache",
        })

    return {
        "app_id": config.get("app_id", ""),
        "app_name": config.get("app_name", ""),
        "market": market,
        "context_hash": suitability._context_hash(config, app_profile),
        "missing_count": len(missing),
        "missing_keywords": missing,
    }


def _iter_missing_markets(payload):
    if "missing_keywords" in payload:
        yield payload
        return
    for market, market_payload in payload.items():
        if isinstance(market_payload, dict):
            item = dict(market_payload)
            item.setdefault("market", market)
            yield item


def _batch_payload(missing_payload, chunk, batch_index, total_batches):
    market = str(missing_payload.get("market", "") or "")
    batch_id = f"{market.lower()}_suitability_batch_{batch_index}"
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


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raw = str(value or "").strip().lower()
    if raw in {"true", "yes", "1"}:
        return True
    if raw in {"false", "no", "0"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def _validate_result_items(result_payload, batch_payload):
    items = result_payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Result JSON must contain an items[] list")
    if result_payload.get("batch_id") and result_payload["batch_id"] != batch_payload.get("batch_id"):
        raise ValueError("Result batch_id does not match batch input")

    expected = {_keyword_value(item) for item in batch_payload.get("keywords", [])}
    expected.discard("")
    seen = set()
    validated = []
    errors = []

    for item in items:
        if not isinstance(item, dict):
            errors.append("Every result item must be an object")
            continue
        keyword = str(item.get("keyword", "") or "").strip()
        if keyword not in expected:
            errors.append(f"Result keyword is not part of the batch: {keyword!r}")
            continue
        if keyword in seen:
            errors.append(f"Duplicate result keyword: {keyword!r}")
            continue
        seen.add(keyword)
        item_errors = []
        try:
            metadata_eligible = _as_bool(item.get("metadata_eligible"))
            ads_eligible = _as_bool(item.get("ads_eligible"))
            research_only = _as_bool(item.get("research_only"))
        except ValueError as exc:
            item_errors.append(f"{exc} for {keyword!r}")
            metadata_eligible = ads_eligible = False
            research_only = True
        for field in ("suitability_bucket", "decision_rule", "reason"):
            if not str(item.get(field, "") or "").strip():
                item_errors.append(f"Missing {field} for {keyword!r}")
        try:
            confidence = float(item.get("confidence", ""))
            if not 0.0 <= confidence <= 1.0:
                item_errors.append(f"Confidence must be between 0 and 1 for {keyword!r}")
        except (TypeError, ValueError):
            item_errors.append(f"Invalid confidence for {keyword!r}")
            confidence = 0.0
        if metadata_eligible and research_only:
            item_errors.append(f"metadata_eligible and research_only conflict for {keyword!r}")
        if item_errors:
            errors.extend(item_errors)
            continue
        normalized = dict(item)
        normalized["metadata_eligible"] = metadata_eligible
        normalized["ads_eligible"] = ads_eligible
        normalized["research_only"] = research_only
        normalized["confidence"] = confidence
        validated.append(normalized)

    missing = expected - {item["keyword"] for item in validated}
    if missing:
        sample = ", ".join(sorted(missing)[:5])
        errors.append(f"Result JSON is missing {len(missing)} batch keyword(s): {sample}")
    if errors:
        raise ValueError("; ".join(errors))
    return validated


def cmd_find_misses(args):
    if args.input_dir:
        payload = {}
        total = 0
        for filename in sorted(os.listdir(args.input_dir)):
            if not filename.lower().endswith(".csv"):
                continue
            path = os.path.join(args.input_dir, filename)
            market = extract_locale_from_filename(filename, "")
            item = _scan_misses(args.app, path, market, args.cache_path)
            payload[item["market"]] = item
            total += item["missing_count"]
        output = args.output or os.path.join(PROJECT_ROOT, ".cache", f"{args.app}_suitability_missing.json")
        _write_json(output, payload)
        print(f"Found {total} missing suitability entries across {len(payload)} market(s).")
        print(f"Details saved to: {output}")
        return
    if not args.csv:
        raise SystemExit("find-misses requires either --csv or --input-dir")
    market = args.market or extract_locale_from_filename(args.csv, "")
    payload = _scan_misses(args.app, args.csv, market, args.cache_path)
    output = args.output or os.path.join(PROJECT_ROOT, ".cache", f"{args.app}_{(payload['market'] or 'default').lower()}_suitability_missing.json")
    _write_json(output, payload)
    print(f"Found {payload['missing_count']} missing suitability entries.")
    print(f"Details saved to: {output}")


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
    print(f"Prepared {len(recipe)} suitability batch file(s) in {output_dir}")
    print(json.dumps({"batches": recipe}, ensure_ascii=False, indent=2))


def cmd_save_results(args):
    batch = _load_json(args.batch)
    result = _load_json(args.results)
    market = args.market or batch.get("market", "")
    _, _, config, app_profile = _resolve_app_context(args.app, market)
    config["market"] = market
    expected_hash = suitability._context_hash(config, app_profile)
    if batch.get("context_hash") != expected_hash:
        raise ValueError("Batch context_hash does not match current app config. Regenerate suitability misses and batches.")
    items = _validate_result_items(result, batch)
    cache = suitability.SuitabilityCache(
        _resolve_cache_path(config, args.cache_path),
        config=config,
        app_profile=app_profile,
        market=market,
    )
    source = args.source or os.environ.get("SUITABILITY_SUBAGENT_SOURCE", "antigravity_subagent")
    for item in items:
        cache.store(
            suitability.SuitabilityAnalysis(
                keyword=str(item["keyword"]),
                metadata_eligible=bool(item["metadata_eligible"]),
                ads_eligible=bool(item["ads_eligible"]),
                research_only=bool(item["research_only"]),
                suitability_bucket=str(item["suitability_bucket"]).strip(),
                decision_rule=str(item["decision_rule"]).strip(),
                reason=str(item["reason"]).strip(),
                confidence=float(item["confidence"]),
                source=source,
            ),
            {"batch": batch, "item": item, "source": source},
        )
    print(f"Successfully saved {len(items)} suitability item(s) to SQLite cache.")


def cmd_verify_cache(args):
    checks = []
    if args.input_dir:
        for filename in sorted(os.listdir(args.input_dir)):
            if filename.lower().endswith(".csv"):
                checks.append((os.path.join(args.input_dir, filename), extract_locale_from_filename(filename, "")))
    else:
        if not args.csv:
            raise SystemExit("verify-cache requires either --csv or --input-dir")
        checks.append((args.csv, args.market or extract_locale_from_filename(args.csv, "")))

    results = {}
    total_missing = 0
    for path, market in checks:
        payload = _scan_misses(args.app, path, market, args.cache_path)
        results[payload["market"]] = {
            "csv": path,
            "missing_count": payload["missing_count"],
            "context_hash": payload["context_hash"],
        }
        total_missing += payload["missing_count"]
        status = "PASS" if payload["missing_count"] == 0 else "FAIL"
        print(f"{status} {payload['market']}: {payload['missing_count']} missing suitability")
    if args.output:
        _write_json(args.output, results)
    if total_missing:
        raise SystemExit(1)


def _build_parser():
    parser = argparse.ArgumentParser(description="ASO metadata/ads suitability cache helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_find = subparsers.add_parser("find-misses", help="Find candidates missing suitability audit")
    p_find.add_argument("--app", required=True)
    p_find.add_argument("--csv", default="", help="Candidate CSV with Keyword/Bucket columns")
    p_find.add_argument("--input-dir", default="", help="Directory of candidate CSV files")
    p_find.add_argument("--market", default="")
    p_find.add_argument("--cache-path", default="")
    p_find.add_argument("--output", default="")

    p_prepare = subparsers.add_parser("prepare-batches", help="Create suitability subagent batch JSON files")
    p_prepare.add_argument("--misses", required=True)
    p_prepare.add_argument("--output-dir", default=DEFAULT_BATCH_DIR)
    p_prepare.add_argument("--chunk-size", type=int, default=DEFAULT_BATCH_SIZE)

    p_save = subparsers.add_parser("save-results", help="Validate and save suitability subagent results")
    p_save.add_argument("--app", required=True)
    p_save.add_argument("--batch", required=True)
    p_save.add_argument("--results", required=True)
    p_save.add_argument("--market", default="")
    p_save.add_argument("--cache-path", default="")
    p_save.add_argument("--source", default="")

    p_verify = subparsers.add_parser("verify-cache", help="Verify suitability cache coverage")
    p_verify.add_argument("--app", required=True)
    p_verify.add_argument("--csv", default="")
    p_verify.add_argument("--input-dir", default="")
    p_verify.add_argument("--market", default="")
    p_verify.add_argument("--cache-path", default="")
    p_verify.add_argument("--output", default="")

    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    {
        "find-misses": cmd_find_misses,
        "prepare-batches": cmd_prepare_batches,
        "save-results": cmd_save_results,
        "verify-cache": cmd_verify_cache,
    }[args.command](args)


if __name__ == "__main__":
    main()
