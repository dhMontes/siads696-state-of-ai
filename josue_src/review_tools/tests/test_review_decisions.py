"""Regression tests for a persistent human log independent of generated CSVs.
"""

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]
PREPARATION = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import review_decisions as review


class ReviewLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="review-log-fixture-", dir=TOOLS / "tests")
        self.root = Path(self.temp.name)
        self.generated = self.root / "generated"
        self.generated.mkdir()
        self.review_dir = self.root / "review"
        self.review_dir.mkdir()
        self.source = self.root / "source.csv"
        self.source.write_bytes(b"Bill_Number,Year\nHB 1,2025\nHB 2,2025\n")
        self.source_sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.queue = self.generated / "review_records.csv"
        self.audit = self.generated / "common_input_audit.json"
        self.decisions = self.review_dir / "review_decisions.csv"
        self.queue_rows = []
        for logical_row, reason in ((2, review.REVIEW_REASONS[0]),
                                    (2, review.REVIEW_REASONS[2]),
                                    (3, review.REVIEW_REASONS[1])):
            row = dict.fromkeys(review.QUEUE_COLUMNS, "")
            row.update({"row_locator": f"sha256:{self.source_sha}#csv-record={logical_row}",
                        "logical_csv_row": str(logical_row), "review_reason": reason,
                        "review_status": "unreviewed_retained"})
            self.queue_rows.append(row)
        self.write_queue_and_audit()

    def tearDown(self):
        self.temp.cleanup()

    def write_csv(self, path, fields, rows):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def write_queue_and_audit(self):
        self.write_csv(self.queue, review.QUEUE_COLUMNS, self.queue_rows)
        queue_bytes = self.queue.read_bytes()
        self.metadata = {
            "source": {"sha256_before": self.source_sha, "sha256_after": self.source_sha,
                       "unchanged": True, "rows": 2, "bytes": self.source.stat().st_size},
            "checks": {"source_unchanged": True},
            "output_artifacts": {"review_records.csv": {
                "sha256": hashlib.sha256(queue_bytes).hexdigest(), "bytes": len(queue_bytes),
                "rows": len(self.queue_rows), "columns": list(review.QUEUE_COLUMNS)}},
            "review_queue": {
                "record_reason_entries": len(self.queue_rows),
                "distinct_source_records": len({row["row_locator"] for row in self.queue_rows}),
                "reason_counts": {reason: sum(row["review_reason"] == reason for row in self.queue_rows)
                                  for reason in review.REVIEW_REASONS}},
        }
        self.save_audit()

    def save_audit(self):
        self.audit.write_text(json.dumps(self.metadata), encoding="utf-8")

    def initialize(self):
        return review.initialize_review_log(self.source, self.audit, self.queue, self.decisions)

    def validate(self):
        return review.validate_review_log(self.source, self.audit, self.queue, self.decisions)

    def decision_rows(self):
        with self.decisions.open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    def save_decisions(self, rows):
        self.write_csv(self.decisions, review.DECISION_COLUMNS, rows)

    def test_full_initialization_has_reason_entries_not_unique_record_count(self):
        originals = {path: path.read_bytes() for path in (self.source, self.queue, self.audit)}
        summary = self.initialize()
        self.assertEqual(summary["record_reason_entries"], 3)
        self.assertEqual(summary["distinct_source_records"], 2)
        self.assertEqual(summary["status_counts"]["unreviewed"], 3)
        self.assertEqual(self.validate(), summary)
        self.assertTrue(all(row["status"] == "unreviewed" and row["reviewed_at"] == ""
                            and row["note"] == "" and row["evidence_reference"] == ""
                            for row in self.decision_rows()))
        for path, data in originals.items():
            self.assertEqual(path.read_bytes(), data)

    def test_initialization_refuses_both_empty_and_populated_existing_logs(self):
        for content in (b"", b"keep a saved review\n"):
            with self.subTest(content=content):
                self.decisions.write_bytes(content)
                with self.assertRaisesRegex(ValueError, "refuses overwrite"):
                    self.initialize()
                self.assertEqual(self.decisions.read_bytes(), content)

    def test_review_values_survive_generated_queue_and_audit_rerun(self):
        self.initialize()
        rows = self.decision_rows()
        rows[0].update(status="needs_source_check", note="Compare dated version, then discuss.\nNo change applied.",
                       evidence_reference="Saved official-page reference", reviewed_at="2026-10-05")
        self.save_decisions(rows)
        persisted = self.decisions.read_bytes()
        self.write_queue_and_audit()
        self.metadata["generated_at_utc"] = "2026-10-06T00:00:00+00:00"
        self.save_audit()
        summary = self.validate()
        self.assertEqual(summary["status_counts"]["needs_source_check"], 1)
        self.assertEqual(self.decisions.read_bytes(), persisted)
        self.assertEqual(self.decision_rows()[0], rows[0])

    def test_modified_queue_is_rejected_before_log_creation(self):
        self.queue.write_bytes(self.queue.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Queue checksum"):
            self.initialize()
        self.assertFalse(self.decisions.exists())

    def test_changed_raw_source_is_rejected_and_saved_log_is_preserved(self):
        self.initialize()
        persisted = self.decisions.read_bytes()
        self.source.write_bytes(self.source.read_bytes().replace(b"HB 1", b"HB 9"))
        with self.assertRaisesRegex(ValueError, "Source checksum"):
            self.validate()
        self.assertEqual(self.decisions.read_bytes(), persisted)

    def test_wrong_source_and_wrong_audit_checksum_fail_closed(self):
        for field in ("sha256_before", "sha256_after"):
            with self.subTest(field=field):
                self.write_queue_and_audit()
                self.metadata["source"][field] = "a" * 64
                self.save_audit()
                with self.assertRaises(ValueError):
                    self.initialize()
                self.assertFalse(self.decisions.exists())
        self.write_queue_and_audit()
        self.metadata["output_artifacts"]["review_records.csv"]["sha256"] = "b" * 64
        self.save_audit()
        with self.assertRaisesRegex(ValueError, "Queue checksum"):
            self.initialize()

    def test_stale_saved_source_or_queue_checksum_is_rejected(self):
        self.initialize()
        original = self.decision_rows()
        for name in ("source_sha256", "queue_sha256"):
            with self.subTest(name=name):
                rows = [dict(row) for row in original]
                rows[0][name] = "a" * 64
                self.save_decisions(rows)
                with self.assertRaisesRegex(ValueError, "stale"):
                    self.validate()

    def test_changed_queue_with_updated_audit_still_rejects_old_log(self):
        self.initialize()
        self.queue_rows[0]["jurisdiction_raw"] = "A corrected diagnostic label"
        self.write_queue_and_audit()
        with self.assertRaisesRegex(ValueError, "stale queue"):
            self.validate()

    def test_duplicate_unknown_and_missing_saved_keys_are_rejected(self):
        self.initialize()
        original = self.decision_rows()
        cases = ((original + [original[0]], "duplicate"),
                 ([dict(original[0], review_reason="unrecognized_reason")] + original[1:], "unknown"),
                 ([dict(original[0], row_locator="unknown_locator")] + original[1:], "unknown"),
                 (original[:-1], "missing 1"))
        for rows, message in cases:
            with self.subTest(message=message, count=len(rows)):
                self.save_decisions(rows)
                with self.assertRaisesRegex(ValueError, message):
                    self.validate()

    def test_review_status_and_iso_date_rules_reject_invalid_values(self):
        self.initialize()
        original = self.decision_rows()
        for status, reviewed_at, message in (
            ("excluded", "2026-10-05", "invalid status"),
            ("reviewed_no_change", "", "ISO"),
            ("needs_team_decision", "2026-02-30", "ISO"),
            ("needs_source_check", "20261005", "ISO"),
            ("reviewed_no_change", "2026-10-05T12:00:00", "ISO"),
            ("unreviewed", "2026-10-05", "Unreviewed"),
        ):
            with self.subTest(status=status, reviewed_at=reviewed_at):
                rows = [dict(row) for row in original]
                rows[0].update(status=status, reviewed_at=reviewed_at)
                self.save_decisions(rows)
                with self.assertRaisesRegex(ValueError, message):
                    self.validate()

    def test_all_reviewed_statuses_and_reordered_complete_log_are_valid(self):
        self.initialize()
        rows = self.decision_rows()
        for row, status in zip(rows, review.STATUSES[1:]):
            row.update(status=status, reviewed_at="2026-10-05")
        self.save_decisions(list(reversed(rows)))
        self.assertEqual(self.validate()["status_counts"],
                         {status: (0 if status == "unreviewed" else 1) for status in review.STATUSES})

    def test_malformed_schema_or_record_is_rejected(self):
        self.initialize()
        original = self.decisions.read_bytes()
        for malformed in (original.replace(b"evidence_reference", b"unexpected_column", 1),
                          original + b"extra,too,few,values\n"):
            with self.subTest(malformed_size=len(malformed)):
                self.decisions.write_bytes(malformed)
                with self.assertRaisesRegex(ValueError, "schema|malformed"):
                    self.validate()

    def test_duplicate_queue_key_and_invalid_locator_reject_even_matching_hash(self):
        original = [dict(row) for row in self.queue_rows]
        for rows, message in ((original + [original[0]], "duplicate"),
                              ([dict(original[0], row_locator="wrong_source")] + original[1:], "locator")):
            with self.subTest(message=message):
                self.queue_rows = rows
                self.write_queue_and_audit()
                with self.assertRaisesRegex(ValueError, message):
                    self.initialize()
                self.assertFalse(self.decisions.exists())

    def test_audit_missing_fields_inconsistent_counts_and_changed_source_are_rejected(self):
        for mutation in (lambda data: data.pop("source"),
                         lambda data: data["review_queue"].update(distinct_source_records=3),
                         lambda data: data["source"].update(unchanged=False),
                         lambda data: data["output_artifacts"]["review_records.csv"].update(rows=True)):
            self.write_queue_and_audit()
            mutation(self.metadata)
            self.save_audit()
            with self.assertRaises(ValueError):
                self.initialize()
            self.assertFalse(self.decisions.exists())

    def test_log_in_generated_directory_is_refused_without_writing(self):
        output = self.generated / "notes.csv"
        with self.assertRaisesRegex(ValueError, "outside generated"):
            review.initialize_review_log(self.source, self.audit, self.queue, output)
        self.assertFalse(output.exists())

    def test_cli_prints_counts_and_returns_nonzero_for_invalid_log(self):
        common = ["--source", str(self.source), "--audit", str(self.audit), "--queue", str(self.queue)]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = review.main(["init", *common, "--output", str(self.decisions)])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["record_reason_entries"], 3)
        self.assertNotIn(self.source_sha, stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        self.decisions.write_bytes(b"bad log\n")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            result = review.main(["validate", *common, "--decisions", str(self.decisions)])
        self.assertEqual(result, 1)
        self.assertIn("check failed", stderr.getvalue())


class GeneratedPipelinePersistenceTests(unittest.TestCase):
    def test_saved_review_survives_real_fixture_pipeline_and_audit_rerun(self):
        # The shared handoff contains the same sibling pipeline/audit modules.
        sys.path.insert(0, str(PREPARATION))
        import audit_common_inputs
        import pipeline

        with tempfile.TemporaryDirectory(prefix="review-pipeline-fixture-", dir=TOOLS / "tests") as folder:
            root = Path(folder)
            source, generated = root / "source.csv", root / "generated"
            review_folder = root / "review"
            review_folder.mkdir()
            row = dict.fromkeys(pipeline.INPUT_COLUMNS, "")
            row.update(Bill_Number="HB 1", Jurisdiction="Example State", Year="2025",
                       Bill_Title="Title", Bill_Text="Independent example policy text.",
                       Introduction_Date="01/01/2025", Version_Date="02/01/2025")
            with source.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=pipeline.INPUT_COLUMNS, lineterminator="\n")
                writer.writeheader()
                writer.writerow(row)
            checksum = hashlib.sha256(source.read_bytes()).hexdigest()
            def rerun():
                pipeline.run_pipeline(source, generated, expected_sha256=checksum, expected_rows=1)
                audit_common_inputs.run_audit(source, generated, expected_sha256=checksum, expected_rows=1)
            rerun()
            audit, queue = generated / "common_input_audit.json", generated / "review_records.csv"
            decisions = review_folder / "review_decisions.csv"
            review.initialize_review_log(source, audit, queue, decisions)
            with decisions.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            rows[0].update(status="needs_team_decision", note="Discuss timing question.", reviewed_at="2026-10-05")
            with decisions.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=review.DECISION_COLUMNS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            saved_log, saved_source = decisions.read_bytes(), source.read_bytes()
            rerun()
            result = review.validate_review_log(source, audit, queue, decisions)
            self.assertEqual(result["status_counts"]["needs_team_decision"], 1)
            self.assertEqual(decisions.read_bytes(), saved_log)
            self.assertEqual(source.read_bytes(), saved_source)


if __name__ == "__main__":
    unittest.main()
