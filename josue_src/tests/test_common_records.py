"""End-to-end preservation and decision-boundary tests for the common handoff.
"""

import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PREPARATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PREPARATION))
import audit_common_inputs as audit
import common_records
import pipeline
import prepare
import validate_outputs


class CommonHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="common-fixture-", dir=PREPARATION / "tests")
        self.root = Path(self.temp.name)
        self.source, self.output = self.root / "source.csv", self.root / "output"
        first = {name: "original:" + name for name in pipeline.INPUT_COLUMNS}
        first.update({"Bill_Text": "AI shall NOT allow $5.\nSection 12.", "Bill_Title": " Text Title ",
                      "NCSL_Summary": " NCSL summary\ttext ", "summary": "Publisher summary",
                      "bill_extracts": "Publisher extract", "Introduction_Date": "02/01/2025",
                      "Version_Date": "01/31/2025", "Year": "2025", "Sponsor": '["A", null]',
                      "Sponsor_Party": '["D", null]', "Bill_Status": "Pending - Carryover",
                      "Bill_Status_Grouped": "Pending", "status": "filtered_not_ai"})
        second = dict(first)
        second.update({"Bill_Number": "H 2", "Bill_Text": "AI shall NOT allow $5.  Section 12.",
                       "summary": "", "bill_extracts": " \n", "Bill_Title": "", "Year": "null",
                       "Sponsor_Party": '["D", 1]', "Introduction_Date": "02/30/2025"})
        self.rows = [first, second, dict(first)]
        with self.source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=pipeline.INPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)
        self.original_bytes = self.source.read_bytes()
        self.receipt = prepare.prepare(self.source, self.output, expected_sha256=None, expected_rows=3)
        self.common, self.contract = common_records.load_common_records(self.output)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_original_fields_distinct_text_and_order_survive_one_command(self):
        self.assertEqual(self.source.read_bytes(), self.original_bytes)
        self.assertEqual([{name: row[name] for name in pipeline.INPUT_COLUMNS} for row in self.common], self.rows)
        self.assertEqual([row["logical_csv_row"] for row in self.common], ["2", "3", "4"])
        checksum = pipeline.sha256_bytes(self.original_bytes)
        self.assertEqual([row["row_locator"] for row in self.common], [pipeline.row_locator(checksum, i) for i in (2, 3, 4)])
        self.assertNotEqual(self.common[0]["normalized__NCSL_Summary"], self.common[0]["normalized__summary"])
        self.assertNotEqual(self.common[0]["normalized__summary"], self.common[0]["normalized__bill_extracts"])
        self.assertEqual(set(self.contract["distinct_text_fields"]), set(common_records.TEXT_FIELDS))
        self.assertTrue(self.receipt["checks"]["all_raw_values_preserved"])
        self.assertEqual(len(self.receipt["ordered_tables"]), 8)

    def test_empty_whitespace_literal_and_json_null_are_not_imputed(self):
        row = self.common[1]
        self.assertEqual(row["summary"], "")
        self.assertEqual(row["bill_extracts"], " \n")
        self.assertEqual(row["normalized__summary"], "")
        self.assertEqual(row["cell_category__summary"], "empty_string")
        self.assertEqual(row["cell_category__bill_extracts"], "whitespace_only")
        self.assertEqual(row["Year"], "null")
        self.assertEqual(row["cell_category__Year"], "exact_literal:null")
        self.assertEqual(json.loads(self.common[0]["review__sponsor_array_json"]), ["A", None])
        self.assertEqual(json.loads(self.common[0]["review__party_array_json"]), ["D", None])
        self.assertEqual(row["review__party_parse_state"], "invalid_item_type")
        self.assertEqual(row["review__party_array_json"], "")

    def test_flags_remain_unresolved_and_all_publisher_filtered_rows_remain(self):
        self.assertEqual(len(self.common), 3)
        self.assertTrue(all(row["status"] == "filtered_not_ai" for row in self.common))
        self.assertTrue(all(row["review_status"] == "unreviewed_retained" for row in self.common))
        self.assertTrue(all(row["review__exact_normalized_text_duplicate_flag"] == "True" for row in self.common))
        self.assertEqual(self.common[0]["review__version_before_introduction"], "True")
        self.assertEqual(self.common[1]["review__introduction_date_parse_error"], "True")
        self.assertEqual(self.common[1]["review__version_before_introduction"], "")
        self.assertIn("bill_title_missing", json.loads(self.common[1]["review_reasons_json"]))

    def test_outcome_and_publisher_fields_cannot_be_misclassified_as_candidate(self):
        entries = self.contract["columns"]
        for name in ("Bill_Status", "Bill_Status_Grouped", "normalized__Bill_Status", "normalized__Bill_Status_Grouped"):
            self.assertEqual(entries[name]["role"], "outcome")
        for name in pipeline.SOURCE_ROLES["publisher_derived"]:
            self.assertEqual(entries[name]["role"], "publisher_derived")
            normalized = "normalized__" + name
            if normalized in entries:
                self.assertEqual(entries[normalized]["role"], "publisher_derived")
        self.assertEqual(entries["NCSL_Summary"]["role"], "evidence")
        self.assertTrue(all(item["use_in_model_now"] is False for item in entries.values()))
        self.assertFalse(any(name.lower() in {"target", "label", "split", "prediction"} for name in entries))
        self.assertEqual(self.common[0]["Bill_Status_Grouped"], "Pending")

    def test_contract_distinguishes_normalized_text_from_original_values(self):
        entries = self.contract["columns"]
        original = entries["Bill_Text"]
        normalized = entries["normalized__Bill_Text"]
        self.assertEqual(original["representation"], "original_csv_string")
        self.assertEqual(normalized["representation"], "unicode_nfc_whitespace_collapse_trim")
        self.assertIn("Original value retained", original["description"])
        self.assertIn("whitespace collapsed and trimmed", normalized["description"])
        self.assertEqual(normalized["source_column"], "Bill_Text")

    def test_tampered_values_or_contract_fail_validation(self):
        path = self.output / common_records.COMMON_FILE
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            validate_outputs.validate(self.source, self.output)
        prepare.prepare(self.source, self.output, expected_sha256=None, expected_rows=3)
        path = self.output / common_records.CONTRACT_FILE
        contract = json.loads(path.read_text(encoding="utf-8"))
        contract["columns"]["Bill_Status_Grouped"]["role"] = "candidate"
        pipeline.write_json(path, contract)
        summary_path = self.output / common_records.SUMMARY_FILE
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["output_artifacts"][common_records.CONTRACT_FILE]["sha256"] = pipeline.sha256_bytes(path.read_bytes())
        pipeline.write_json(summary_path, summary)
        with self.assertRaisesRegex(ValueError, "canonical contract"):
            validate_outputs.validate(self.source, self.output)

    def test_rerun_reproduces_common_artifacts_and_keeps_external_review_notes(self):
        human = self.root / "human_review.csv"
        human.write_text("status,note\nunreviewed,\n", encoding="utf-8")
        before = {name: (self.output / name).read_bytes() for name in (common_records.COMMON_FILE, common_records.CONTRACT_FILE)}
        prepare.prepare(self.source, self.output, expected_sha256=None, expected_rows=3)
        for name, value in before.items():
            self.assertEqual((self.output / name).read_bytes(), value)
        self.assertEqual(human.read_text(encoding="utf-8"), "status,note\nunreviewed,\n")

    def test_one_command_defaults_work_from_repository_and_code_folder(self):
        repository = self.root / "repository"
        code = repository / "josue_src"
        code.mkdir(parents=True)
        for name in ("pipeline.py", "audit_common_inputs.py", "common_records.py", "validate_outputs.py", "prepare.py"):
            shutil.copyfile(PREPARATION / name, code / name)
        # Pin a controlled test snapshot exactly as production pins the real source.
        path = code / "pipeline.py"
        content = path.read_text(encoding="utf-8")
        content = content.replace(pipeline.EXPECTED_SHA256, pipeline.sha256_bytes(self.original_bytes))
        content = content.replace("EXPECTED_ROWS = 2571", "EXPECTED_ROWS = 3")
        path.write_text(content, encoding="utf-8")
        source = repository / "data/raw/Final_Database.csv"
        source.parent.mkdir(parents=True)
        source.write_bytes(self.original_bytes)
        expected_output = repository / "data/processed/common_intake"
        root_run = subprocess.run([sys.executable, "josue_src/prepare.py"], cwd=repository,
                                  capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(root_run.stdout)["source_rows"], 3)
        first = (expected_output / common_records.COMMON_FILE).read_bytes()
        folder_run = subprocess.run([sys.executable, "prepare.py"], cwd=code,
                                    capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(folder_run.stdout)["source_rows"], 3)
        self.assertEqual((expected_output / common_records.COMMON_FILE).read_bytes(), first)
        self.assertFalse((code / "output").exists())
        self.assertEqual(source.read_bytes(), self.original_bytes)

    def test_loader_reads_large_text_in_a_fresh_python_process(self):
        rows = [dict(self.rows[0])]
        rows[0]["Bill_Text"] = "AI shall NOT permit this.\n" * 7000
        source, output = self.root / "large.csv", self.root / "large-output"
        with source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=pipeline.INPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        prepare.prepare(source, output, expected_sha256=None, expected_rows=1)
        program = ("import sys; sys.path.insert(0, sys.argv[1]); "
                   "from common_records import load_common_records; "
                   "rows, contract = load_common_records(sys.argv[2]); "
                   "print(len(rows[0]['Bill_Text']))")
        run = subprocess.run([sys.executable, "-c", program, str(PREPARATION), str(output)],
                             capture_output=True, text=True, check=True)
        self.assertEqual(int(run.stdout), len(rows[0]["Bill_Text"]))


if __name__ == "__main__":
    unittest.main()
