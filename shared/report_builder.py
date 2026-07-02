"""Shared output-verbosity policy for the ASO workbook.

Runners build every sheet as before, then call ``apply_output_mode(wb, config)``
right before saving. In the default ``lean`` mode this trims the audit/derived
sheets that are just filtered or re-sorted views of ``06_All_Candidates`` (which
already carries every keyword with Bucket / LanguageGroup / all scores), leaving
only the sheets a human actually acts on. In ``full`` mode nothing is removed.

Policy lives here so it is identical across every app; each app can still
override it via its own ``app_config.py`` (see ``resolve_output_mode`` /
``_overrides``) when a feature genuinely needs a different sheet set.
"""

# Audit / derived sheets removed in lean mode. Their content is reachable by
# filtering or sorting 06_All_Candidates, so they are noise for day-to-day use.
# Titles are stable across all app runners (template-derived numbering).
FULL_ONLY_SHEETS = {
    "04_Dropped_Audit",
    "07_Language_Mismatch",
    "08_Generic_Style_Reserve",
    "09_Manual_Review",
    "10_Top_By_Score",
    "11_Secondary_Language",
    "12_Text_Dedup_Log",
    "13_Top_By_Volume",
    "14_Not_Selected_Audit",
    "15_Selector_Quality_Log",
}

DEFAULT_MODE = "lean"
VALID_MODES = {"lean", "full"}


def _overrides(config):
    return (config or {}).get("report_output", {}) or {}


def resolve_output_mode(config):
    """Return the effective output mode ('lean' or 'full').

    Precedence: config['output_mode'] -> config['report_output']['mode'] ->
    DEFAULT_MODE. Unknown values fall back to the default.
    """
    config = config or {}
    mode = config.get("output_mode") or _overrides(config).get("mode") or DEFAULT_MODE
    mode = str(mode).strip().lower()
    return mode if mode in VALID_MODES else DEFAULT_MODE


def sheets_to_remove(titles, config):
    """Given the workbook's current sheet titles, return the set to remove.

    lean  -> FULL_ONLY_SHEETS, minus per-app keep_extra, plus per-app drop_extra.
    full  -> nothing (unless the app explicitly lists drop_extra).
    """
    mode = resolve_output_mode(config)
    overrides = _overrides(config)
    keep_extra = {str(t) for t in overrides.get("keep_extra", []) or []}
    drop_extra = {str(t) for t in overrides.get("drop_extra", []) or []}

    if mode == "full":
        target = set()
    else:
        target = set(FULL_ONLY_SHEETS)
    target = (target - keep_extra) | drop_extra
    return {title for title in titles if title in target}


def apply_output_mode(wb, config):
    """Trim sheets from an openpyxl workbook according to the output mode.

    Returns the list of removed sheet titles. Never removes the final remaining
    sheet (openpyxl requires at least one), so a mis-configured override can't
    produce an empty workbook.
    """
    titles = [ws.title for ws in wb.worksheets]
    remove = sheets_to_remove(titles, config)
    removed = []
    for title in titles:
        if title not in remove:
            continue
        if len(wb.worksheets) <= 1:
            break
        wb.remove(wb[title])
        removed.append(title)
    return removed
