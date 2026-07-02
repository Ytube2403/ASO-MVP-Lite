import os
import sys
import unittest

from openpyxl import Workbook

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared import report_builder


ALL_SHEETS = [
    "00_Project_Memory",
    "00_README_CONFIG",
    "01_Main_Keyword_Shortlist",
    "02_Feature_Keywords",
    "03_Style_Keywords",
    "04_Dropped_Audit",
    "05_Report_Summary",
    "06_All_Candidates",
    "07_Language_Mismatch",
    "08_Generic_Style_Reserve",
    "09_Manual_Review",
    "10_Top_By_Score",
    "11_Secondary_Language",
    "12_Text_Dedup_Log",
    "13_Top_By_Volume",
    "14_Not_Selected_Audit",
    "15_Selector_Quality_Log",
]


def _workbook(titles=ALL_SHEETS):
    wb = Workbook()
    wb.remove(wb.active)  # drop the default "Sheet"
    for title in titles:
        wb.create_sheet(title=title)
    return wb


class ReportBuilderTests(unittest.TestCase):
    def test_resolve_output_mode_precedence_and_fallback(self):
        self.assertEqual(report_builder.resolve_output_mode({}), "lean")
        self.assertEqual(report_builder.resolve_output_mode({"output_mode": "full"}), "full")
        self.assertEqual(
            report_builder.resolve_output_mode({"report_output": {"mode": "full"}}), "full"
        )
        # top-level output_mode wins over nested
        self.assertEqual(
            report_builder.resolve_output_mode(
                {"output_mode": "lean", "report_output": {"mode": "full"}}
            ),
            "lean",
        )
        # unknown value falls back to default
        self.assertEqual(report_builder.resolve_output_mode({"output_mode": "verbose"}), "lean")

    def test_lean_trims_audit_sheets_keeps_deliverables(self):
        wb = _workbook()
        removed = report_builder.apply_output_mode(wb, {"output_mode": "lean"})
        remaining = {ws.title for ws in wb.worksheets}
        self.assertEqual(set(removed), report_builder.FULL_ONLY_SHEETS)
        self.assertEqual(
            remaining,
            {
                "00_Project_Memory",
                "00_README_CONFIG",
                "01_Main_Keyword_Shortlist",
                "02_Feature_Keywords",
                "03_Style_Keywords",
                "05_Report_Summary",
                "06_All_Candidates",
            },
        )

    def test_full_keeps_everything(self):
        wb = _workbook()
        removed = report_builder.apply_output_mode(wb, {"output_mode": "full"})
        self.assertEqual(removed, [])
        self.assertEqual(len(wb.worksheets), len(ALL_SHEETS))

    def test_default_is_lean(self):
        wb = _workbook()
        report_builder.apply_output_mode(wb, {})
        self.assertNotIn("10_Top_By_Score", {ws.title for ws in wb.worksheets})

    def test_keep_extra_and_drop_extra_overrides(self):
        wb = _workbook()
        config = {
            "output_mode": "lean",
            "report_output": {
                "keep_extra": ["10_Top_By_Score"],
                "drop_extra": ["06_All_Candidates"],
            },
        }
        report_builder.apply_output_mode(wb, config)
        remaining = {ws.title for ws in wb.worksheets}
        self.assertIn("10_Top_By_Score", remaining)      # audit sheet force-kept
        self.assertNotIn("06_All_Candidates", remaining)  # deliverable force-dropped

    def test_never_removes_last_sheet(self):
        wb = _workbook(["04_Dropped_Audit"])  # only a full-only sheet exists
        removed = report_builder.apply_output_mode(wb, {"output_mode": "lean"})
        self.assertEqual(removed, [])
        self.assertEqual(len(wb.worksheets), 1)


if __name__ == "__main__":
    unittest.main()
