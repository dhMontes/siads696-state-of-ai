"""Validate complete source preservation, ordered joins, roles and hashes.
"""

import argparse
from collections import defaultdict
import json
from pathlib import Path

import audit_common_inputs as audit
import common_records
import pipeline


def validate(source=pipeline.DEFAULT_SOURCE, output=pipeline.DEFAULT_OUTPUT):
    """Verify saved outputs against the source and write a validation receipt."""
    source, output = Path(source).resolve(), Path(output).resolve()
    checksum = pipeline.sha256_bytes(source.read_bytes())
    columns, original = pipeline.load_source(source)
    expected = [pipeline.row_locator(checksum, i) for i in range(2, len(original) + 2)]
    # Check each file and its ordered source links before inspecting field values.
    artifacts = {}
    ordered_tables = []
    for summary_name in ("quality_summary.json", "common_input_audit.json", "common_records_summary.json"):
        summary = json.loads((output / summary_name).read_text(encoding="utf-8"))
        if summary["source"]["sha256_before"] != checksum or summary["source"]["rows"] != len(original):
            raise ValueError("Summary does not describe selected source: " + summary_name)
        common_records.verify_artifacts(output, summary)
        artifacts[summary_name] = pipeline.sha256_bytes((output / summary_name).read_bytes())
        for filename, artifact in summary["output_artifacts"].items():
            artifacts[filename] = artifact["sha256"]
            if filename.endswith(".csv") and filename not in {"review_records.csv", "column_missingness.csv"}:
                rows = audit.read_table(output / filename)
                if [row["row_locator"] for row in rows] != expected:
                    raise ValueError("Complete ordered row links failed: " + filename)
                ordered_tables.append(filename)
    raw = audit.read_table(output / "raw_evidence.csv")
    common, contract = common_records.load_common_records(output)
    for filename, rows in (("raw_evidence.csv", raw), (common_records.COMMON_FILE, common)):
        if [{name: row[name] for name in columns} for row in rows] != original:
            raise ValueError("Original source value preservation failed: " + filename)
    # Recompute the contract and derived values to check the complete handoff.
    canonical = common_records.make_contract(list(common[0]))
    if contract != canonical:
        raise ValueError("Column roles/representations differ from canonical contract")
    flags = audit.read_table(output / "quality_flags.csv")
    reasons = defaultdict(list)
    for entry in audit.read_table(output / "review_records.csv"):
        reasons[entry["row_locator"]].append(entry["review_reason"])
    for record_number, (row, raw_row, row_flags) in enumerate(zip(common, original, flags), start=2):
        if row["source_sha256"] != checksum or row["logical_csv_row"] != str(record_number):
            raise ValueError("Common source provenance mismatch")
        for name in common_records.NORMALIZED_COLUMNS:
            if row["normalized__" + name] != pipeline.clean_text(raw_row[name]):
                raise ValueError("Conservative normalization mismatch: " + name)
        for name in columns:
            if row["cell_category__" + name] != audit.cell_category(raw_row[name]):
                raise ValueError("Cell category mismatch: " + name)
        for name, value in row_flags.items():
            if name != "row_locator" and row["review__" + name] != value:
                raise ValueError("Joined review flag mismatch: " + name)
        for prefix, source_name in (("introduction", "Introduction_Date"), ("version", "Version_Date")):
            iso = pipeline.parse_date(raw_row[source_name])["iso"]
            if row[prefix + "_date_iso"] != iso or row[prefix + "_year_parsed"] != iso[:4]:
                raise ValueError("Parsed date observation mismatch: " + source_name)
        if json.loads(row["review_reasons_json"]) != reasons[row["row_locator"]]:
            raise ValueError("Joined review queue mismatch")
        if row["review_status"] != "unreviewed_retained":
            raise ValueError("Generated common table must not imply completed human review")
    if pipeline.sha256_bytes(source.read_bytes()) != checksum:
        raise RuntimeError("Source changed during validation")
    receipt = {"source_sha256": checksum, "source_rows": len(original), "source_columns": len(columns),
               "source_unchanged": True, "ordered_tables": ordered_tables,
               "artifact_sha256": artifacts,
               "checks": {"all_raw_values_preserved": True, "all_common_values_verified": True,
                          "complete_ordered_source_links": True, "all_artifact_hashes_verified": True,
                          "column_roles_verified": True, "human_review_claimed": False,
                          "rows_dropped_or_merged": 0, "targets_splits_models_created": False}}
    pipeline.write_json(output / "validation_receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=pipeline.DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=pipeline.DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(validate(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
