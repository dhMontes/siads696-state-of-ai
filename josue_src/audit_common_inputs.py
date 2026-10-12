"""Audit common source intake without selecting either method owner's inputs.

Literal cell markers are observations, never automatic missing-value rules.
The audit retains every source locator and does not refresh sources, alter
raw cells, filter or merge records, label outcomes, vectorize, split or fit.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import sys

import pipeline


# Case, punctuation and surrounding whitespace are intentionally significant.
# Tokens like [] can be legitimate structured values, so none is recoded.
EXACT_SENTINELS = (
    "NA", "N/A", "n/a", "NaN", "nan", "NaT", "None", "none", "NULL",
    "Null", "null", "[]", "{}", "-", "--",
)
TEXT_COLUMNS = ("Bill_Text", "NCSL_Summary", "summary", "bill_extracts")
OVERLAP_COLUMNS = TEXT_COLUMNS[1:]
REVIEW_FLAGS = (
    "version_before_introduction", "version_after_introduction",
    "bill_title_missing", "exact_normalized_text_duplicate_flag",
)
REVIEW_COLUMNS = (
    "row_locator", "logical_csv_row", "review_reason", "review_status",
    "jurisdiction_raw", "bill_number_raw", "source_year_raw",
    "introduction_date_raw", "version_date_raw", "introduction_date_iso",
    "version_date_iso", "normalized_text_group_id", "normalized_text_group_size",
)
PREFIXES = {
    "Bill_Text": "bill_text", "NCSL_Summary": "ncsl_summary",
    "summary": "summary", "bill_extracts": "bill_extracts",
}


def blank_kind(value: str) -> str:
    """Distinguish a zero-length cell from a nonempty whitespace-only cell."""
    if value == "":
        return "empty_string"
    if not value.strip():
        return "whitespace_only"
    return "nonblank"


def cell_category(value: str) -> str:
    kind = blank_kind(value)
    if kind != "nonblank":
        return kind
    if value in EXACT_SENTINELS:
        return "exact_literal:" + value
    return "other_nonblank"


def raw_available(value: str) -> bool:
    """Represent raw nonblank availability only, not useful/eligible content."""
    return blank_kind(value) == "nonblank"


def overlap_counts(rows: list[dict[str, str]]) -> list[dict]:
    """Emit all eight combinations, including zero-count combinations."""
    counts = Counter(tuple(raw_available(row[name]) for name in OVERLAP_COLUMNS)
                     for row in rows)
    return [{"availability": dict(zip(OVERLAP_COLUMNS, pattern)),
             "rows": counts[pattern]}
            for pattern in itertools.product((False, True), repeat=3)]


def coverage_counts(rows: list[dict[str, str]]) -> dict:
    """Count blank cells once per text field, retaining empty-group results."""
    total = len(rows)
    coverage = {}
    for name in TEXT_COLUMNS:
        blank_rows = sum(not raw_available(row[name]) for row in rows)
        coverage[name] = {
            "raw_nonblank_rows": total - blank_rows,
            "raw_blank_rows": blank_rows,
            "raw_blank_fraction": blank_rows / total if total else None,
        }
    return coverage


def segment_coverage(rows: list[dict[str, str]], column: str) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[row[column]].append(row)
    return [{"source_column": column, "source_value_raw": value,
             "source_value_cell_category": cell_category(value),
             "rows": len(groups[value]), "coverage": coverage_counts(groups[value]),
             "summary_extract_overlap": overlap_counts(groups[value])}
            for value in sorted(groups)]


def repeated_state_bill_across_years(rows: list[dict[str, str]], checksum: str) -> dict:
    """Group provisional labels for inspection; not duplicate dispositions."""
    groups = defaultdict(list)
    incomplete = 0
    for record, row in enumerate(rows, start=2):
        state, bill, year = (pipeline.clean_text(row[name])
                             for name in ("Jurisdiction", "Bill_Number", "Year"))
        if not (state and bill and year):
            incomplete += 1
            continue
        groups[(state, bill)].append((year, record))
    repeated = []
    for (state, bill), items in sorted(groups.items()):
        years = sorted({year for year, _ in items})
        if len(years) > 1:
            repeated.append({"jurisdiction_label_normalized": state,
                             "bill_number_label_normalized": bill,
                             "supplied_year_labels": years, "rows": len(items),
                             "row_locators": [pipeline.row_locator(checksum, record)
                                              for _, record in items]})
    return {"groups_spanning_multiple_supplied_years": len(repeated),
            "rows_in_these_groups": sum(group["rows"] for group in repeated),
            "rows_with_incomplete_labels": incomplete,
            "groups": repeated,
            "interpretation": "Repeated provisional jurisdiction/bill labels across supplied Year values. "
                              "Not verified sessions, duplicate bills or a merge/drop instruction."}


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_table(path: Path, columns: list[str] | tuple[str, ...], rows: list[dict]) -> None:
    # Unlike the intake helper, header-only review output is valid when no flags occur.
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_review_records(raw_rows: list[dict[str, str]], flags: list[dict[str, str]],
                         dates: list[dict[str, str]], checksum: str) -> list[dict]:
    records = []
    for logical_record, (raw, row_flags, row_dates) in enumerate(zip(raw_rows, flags, dates), start=2):
        for reason in REVIEW_FLAGS:
            if row_flags[reason] != "True":
                continue
            records.append({
                "row_locator": pipeline.row_locator(checksum, logical_record),
                "logical_csv_row": logical_record, "review_reason": reason,
                "review_status": "unreviewed_retained",
                "jurisdiction_raw": raw["Jurisdiction"], "bill_number_raw": raw["Bill_Number"],
                "source_year_raw": raw["Year"], "introduction_date_raw": raw["Introduction_Date"],
                "version_date_raw": raw["Version_Date"],
                "introduction_date_iso": row_dates["introduction_date_iso"],
                "version_date_iso": row_dates["version_date_iso"],
                "normalized_text_group_id": row_flags["exact_normalized_text_group_id"],
                "normalized_text_group_size": row_flags["exact_normalized_text_group_size"],
            })
    return records


def select_examples(records: list[dict], per_reason: int = 3) -> dict:
    """Stable lowest logical CSV records per reason, irrespective of input order."""
    if per_reason < 1:
        raise ValueError("Example limit must be positive")
    selected = {}
    for reason in REVIEW_FLAGS:
        candidates = [row for row in records if row["review_reason"] == reason]
        candidates.sort(key=lambda row: (int(row["logical_csv_row"]), row["row_locator"]))
        selected[reason] = candidates[:per_reason]
    return selected


def run_audit(source: Path = pipeline.DEFAULT_SOURCE, output: Path = pipeline.DEFAULT_OUTPUT,
              expected_sha256: str | None = pipeline.EXPECTED_SHA256,
              expected_rows: int | None = pipeline.EXPECTED_ROWS) -> dict:
    source, output = Path(source).resolve(), Path(output).resolve()
    if source.parent == output or source == output:
        raise ValueError("Audit output must be separate from the preserved input")
    source_before = pipeline.sha256_bytes(source.read_bytes())
    if expected_sha256 is not None and source_before != expected_sha256:
        raise ValueError("Source checksum differs from the preserved v4 input")
    columns, raw_rows = pipeline.load_source(source)
    if expected_rows is not None and len(raw_rows) != expected_rows:
        raise ValueError("Source row count differs from the preserved v4 input")
    if not raw_rows:
        raise ValueError("Common audit requires at least one source record")

    intake = json.loads((output / "quality_summary.json").read_text(encoding="utf-8"))
    if intake["source"]["sha256_before"] != source_before or intake["source"]["rows"] != len(raw_rows):
        raise ValueError("Intake evidence does not describe this source")
    required = ("column_contract.json", "quality_flags.csv", "date_correction_record.csv")
    input_artifacts = {}
    for filename in required:
        checksum = pipeline.sha256_bytes((output / filename).read_bytes())
        if checksum != intake["output_artifacts"][filename]["sha256"]:
            raise ValueError("Intake evidence checksum mismatch: " + filename)
        input_artifacts[filename] = checksum
    contract = json.loads((output / "column_contract.json").read_text(encoding="utf-8"))
    if set(contract["input_columns"]) != set(columns):
        raise ValueError("Intake column contract is incomplete")
    flags = read_table(output / "quality_flags.csv")
    dates = read_table(output / "date_correction_record.csv")
    locators = [pipeline.row_locator(source_before, record) for record in range(2, len(raw_rows) + 2)]
    for filename, rows in (("quality_flags.csv", flags), ("date_correction_record.csv", dates)):
        if [row["row_locator"] for row in rows] != locators:
            raise ValueError("Intake evidence locator/order mismatch: " + filename)

    # Every source column has the same mutually exclusive category partition.
    categories = ("empty_string", "whitespace_only", *["exact_literal:" + token for token in EXACT_SENTINELS],
                  "other_nonblank")
    missingness = []
    for name in columns:
        counts = Counter(cell_category(row[name]) for row in raw_rows)
        for category in categories:
            missingness.append({"source_column": name, "cell_category": category,
                                "rows": counts[category], "denominator": len(raw_rows),
                                "fraction": counts[category] / len(raw_rows)})
    coverage = []
    for logical_record, raw in enumerate(raw_rows, start=2):
        row = {"row_locator": pipeline.row_locator(source_before, logical_record),
               "logical_csv_row": logical_record, "jurisdiction_raw": raw["Jurisdiction"],
               "source_year_raw": raw["Year"]}
        for name in TEXT_COLUMNS:
            prefix = PREFIXES[name]
            row[prefix + "_raw_available"] = raw_available(raw[name])
            row[prefix + "_blank_kind"] = blank_kind(raw[name])
            row[prefix + "_cell_category"] = cell_category(raw[name])
        coverage.append(row)
    review = build_review_records(raw_rows, flags, dates, source_before)
    reason_counts = dict(Counter(row["review_reason"] for row in review))
    reason_counts = {reason: reason_counts.get(reason, 0) for reason in REVIEW_FLAGS}
    overlap = overlap_counts(raw_rows)
    if sum(item["rows"] for item in overlap) != len(raw_rows):
        raise RuntimeError("Summary/extract overlap does not partition the source")
    if any(sum(row["rows"] for row in missingness if row["source_column"] == name) != len(raw_rows)
           for name in columns):
        raise RuntimeError("Column categories do not partition the source")

    # All evidence checks finish before any audit output is written.
    if pipeline.sha256_bytes(source.read_bytes()) != source_before:
        raise RuntimeError("Preserved source changed during audit")
    tables = {
        "column_missingness.csv": (list(missingness[0]), missingness),
        "text_coverage.csv": (list(coverage[0]), coverage),
        "review_records.csv": (REVIEW_COLUMNS, review),
    }
    for filename, (fields, rows) in tables.items():
        write_table(output / filename, fields, rows)
        written = read_table(output / filename)
        expected_written = [{name: str(row[name]) for name in fields} for row in rows]
        if written != expected_written:
            raise RuntimeError("Audit CSV failed value roundtrip: " + filename)
        if filename == "text_coverage.csv" and [row["row_locator"] for row in written] != locators:
            raise RuntimeError("Written coverage CSV lost source locator order")
    source_after = pipeline.sha256_bytes(source.read_bytes())
    if source_after != source_before:
        raise RuntimeError("Preserved source changed during audit output")
    output_artifacts = {name: {"sha256": pipeline.sha256_bytes((output / name).read_bytes()),
                              "bytes": (output / name).stat().st_size, "rows": len(rows),
                              "columns": list(fields)}
                        for name, (fields, rows) in tables.items()}
    summary = {
        "artifact_status": "common_data_diagnostics_no_analysis_specific_filtering",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"sha256_before": source_before, "sha256_after": source_after,
                   "unchanged": source_before == source_after, "rows": len(raw_rows),
                   "columns": columns, "bytes": source.stat().st_size,
                   "freshness_note": "Audit execution is not source observation time; no refresh or external verification."},
        "provenance": {"audit_code_sha256": pipeline.sha256_bytes(Path(__file__).read_bytes()),
                       "python_version": sys.version.split()[0],
                       "verified_intake_artifact_sha256": input_artifacts},
        "definitions": {
            "empty_string": "Raw CSV cell is exactly the zero-length string.",
            "whitespace_only": "Raw cell is nonempty and Python str.strip() yields the empty string; Unicode whitespace is included.",
            "exact_literal_markers": list(EXACT_SENTINELS),
            "literal_matching": "Raw full-cell exact match; case and surrounding whitespace are significant. Tokens are never replaced or deemed missing.",
            "availability": "Raw cell is neither empty_string nor whitespace_only. Nonblank markers count as available; this does not prove meaningful text, eligibility or provenance.",
            "overlap_column_order": list(OVERLAP_COLUMNS),
            "segment_labels": "Exact raw supplied Year/Jurisdiction labels; not verified dates, sessions, current populations or representative coverage.",
            "publisher_status_segments": "Exact raw publisher status strings crossed with raw availability; diagnostic evidence only, never independent relevance or an eligibility rule.",
            "logical_csv_record": "Header is record 1, first data record is 2; multiline fields do not change numbering.",
            "review_reason": "Existing intake flag, not a confirmed source error. Each record/reason pair is a separate queue entry; a source record may recur.",
            "example_selection": "Up to three records per reason, lowest logical CSV record first; deterministic examples, not a random sample.",
        },
        "raw_text_coverage": coverage_counts(raw_rows),
        "summary_extract_overlap": overlap,
        "column_blank_counts": {name: {kind: sum(blank_kind(row[name]) == kind for row in raw_rows)
                                       for kind in ("empty_string", "whitespace_only")}
                                for name in columns},
        "nonzero_literal_marker_counts": {name: {token: sum(row[name] == token for row in raw_rows)
                                                 for token in EXACT_SENTINELS if any(row[name] == token for row in raw_rows)}
                                          for name in columns},
        "coverage_by_source_year": segment_coverage(raw_rows, "Year"),
        "coverage_by_source_jurisdiction": segment_coverage(raw_rows, "Jurisdiction"),
        "coverage_by_publisher_status": segment_coverage(raw_rows, "status"),
        "repeated_state_bill_across_supplied_years": repeated_state_bill_across_years(raw_rows, source_before),
        "review_queue": {"record_reason_entries": len(review),
                         "distinct_source_records": len({row["row_locator"] for row in review}),
                         "reason_counts": reason_counts, "examples": select_examples(review),
                         "confirmed_errors": None, "rows_dropped_or_merged": 0},
        "checks": {"source_unchanged": source_before == source_after,
                   "all_source_columns_partitioned": True, "eight_overlap_cells_partition_source": True,
                   "all_coverage_rows_retained_in_source_order": [row["row_locator"] for row in coverage] == locators,
                   "all_output_csv_values_roundtrip_verified": True,
                   "unique_coverage_locators": len(set(locators)),
                   "rows_dropped": 0, "rows_merged": 0, "raw_cells_replaced": 0,
                   "targets_encoded": False, "model_subsets_exported": False,
                   "vectorizers_splits_or_models_fitted": False},
        "output_artifacts": output_artifacts,
        "checksum_scope": "Every audit CSV is hashed; this JSON excludes itself to avoid a circular hash.",
        "limitations": [
            "The audit checks the supplied file; it does not verify bill histories against external sources.",
            "NCSL_Summary, summary and bill_extracts are separate fields. Coverage checks do not establish how their text was created.",
            "Missing-value checks use the listed literal markers; other placeholders may need review.",
            "The audit applies no text eligibility threshold or analysis-specific filtering.",
            "State/year proportions describe this file, not the full population of bills.",
            "Publisher status labels are preserved and are not used to remove rows.",
            "Date flags identify timing differences; a later version is not automatically invalid.",
            "Matching normalized text does not establish that two records represent the same bill.",
            "The audit preserves bill text and does not detect every possible outcome clue.",
        ],
    }
    pipeline.write_json(output / "common_input_audit.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=pipeline.DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=pipeline.DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = run_audit(args.source, args.output)
    print(json.dumps({"source_rows": summary["source"]["rows"],
                      "source_unchanged": summary["source"]["unchanged"],
                      "raw_text_coverage": summary["raw_text_coverage"],
                      "summary_extract_overlap": summary["summary_extract_overlap"],
                      "review_reason_counts": summary["review_queue"]["reason_counts"],
                      "review_records": summary["review_queue"]["distinct_source_records"],
                      "repeated_state_bill_groups": summary["repeated_state_bill_across_supplied_years"]["groups_spanning_multiple_supplied_years"]},
                     indent=2))


if __name__ == "__main__":
    main()
