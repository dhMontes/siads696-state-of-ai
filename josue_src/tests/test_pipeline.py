"""Data-integrity tests for conservative intake; run with unittest discovery.
"""

import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

PREPARATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PREPARATION))
import pipeline


class TransformationIntegrityTests(unittest.TestCase):
    def test_normalization_preserves_case_negation_punctuation_and_numbers(self):
        source = "\tAI shall NOT allow $10.50; Section 12(a).\r\nCafe\u0301\u00a0law\t"
        result = pipeline.clean_text(source)
        self.assertEqual(result, "AI shall NOT allow $10.50; Section 12(a). Café law")
        self.assertNotEqual(result, pipeline.clean_text(source.lower()))
        self.assertNotEqual(pipeline.text_hash(source), pipeline.text_hash(result))
        self.assertEqual(result, pipeline.clean_text(result))
        self.assertEqual(pipeline.clean_text("① ﬀ １２"), "① ﬀ １２")

    def test_dates_do_not_guess_or_silently_repair_invalid_values(self):
        self.assertEqual(pipeline.parse_date("02/29/2024")["iso"], "2024-02-29")
        self.assertEqual(pipeline.parse_date("2025-01-03")["iso"], "2025-01-03")
        for invalid in ("02/29/2025", "13/01/2025", "2025-02-30", "01/02/25", "March 1, 2025"):
            with self.subTest(value=invalid):
                self.assertTrue(pipeline.parse_date(invalid)["parse_error"])
                self.assertEqual(pipeline.parse_date(invalid)["iso"], "")
        blank = pipeline.parse_date(" \n")
        self.assertTrue(blank["missing"])
        self.assertFalse(blank["parse_error"])

    def test_json_arrays_keep_missingness_and_reject_wrong_structures(self):
        parsed = pipeline.parse_string_array('["D", "", null, "DFL"]')
        self.assertEqual(parsed["values"], ["D", "", None, "DFL"])
        self.assertEqual(parsed["missing_items"], 2)
        for source, state in (("['D']", "malformed_json"), ('{"party":"D"}', "not_array"),
                              ('"D"', "not_array"), ('["D", 7]', "invalid_item_type"),
                              ("null", "not_array"), ("", "missing")):
            with self.subTest(value=source):
                self.assertEqual(pipeline.parse_string_array(source)["state"], state)
                self.assertIsNone(pipeline.parse_string_array(source)["values"])

    def test_row_locator_ties_identity_to_source_record_and_checksum(self):
        self.assertNotEqual(pipeline.row_locator("abc", 2), pipeline.row_locator("abc", 3))
        self.assertNotEqual(pipeline.row_locator("abc", 2), pipeline.row_locator("def", 2))


class EndToEndIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="integrity-fixture-", dir=PREPARATION / "tests")
        self.root = Path(self.temp.name)
        self.source = self.root / "source.csv"
        base = {name: "" for name in pipeline.INPUT_COLUMNS}
        base.update({"Bill_Number": " H 12 ", "Jurisdiction": "Example State", "Year": "2025",
                     "Bill_Title": "Do NOT Replace This Title", "Bill_Text": "AI shall NOT authorize $5.\nSection 12.",
                     "Introduction_Date": "12/30/2024", "Version_Date": "02/01/2025",
                     "Bill_Status": "Pending - Carryover", "Bill_Status_Grouped": "Pending",
                     "Sponsor": '["A", "B"]', "Sponsor_Party": '["D", ""]',
                     "status": "filtered_not_ai", "summary": "generated content",
                     "NCSL_Category": "generated category", "ai_advancement_score": "1.0"})
        changed = dict(base)
        changed.update({"Bill_Number": "H 13", "Bill_Text": "AI shall NOT authorize $5.  Section 12.",
                        "Bill_Status": "Enacted", "Bill_Status_Grouped": "Passed",
                        "Introduction_Date": "02/30/2025", "Sponsor": '["A"]', "Sponsor_Party": '["D", "R"]'})
        malformed = dict(base)
        malformed.update({"Bill_Number": "H 14", "Bill_Text": " \n", "Sponsor": "['A']",
                          "Sponsor_Party": '["D", 1]', "Version_Date": "", "Year": "invalid"})
        self.rows = [base, changed, dict(base), malformed]
        with self.source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=pipeline.INPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)
        self.original_bytes = self.source.read_bytes()
        self.summary = pipeline.run_pipeline(self.source, self.root / "output", expected_sha256=None, expected_rows=None)

    def tearDown(self):
        self.temp.cleanup()

    def read_table(self, filename):
        with (self.root / "output" / filename).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_no_rows_lost_and_multiline_raw_cells_roundtrip_unchanged(self):
        self.assertEqual(self.source.read_bytes(), self.original_bytes)
        raw = self.read_table("raw_evidence.csv")
        self.assertEqual(len(raw), 4)
        for exported, original in zip(raw, self.rows):
            self.assertEqual({name: exported[name] for name in pipeline.INPUT_COLUMNS}, original)
        self.assertEqual([row["logical_csv_row"] for row in raw], ["2", "3", "4", "5"])
        for filename in self.summary["output_artifacts"]:
            if filename.endswith(".csv"):
                self.assertEqual([row["row_locator"] for row in self.read_table(filename)], [row["row_locator"] for row in raw])

    def test_pending_remains_evidence_and_publisher_flag_does_not_filter(self):
        predictors = self.read_table("candidate_predictors.csv")
        self.assertEqual(set(predictors[0]), {"row_locator", "bill_text_normalized", "bill_title_normalized"})
        self.assertEqual(len(predictors), len(self.rows))
        evidence = self.read_table("quality_flags.csv")
        self.assertEqual(evidence[0]["source_status_prefix"], "Pending")
        self.assertEqual(self.summary["publisher_classification_status_counts_evidence_only"], {"filtered_not_ai": 4})
        self.assertFalse(self.summary["checks"]["target_labels_encoded"])
        self.assertFalse(self.summary["checks"]["splits_created"])
        self.assertFalse(any(name.lower() in {"target", "label", "failure", "split"} for name in evidence[0]))

    def test_dates_alignment_identity_and_party_semantics_fail_closed(self):
        flags = self.read_table("quality_flags.csv")
        self.assertEqual(flags[0]["source_year_differs_introduction_year"], "True")
        self.assertEqual(flags[1]["introduction_date_parse_error"], "True")
        self.assertEqual(flags[1]["version_after_introduction"], "")
        self.assertEqual(flags[1]["sponsor_party_length_mismatch"], "True")
        self.assertEqual(flags[3]["sponsor_party_alignment_unavailable"], "True")
        self.assertEqual(flags[3]["observed_party_code_D_present"], "")
        self.assertEqual(flags[0]["party_missing_items"], "1")
        self.assertTrue(all(row["party_semantics_verified"] == "False" for row in flags))
        identities = self.read_table("bill_identity_crosswalk.csv")
        self.assertTrue(all(row["verified_state_session_bill_key"] == "" for row in identities))
        self.assertTrue(all(row["candidate_key_is_verified_session_key"] == "False" for row in identities))

    def test_exact_duplicates_are_flagged_and_retained(self):
        flags = self.read_table("quality_flags.csv")
        self.assertEqual(self.summary["duplicates"]["exact_raw_row"]["rows_in_groups"], 2)
        self.assertEqual(self.summary["duplicates"]["exact_normalized_text"]["rows_in_groups"], 3)
        self.assertEqual(len(flags), 4)
        self.assertNotEqual(flags[0]["row_locator"], flags[2]["row_locator"])
        self.assertEqual(flags[0]["exact_raw_row_group_id"], flags[2]["exact_raw_row_group_id"])
        self.assertEqual(flags[0]["exact_normalized_text_group_id"], flags[1]["exact_normalized_text_group_id"])

    def test_deterministic_csv_reproduction_and_exhaustive_column_contract(self):
        other = pipeline.run_pipeline(self.source, self.root / "independent_output", expected_sha256=None, expected_rows=None)
        for filename, artifact in self.summary["output_artifacts"].items():
            self.assertEqual(artifact["sha256"], other["output_artifacts"][filename]["sha256"])
        contract = json.loads((self.root / "output/column_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(set(contract["input_columns"]), set(pipeline.INPUT_COLUMNS))
        for filename, entries in contract["output_columns"].items():
            self.assertEqual(set(entries), set(self.read_table(filename)[0]))
            self.assertTrue(all(entry["role"] in contract["roles"] for entry in entries.values()))
            self.assertTrue(all(entry["use_in_model_now"] is False for entry in entries.values()))

    def test_wrong_source_checksum_or_schema_stops_before_output(self):
        with self.assertRaisesRegex(ValueError, "checksum"):
            pipeline.run_pipeline(self.source, self.root / "rejected", expected_sha256="wrong", expected_rows=None)
        self.assertFalse((self.root / "rejected").exists())
        malformed = self.root / "wrong_schema.csv"
        malformed.write_text("Bill_Number\nH 12\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "schema"):
            pipeline.run_pipeline(malformed, self.root / "rejected", expected_sha256=None, expected_rows=None)
        self.assertFalse((self.root / "rejected").exists())


if __name__ == "__main__":
    unittest.main()
