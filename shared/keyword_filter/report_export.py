from .shortlist import QUALITY_LOG_COLUMNS


def write_quality_log_sheet(workbook, shortlist_result, style_sheet_fn=None, sheet_name="15_Selector_Quality_Log"):
    """Write MainKeywordShortlistBuilder's quality_log to its own sheet.

    quality_log carries selector-level warnings (e.g. SAFE_POOL_EXHAUSTED, raised
    when target_count couldn't be filled without using blocked/over-crowded
    keywords) that otherwise only exist in memory -- previously invisible to
    anyone reading the exported workbook. diversity_log (CLUSTER_CAP_REACHED
    events) is intentionally not duplicated here: those already appear in the
    Not Selected Audit sheet via NotSelectedReason.

    style_sheet_fn, if given, is the app's own worksheet styling function
    (header fill/font, column auto-fit, etc.) -- each app defines its own
    rather than sharing one, so it's injected instead of imported.
    """
    ws = workbook.create_sheet(title=sheet_name)
    quality_log = getattr(shortlist_result, "quality_log", None) or []
    for col_idx, col in enumerate(QUALITY_LOG_COLUMNS, 1):
        ws.cell(row=1, column=col_idx, value=col)
    for row_idx, entry in enumerate(quality_log, 2):
        for col_idx, col in enumerate(QUALITY_LOG_COLUMNS, 1):
            ws.cell(row=row_idx, column=col_idx, value=entry.get(col, ""))
    if style_sheet_fn:
        style_sheet_fn(ws, sheet_name)
    return ws
