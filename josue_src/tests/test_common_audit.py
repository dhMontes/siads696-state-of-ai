"""Common-intake audit integrity tests; no model/missingness policy assertions.
"""

import csv
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest

PREPARATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PREPARATION))
import audit_common_inputs as audit
import pipeline


class CategoryAndPartitionTests(unittest.TestCase):
    def test_raw_blank_categories_and_exact_markers_stay_distinct(self):
        self.assertEqual(audit.blank_kind(""), "empty_string")
        self.assertEqual(audit.blank_kind(" \t\n\u00a0"), "whitespace_only")
        for token in audit.EXACT_SENTINELS:
            with self.subTest(token=token):
                self.assertEqual(audit.cell_category(token), "exact_literal:" + token)
                self.assertTrue(audit.raw_available(token))
                self.assertEqual(audit.cell_category(" " + token + " "), "other_nonblank")
        self.assertEqual(audit.cell_category("NAN"), "other_nonblank")
        self.assertEqual(audit.cell_category("substantive text"), "other_nonblank")
        self.assertFalse(audit.raw_available(""))
        self.assertFalse(audit.raw_available("\n\t"))

    def test_overlap_partitions_all_eight_patterns_and_keeps_marker_nonblank(self):
        rows = [dict(zip(audit.OVERLAP_COLUMNS, ["None" if available else " \t"
                                              for available in pattern]))
                for pattern in itertools.product((False, True), repeat=3)]
        result = audit.overlap_counts(rows)
        self.assertEqual(len(result), 8)
        self.assertEqual(sum(item["rows"] for item in result), len(rows))
        self.assertTrue(all(item["rows"] == 1 for item in result))
        self.assertEqual(result[-1]["availability"], {name: True for name in audit.OVERLAP_COLUMNS})
        empty = audit.overlap_counts([])
        self.assertEqual(len(empty), 8)
        self.assertTrue(all(item["rows"] == 0 for item in empty))

    def test_examples_use_logical_source_order_not_lexicographic_locator_order(self):
        reason = audit.REVIEW_FLAGS[0]
        rows = [{"review_reason": reason, "logical_csv_row": index,
                 "row_locator": pipeline.row_locator("abc", index)}
                for index in (12, 3, 2, 11, 9)]
        examples = audit.select_examples(rows, per_reason=3)
        self.assertEqual([row["logical_csv_row"] for row in examples[reason]], [2, 3, 9])
        self.assertEqual(examples, audit.select_examples(list(reversed(rows)), per_reason=3))
        self.assertTrue(all(examples[name] == [] for name in audit.REVIEW_FLAGS[1:]))
        with self.assertRaises(ValueError):
            audit.select_examples(rows, per_reason=0)


class AuditEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="common-audit-fixture-", dir=PREPARATION / "tests")
        self.root = Path(self.temp.name)
        self.source = self.root / "source.csv"
        self.output = self.root / "output"
        self.rows = []
        for index, pattern in enumerate(itertools.product((False, True), repeat=3)):
            row = {name: "" for name in pipeline.INPUT_COLUMNS}
            row.update({"Bill_Number": "H 1" if index < 3 else "H " + str(index + 1),
                        "Jurisdiction": "Example State", "Year": "2024" if index == 0 else "2025",
                        "Bill_Title": "" if index == 1 else "Title",
                        "Bill_Text": "Rule shall NOT apply.\nSection 1." if index < 2 else "Independent rule " + str(index),
                        "Introduction_Date": "02/01/2025", "Version_Date": "01/01/2025" if index == 0 else "03/01/2025",
                        "Sponsor": "[]", "Sponsor_Party": "[]", "measure_code": "HB",
                        "status": "filtered_not_ai" if index == 0 else " processed "})
            row.update(dict(zip(audit.OVERLAP_COLUMNS, ["None" if available else (" \t" if index % 2 else "")
                                                       for available in pattern])))
            self.rows.append(row)
        with self.source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=pipeline.INPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)
        self.original_bytes = self.source.read_bytes()
        self.checksum = pipeline.sha256_bytes(self.original_bytes)
        pipeline.run_pipeline(self.source, self.output, expected_sha256=self.checksum, expected_rows=len(self.rows))

    def tearDown(self):
        self.temp.cleanup()

    def run_fixture(self):
        return audit.run_audit(self.source, self.output,
                               expected_sha256=self.checksum, expected_rows=len(self.rows))

    def test_full_row_coverage_categories_segments_and_original_source_preserved(self):
        summary = self.run_fixture()
        self.assertEqual(self.source.read_bytes(), self.original_bytes)
        self.assertEqual(summary["source"]["sha256_before"], self.checksum)
        self.assertEqual(summary["source"]["sha256_after"], self.checksum)
        coverage = audit.read_table(self.output / "text_coverage.csv")
        locators = [pipeline.row_locator(self.checksum, record) for record in range(2, 10)]
        self.assertEqual([row["row_locator"] for row in coverage], locators)
        self.assertEqual(len(set(locators)), len(self.rows))
        for raw, exported in zip(self.rows, coverage):
            for name, prefix in audit.PREFIXES.items():
                self.assertEqual(exported[prefix + "_blank_kind"], audit.blank_kind(raw[name]))
                self.assertEqual(exported[prefix + "_raw_available"], str(audit.raw_available(raw[name])))
        missing = audit.read_table(self.output / "column_missingness.csv")
        self.assertEqual({row["source_column"] for row in missing}, set(pipeline.INPUT_COLUMNS))
        for name in pipeline.INPUT_COLUMNS:
            self.assertEqual(sum(int(row["rows"]) for row in missing if row["source_column"] == name), len(self.rows))
        self.assertTrue(all(item["rows"] == 1 for item in summary["summary_extract_overlap"]))
        self.assertEqual(sum(group["rows"] for group in summary["coverage_by_source_year"]), len(self.rows))
        self.assertEqual(sum(group["rows"] for group in summary["coverage_by_source_jurisdiction"]), len(self.rows))
        statuses = {group["source_value_raw"]: group for group in summary["coverage_by_publisher_status"]}
        self.assertEqual(set(statuses), {"filtered_not_ai", " processed "})
        self.assertEqual(statuses["filtered_not_ai"]["rows"], 1)
        self.assertEqual(statuses["filtered_not_ai"]["summary_extract_overlap"][0]["rows"], 1)
        self.assertEqual(statuses[" processed "]["rows"], 7)
        self.assertEqual(summary["nonzero_literal_marker_counts"]["Sponsor"], {"[]": len(self.rows)})
        self.assertTrue(summary["checks"]["all_output_csv_values_roundtrip_verified"])
        self.assertFalse(summary["checks"]["model_subsets_exported"])

    def test_review_is_row_linked_repeated_reasons_are_not_distinct_bills(self):
        summary = self.run_fixture()
        review = audit.read_table(self.output / "review_records.csv")
        allowed = {pipeline.row_locator(self.checksum, record) for record in range(2, 10)}
        self.assertTrue(all(row["row_locator"] in allowed for row in review))
        self.assertEqual(summary["review_queue"]["reason_counts"]["version_before_introduction"], 1)
        self.assertEqual(summary["review_queue"]["reason_counts"]["version_after_introduction"], 7)
        self.assertEqual(summary["review_queue"]["reason_counts"]["bill_title_missing"], 1)
        self.assertEqual(summary["review_queue"]["reason_counts"]["exact_normalized_text_duplicate_flag"], 2)
        self.assertEqual(len(review), 11)
        self.assertEqual(summary["review_queue"]["distinct_source_records"], 8)
        self.assertTrue(all(row["review_status"] == "unreviewed_retained" for row in review))
        repeated = summary["repeated_state_bill_across_supplied_years"]
        self.assertEqual(repeated["groups_spanning_multiple_supplied_years"], 1)
        self.assertEqual(repeated["rows_in_these_groups"], 3)
        self.assertEqual(repeated["groups"][0]["supplied_year_labels"], ["2024", "2025"])
        self.assertEqual(len(repeated["groups"][0]["row_locators"]), 3)
        self.assertEqual(summary["review_queue"]["rows_dropped_or_merged"], 0)

    def test_audit_csv_hashes_and_selection_are_reproducible(self):
        first = self.run_fixture()
        second = self.run_fixture()
        self.assertEqual(first["output_artifacts"], second["output_artifacts"])
        self.assertEqual(first["review_queue"], second["review_queue"])
        for filename, artifact in first["output_artifacts"].items():
            self.assertEqual(pipeline.sha256_bytes((self.output / filename).read_bytes()), artifact["sha256"])
        saved = json.loads((self.output / "common_input_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, second)
        self.assertEqual(self.source.read_bytes(), self.original_bytes)

    def test_hash_refusal_does_not_create_audit_outputs_or_mutate_source(self):
        with self.assertRaisesRegex(ValueError, "Source checksum"):
            audit.run_audit(self.source, self.output, expected_sha256="incorrect", expected_rows=len(self.rows))
        self.assertFalse((self.output / "text_coverage.csv").exists())
        self.assertFalse((self.output / "common_input_audit.json").exists())
        self.assertEqual(self.source.read_bytes(), self.original_bytes)

    def test_modified_intake_evidence_is_rejected_before_audit_output(self):
        target = self.output / "quality_flags.csv"
        target.write_bytes(target.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Intake evidence checksum mismatch"):
            self.run_fixture()
        self.assertFalse((self.output / "text_coverage.csv").exists())
        self.assertEqual(self.source.read_bytes(), self.original_bytes)


if __name__ == "__main__":
    unittest.main()
