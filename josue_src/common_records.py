"""Build a complete source-preserving common handoff, never a feature matrix.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

import audit_common_inputs as audit
import pipeline


NORMALIZED_COLUMNS = (
    "Bill_Number", "measure_code", "Bill_Title", "Jurisdiction", "NCSL_Summary",
    "NCSL_Category", "Bill_URL", "Year", "Bill_Status", "State_Political_Control",
    "Regional_Cluster_ID", "Bill_Text", "bill_extracts", "summary", "status",
    "Bill_Status_Grouped",
)
TEXT_FIELDS = ("Bill_Text", "Bill_Title", "NCSL_Summary", "summary", "bill_extracts")
COMMON_FILE = "common_records.csv"
CONTRACT_FILE = "common_records_contract.json"
SUMMARY_FILE = "common_records_summary.json"


def verify_artifacts(output: Path, summary: dict) -> None:
    """Check that the saved files still match the hashes in their summary."""
    for filename, artifact in summary["output_artifacts"].items():
        actual = pipeline.sha256_bytes((output / filename).read_bytes())
        if actual != artifact["sha256"]:
            raise ValueError("Output checksum mismatch: " + filename)


def build_common_records(source: Path, output: Path) -> dict:
    """Join already verified preparation evidence in immutable source order."""
    source, output = Path(source).resolve(), Path(output).resolve()
    checksum = pipeline.sha256_bytes(source.read_bytes())
    columns, raw_rows = pipeline.load_source(source)
    intake = json.loads((output / "quality_summary.json").read_text(encoding="utf-8"))
    audited = json.loads((output / "common_input_audit.json").read_text(encoding="utf-8"))
    for summary in (intake, audited):
        if summary["source"]["sha256_before"] != checksum or summary["source"]["rows"] != len(raw_rows):
            raise ValueError("Preparation evidence does not describe selected source")
        verify_artifacts(output, summary)
    expected = [pipeline.row_locator(checksum, i) for i in range(2, len(raw_rows) + 2)]
    flags = audit.read_table(output / "quality_flags.csv")
    dates = audit.read_table(output / "date_correction_record.csv")
    for filename, rows in (("quality_flags.csv", flags), ("date_correction_record.csv", dates)):
        if [row["row_locator"] for row in rows] != expected:
            raise ValueError("Ordered source links differ: " + filename)
    reasons = defaultdict(list)
    expected_set = set(expected)
    for entry in audit.read_table(output / "review_records.csv"):
        if entry["row_locator"] not in expected_set:
            raise ValueError("Review queue contains unknown source locator")
        reasons[entry["row_locator"]].append(entry["review_reason"])
    common = []
    for logical_record, (raw, row_flags, row_dates) in enumerate(zip(raw_rows, flags, dates), start=2):
        locator = pipeline.row_locator(checksum, logical_record)
        record = {"row_locator": locator, "source_sha256": checksum,
                  "logical_csv_row": logical_record, **raw}
        record.update({"normalized__" + name: pipeline.clean_text(raw[name]) for name in NORMALIZED_COLUMNS})
        record.update({"cell_category__" + name: audit.cell_category(raw[name]) for name in columns})
        record.update({name: row_dates[name] for name in ("introduction_date_iso", "version_date_iso")})
        record["introduction_year_parsed"] = row_dates["introduction_date_iso"][:4]
        record["version_year_parsed"] = row_dates["version_date_iso"][:4]
        record.update({"review__" + name: value for name, value in row_flags.items() if name != "row_locator"})
        record["review_reasons_json"] = pipeline.json_text(reasons[locator])
        record["review_status"] = "unreviewed_retained"
        common.append(record)
    fields = pipeline.write_csv(output / COMMON_FILE, common)
    written = audit.read_table(output / COMMON_FILE)
    expected_written = [{name: str(value) for name, value in row.items()} for row in common]
    if written != expected_written:
        raise RuntimeError("Common handoff failed complete value roundtrip")
    if pipeline.sha256_bytes(source.read_bytes()) != checksum:
        raise RuntimeError("Source changed while creating common handoff")
    contract = make_contract(fields)
    pipeline.write_json(output / CONTRACT_FILE, contract)
    artifacts = {name: {"sha256": pipeline.sha256_bytes((output / name).read_bytes()),
                        "bytes": (output / name).stat().st_size}
                 for name in (COMMON_FILE, CONTRACT_FILE)}
    artifacts[COMMON_FILE].update({"rows": len(common), "columns": len(fields)})
    summary = {"source": {"sha256_before": checksum, "rows": len(raw_rows), "unchanged": True},
               "status": "complete_common_preparation_unreviewed",
               "checks": {"all_original_fields_retained": True, "all_original_values_preserved": True,
                          "complete_ordered_source_links": True, "value_roundtrip_verified": True,
                          "rows_dropped": 0, "rows_merged": 0, "nulls_or_markers_filled": 0,
                          "outcomes_encoded": False, "eligibility_chosen": False,
                          "vectorization_splits_or_models": False},
               "column_role_counts": dict(Counter(item["role"] for item in contract["columns"].values())),
               "output_artifacts": artifacts}
    pipeline.write_json(output / SUMMARY_FILE, summary)
    return summary


def make_contract(fields: list[str]) -> dict:
    """Describe each field's source, representation and intended review role."""
    entries = {}
    for name in fields:
        source_column = name if name in pipeline.INPUT_COLUMNS else None
        representation = "original_csv_string"
        if name.startswith("normalized__"):
            source_column = name.removeprefix("normalized__")
            representation = "unicode_nfc_whitespace_collapse_trim"
        if source_column:
            role = pipeline.source_role(source_column)
            if name.startswith("normalized__"):
                description = (
                    "Text normalized to Unicode NFC with whitespace collapsed and trimmed; "
                    "the original value remains in the source column."
                )
            else:
                description = "Original value retained; column role does not authorize use in a model."
        elif name in {"row_locator", "source_sha256", "logical_csv_row"}:
            role, representation = "provenance", "source_locator"
            description = "Record provenance and joins only; exclude from features."
        elif name.startswith("cell_category__"):
            source_column = name.removeprefix("cell_category__")
            role, representation = "review", "physical_blank_or_exact_literal_category"
            description = "Observation only; literal markers are never recoded or filled."
        elif name in {"introduction_date_iso", "introduction_year_parsed"}:
            source_column, role, representation = "Introduction_Date", "candidate", "parsed_unverified_date"
            description = "Explicit date parse only; availability at prediction time requires review."
        elif name in {"version_date_iso", "version_year_parsed"}:
            source_column, role, representation = "Version_Date", "evidence", "parsed_unverified_date"
            description = "Parsed version observation; does not correct source chronology or define sessions."
        else:
            role, representation = "review", "diagnostic_observation"
            description = "Unresolved diagnostic or parsed-array evidence; no exclusion or correction applied."
        entries[name] = {"role": role, "source_column": source_column,
                         "representation": representation, "use_in_model_now": False,
                         "description": description}
    return {"contract_version": 1, "file": COMMON_FILE,
            "status": "common preparation, not a model matrix or approved cohort",
            "roles": {
                "candidate": "Source text or observed metadata available for owner review; no predictor choice is made.",
                "evidence": "Source lookup, date or external summary/category evidence; lineage and timing remain unverified.",
                "outcome": "Supplied legislative status/grouping; not encoded targets or independently verified terminal outcomes.",
                "publisher_derived": "Publisher summaries, extracts, analysis, scores and processing metadata; kept apart from candidate fields.",
                "provenance": "Immutable source identity and record order for joins; never predictors.",
                "review": "Availability, parse, duplicate, chronology and structural observations; no automatic decisions."},
            "original_source_fields": list(pipeline.INPUT_COLUMNS),
            "distinct_text_fields": list(TEXT_FIELDS), "columns": entries,
            "array_null_policy": "Sponsor and party JSON arrays preserve null items; invalid/missing arrays remain unavailable without repair.",
            "normalization": "NFC, whitespace collapse and trim only. Original cells remain exact. Structured JSON, scores and retry counts are not coerced.",
            "lineage_boundary": "NCSL_Summary, summary and bill_extracts remain distinct. Roles do not establish human/generated lineage or approval.",
            "leakage_boundary": "Text and titles may retain administrative headers, sponsors, identifiers and outcome clues. Role separation does not establish leakage-free inputs.",
            "decision_boundary": "No imputation, filter, merge, source correction, predictor selection, target mapping, cohort, split, vectorizer or model."}


def load_common_records(output: Path = pipeline.DEFAULT_OUTPUT) -> tuple[list[dict[str, str]], dict]:
    """Read verified strings and contract without automatic dtype/null inference."""
    # Fresh loader-only processes have not run pipeline.load_source's CSV limit.
    csv.field_size_limit(100_000_000)
    output = Path(output)
    summary = json.loads((output / SUMMARY_FILE).read_text(encoding="utf-8"))
    verify_artifacts(output, summary)
    contract = json.loads((output / CONTRACT_FILE).read_text(encoding="utf-8"))
    rows = audit.read_table(output / COMMON_FILE)
    if len(rows) != summary["source"]["rows"]:
        raise ValueError("Common table record count mismatch")
    expected = [pipeline.row_locator(summary["source"]["sha256_before"], i) for i in range(2, len(rows) + 2)]
    if [row["row_locator"] for row in rows] != expected:
        raise ValueError("Common table ordered source links differ")
    if not rows or set(rows[0]) != set(contract["columns"]):
        raise ValueError("Common table schema differs from column contract")
    return rows, contract
