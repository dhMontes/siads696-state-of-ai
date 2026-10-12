"""Prepare source-linked text, dates and review flags from the State AI Policy CSV.

All records and original values are retained. Model-specific filtering and
feature selection happen after this shared preparation step.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import unicodedata

EXPECTED_SHA256 = "188aba4f4e50c6d0acb3532d143b9a81d9cccdf7c0729ba7ded6410399eff232"
EXPECTED_ROWS = 2571
INPUT_COLUMNS = (
    "Bill_Number", "measure_code", "Bill_Title", "Jurisdiction", "NCSL_Summary",
    "NCSL_Category", "Bill_URL", "Version_Date", "Year", "Bill_Status",
    "State_Political_Control", "Regional_Cluster_ID", "Bill_Text", "Sponsor",
    "Sponsor_Party", "Introduction_Date", "bill_extracts", "summary",
    "analyst_results", "retry_attempts", "status", "product_safety_score",
    "ai_inputs_ip_score", "market_structure_score", "specific_use_score",
    "societal_risks_score", "institutional_processes_score",
    "ai_advancement_score", "Bill_Status_Grouped",
)
HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE.parent / "data/raw/Final_Database.csv"
DEFAULT_OUTPUT = HERE.parent / "data/processed/common_intake"
JOIN_COLUMN = "row_locator"
EXCLUDED_INPUTS = tuple(name for name in INPUT_COLUMNS if name not in {"Bill_Text", "Bill_Title"})

# Source roles describe possible use, not eligibility or verified field lineage.
SOURCE_ROLES = {
    "candidate": ("Bill_Text", "Bill_Title", "measure_code", "Jurisdiction",
                  "State_Political_Control", "Regional_Cluster_ID", "Sponsor",
                  "Sponsor_Party", "Introduction_Date"),
    "evidence": ("Bill_Number", "Bill_URL", "Version_Date", "Year",
                 "NCSL_Summary", "NCSL_Category"),
    "outcome": ("Bill_Status", "Bill_Status_Grouped"),
    "publisher_derived": ("bill_extracts", "summary", "analyst_results",
                          "retry_attempts", "status", "product_safety_score",
                          "ai_inputs_ip_score", "market_structure_score",
                          "specific_use_score", "societal_risks_score",
                          "institutional_processes_score", "ai_advancement_score"),
}


def source_role(name: str) -> str:
    matches = [role for role, names in SOURCE_ROLES.items() if name in names]
    if len(matches) != 1:
        raise ValueError("Source field must have exactly one role: " + name)
    return matches[0]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def text_hash(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def clean_text(value: str) -> str:
    """NFC Unicode composition and whitespace collapse; preserve meaning tokens.

    Do not lowercase, remove punctuation/numbers/negations, replace compatibility
    characters, or remove administrative headers. Raw text is retained separately.
    """
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def parse_date(value: str) -> dict:
    """Accept only explicit US month/day/year or ISO dates; never guess locale."""
    cleaned = clean_text(value)
    if not cleaned:
        return {"iso": "", "missing": True, "parse_error": False, "format": "missing"}
    try:
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", cleaned):
            month, day, year = map(int, cleaned.split("/"))
            parsed = date(year, month, day)
            format_name = "explicit_month_day_year"
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
            parsed = date.fromisoformat(cleaned)
            format_name = "iso_year_month_day"
        else:
            raise ValueError("unsupported date representation")
    except ValueError:
        return {"iso": "", "missing": False, "parse_error": True, "format": "unparsed"}
    return {"iso": parsed.isoformat(), "missing": False, "parse_error": False, "format": format_name}


def parse_string_array(value: str) -> dict:
    """Conservative JSON-array parse: no literal_eval, scalar coercion, or repair."""
    if not clean_text(value):
        return {"values": None, "state": "missing", "missing_items": 0, "invalid_items": 0}
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return {"values": None, "state": "malformed_json", "missing_items": 0, "invalid_items": 0}
    if not isinstance(parsed, list):
        return {"values": None, "state": "not_array", "missing_items": 0, "invalid_items": 0}
    invalid = sum(item is not None and not isinstance(item, str) for item in parsed)
    missing = sum(item is None or (isinstance(item, str) and not clean_text(item)) for item in parsed)
    if invalid:
        return {"values": None, "state": "invalid_item_type", "missing_items": missing, "invalid_items": invalid}
    return {"values": parsed, "state": "parsed", "missing_items": missing, "invalid_items": 0}


def row_locator(source_checksum: str, logical_csv_row: int) -> str:
    # The header is logical CSV record 1; multiline fields do not alter numbering.
    return f"sha256:{source_checksum}#csv-record={logical_csv_row}"


def party_indicator_name(code: str) -> str:
    # Hex escape prevents collisions for observed codes with punctuation/non-ASCII.
    encoded = "".join(char if char.isascii() and char.isalnum() else f"_{ord(char):x}_" for char in code)
    return f"observed_party_code_{encoded}_present"


def load_source(source: Path) -> tuple[list[str], list[dict[str, str]]]:
    csv.field_size_limit(100_000_000)
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        if tuple(columns) != INPUT_COLUMNS:
            raise ValueError("Source schema differs from the preserved 29-column contract")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("Source contains records with fewer or more fields than the header")
    return columns, rows


def write_csv(path: Path, rows: list[dict]) -> list[str]:
    if not rows:
        raise ValueError("This intake requires at least one source row")
    columns = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return columns


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def duplicate_groups(values: list[str], prefix: str) -> tuple[list[dict], dict]:
    grouped = defaultdict(list)
    for index, value in enumerate(values):
        if value:  # Missing values do not establish a shared identity/text.
            grouped[value].append(index)
    labels = [{"group_id": "", "group_size": 1, "duplicate_flag": False} for _ in values]
    duplicates = [indices for indices in grouped.values() if len(indices) > 1]
    for indices in duplicates:
        group_id = prefix + ":" + text_hash(values[indices[0]])
        for index in indices:
            labels[index] = {"group_id": group_id, "group_size": len(indices), "duplicate_flag": True}
    counts = {"groups": len(duplicates), "rows_in_groups": sum(map(len, duplicates)),
              "excess_copies": sum(len(indices) - 1 for indices in duplicates), "rows_dropped": 0}
    return labels, counts


def run_pipeline(source: Path = DEFAULT_SOURCE, output: Path = DEFAULT_OUTPUT,
                 expected_sha256: str | None = EXPECTED_SHA256,
                 expected_rows: int | None = EXPECTED_ROWS) -> dict:
    """Validate the source, build preparation tables and save a quality summary."""
    source = Path(source).resolve()
    output = Path(output).resolve()
    if source.parent == output or output == source:
        raise ValueError("Output must be separate from the preserved input")
    checksum_before = sha256_bytes(source.read_bytes())
    if expected_sha256 is not None and checksum_before != expected_sha256:
        raise ValueError("Source checksum differs from the preserved v4 input")
    columns, raw_rows = load_source(source)
    if expected_rows is not None and len(raw_rows) != expected_rows:
        raise ValueError("Source row count differs from the preserved v4 input")
    output.mkdir(parents=True, exist_ok=True)

    raw_evidence = []
    base_inputs = []
    predictors = []
    flags = []
    crosswalk = []
    dates = []
    party_codes = set()
    parsed_parties = []
    for raw in raw_rows:
        party = parse_string_array(raw["Sponsor_Party"])
        parsed_parties.append(party)
        if party["values"] is not None:
            for code in party["values"]:
                if isinstance(code, str) and clean_text(code):
                    party_codes.add(clean_text(code))
    observed_party_codes = sorted(party_codes)
    status_prefix_counts = Counter()
    publisher_status_counts = Counter()

    # A shared locator keeps each derived row tied to its original CSV record.
    for data_index, (raw, parties) in enumerate(zip(raw_rows, parsed_parties), start=2):
        locator = row_locator(checksum_before, data_index)
        text = clean_text(raw["Bill_Text"])
        title = clean_text(raw["Bill_Title"])
        introduction = parse_date(raw["Introduction_Date"])
        version = parse_date(raw["Version_Date"])
        metadata = {name: clean_text(raw[name]) for name in (
            "Jurisdiction", "Bill_Number", "measure_code", "Year",
            "State_Political_Control", "Regional_Cluster_ID")}
        sponsors = parse_string_array(raw["Sponsor"])
        comparable_dates = bool(introduction["iso"] and version["iso"])
        year_valid = bool(re.fullmatch(r"\d{4}", metadata["Year"]))
        identity_parts = [metadata[name] for name in ("Jurisdiction", "Bill_Number", "Year")]
        candidate_key = json_text(identity_parts) if all(identity_parts) else ""
        status_prefix = clean_text(raw["Bill_Status"]).split(" - ", 1)[0]
        publisher_status = clean_text(raw["status"])
        status_prefix_counts[status_prefix] += 1
        publisher_status_counts[publisher_status] += 1

        raw_evidence.append({
            JOIN_COLUMN: locator,
            "source_sha256": checksum_before,
            "logical_csv_row": data_index,
            **raw,
        })
        base = {
            JOIN_COLUMN: locator,
            "bill_text_normalized": text,
            "bill_title_normalized": title,
            "jurisdiction_normalized": metadata["Jurisdiction"],
            "measure_code_normalized": metadata["measure_code"],
            "state_political_control_normalized": metadata["State_Political_Control"],
            "regional_cluster_normalized": metadata["Regional_Cluster_ID"],
            "introduction_date_iso": introduction["iso"],
            "introduction_year_parsed": introduction["iso"][:4],
        }
        base_inputs.append(base)
        predictors.append({name: base[name] for name in (JOIN_COLUMN, "bill_text_normalized", "bill_title_normalized")})

        # A blank alignment result means one of the source arrays could not be read.
        aligned = ""
        if sponsors["values"] is not None and parties["values"] is not None:
            aligned = len(sponsors["values"]) == len(parties["values"])

        observed = None
        if parties["values"] is not None:
            observed = sorted({
                clean_text(code)
                for code in parties["values"]
                if isinstance(code, str) and clean_text(code)
            })
        row_flags = {
            JOIN_COLUMN: locator,
            "raw_row_sha256": text_hash(json_text([raw[name] for name in columns])),
            "bill_text_raw_sha256": text_hash(raw["Bill_Text"]),
            "bill_text_normalized_sha256": text_hash(text),
            "bill_text_raw_characters": len(raw["Bill_Text"]),
            "bill_text_normalized_characters": len(text),
            "bill_text_normalization_changed": text != raw["Bill_Text"],
            "bill_text_missing": not bool(text),
            "bill_title_missing": not bool(title),
            "introduction_date_missing": introduction["missing"],
            "introduction_date_parse_error": introduction["parse_error"],
            "introduction_date_parse_format": introduction["format"],
            "version_date_missing": version["missing"],
            "version_date_parse_error": version["parse_error"],
            "version_date_parse_format": version["format"],
            "date_comparison_available": comparable_dates,
            "version_after_introduction": version["iso"] > introduction["iso"] if comparable_dates else "",
            "version_before_introduction": version["iso"] < introduction["iso"] if comparable_dates else "",
            "version_equals_introduction": version["iso"] == introduction["iso"] if comparable_dates else "",
            "source_year_missing": not bool(metadata["Year"]),
            "source_year_invalid": bool(metadata["Year"]) and not year_valid,
            "source_year_differs_version_year": metadata["Year"] != version["iso"][:4] if year_valid and version["iso"] else "",
            "source_year_differs_introduction_year": metadata["Year"] != introduction["iso"][:4] if year_valid and introduction["iso"] else "",
            "sponsor_parse_state": sponsors["state"],
            "party_parse_state": parties["state"],
            "sponsor_array_json": json_text(sponsors["values"]) if sponsors["values"] is not None else "",
            "party_array_json": json_text(parties["values"]) if parties["values"] is not None else "",
            "sponsor_count": len(sponsors["values"]) if sponsors["values"] is not None else "",
            "party_item_count": len(parties["values"]) if parties["values"] is not None else "",
            "sponsor_missing_items": sponsors["missing_items"],
            "party_missing_items": parties["missing_items"],
            "sponsor_invalid_items": sponsors["invalid_items"],
            "party_invalid_items": parties["invalid_items"],
            "sponsor_party_lengths_equal": aligned,
            "sponsor_party_alignment_unavailable": aligned == "",
            "sponsor_party_length_mismatch": aligned is False,
            "observed_party_codes_json": json_text(observed) if observed is not None else "",
            "party_semantics_verified": False,
            "primary_sponsor_verified": False,
            "source_status_prefix": status_prefix,
            "publisher_classification_status_normalized": publisher_status,
            "publisher_filtered_not_ai": publisher_status == "filtered_not_ai",
            "verified_session_available": False,
            "verified_terminal_outcome_available": False,
            "text_version_timing_verified": False,
            "source_header_or_status_leakage_review_required": True,
        }
        for name in metadata:
            row_flags[name.lower() + "_missing"] = not bool(metadata[name])
        for code in observed_party_codes:
            row_flags[party_indicator_name(code)] = code in observed if observed is not None else ""
        flags.append(row_flags)

        crosswalk.append({
            JOIN_COLUMN: locator,
            "jurisdiction_raw": raw["Jurisdiction"],
            "bill_number_raw": raw["Bill_Number"],
            "source_year_raw": raw["Year"],
            "jurisdiction_normalized": metadata["Jurisdiction"],
            "bill_number_normalized": metadata["Bill_Number"],
            "source_year_normalized": metadata["Year"],
            "candidate_state_bill_year_key": candidate_key,
            "candidate_key_missing": not bool(candidate_key),
            "candidate_key_is_verified_session_key": False,
            "matched_provider_id": "",
            "verified_session": "",
            "verified_state_session_bill_key": "",
            "identity_match_status": "unresolved",
            "match_evidence_url": "",
            "match_retrieved_at": "",
            "related_family_id": "",
            "related_family_status": "unreviewed",
            "duplicate_disposition": "retained_unreviewed",
            "source_bill_url_raw": raw["Bill_URL"],
        })
        dates.append({
            JOIN_COLUMN: locator,
            "introduction_date_raw": raw["Introduction_Date"],
            "version_date_raw": raw["Version_Date"],
            "source_year_raw": raw["Year"],
            "introduction_date_iso": introduction["iso"],
            "version_date_iso": version["iso"],
            "verified_filed_date_iso": "",
            "verified_introduction_date_iso": "",
            "verified_text_version_date_iso": "",
            "verified_session": "",
            "verified_action_date_iso": "",
            "correction_source_url": "",
            "correction_retrieved_at": "",
            "correction_status": "unverified",
            "source_bill_url_raw": raw["Bill_URL"],
            "source_record_url": "https://zenodo.org/records/20781731",
            "source_retrieval_date_reported": "2026-09-03",
            "source_v4_capture_date_recorded": "2026-09-14",
            "date_definition_agreement": "unresolved",
        })

    # Equal labels or text flag records for review; every row is retained.
    duplicate_summary = {}
    duplicate_specs = {
        "exact_raw_row": [row["raw_row_sha256"] for row in flags],
        "candidate_key": [row["candidate_state_bill_year_key"] for row in crosswalk],
        "exact_raw_text": [row["bill_text_raw_sha256"] if not row["bill_text_missing"] else "" for row in flags],
        "exact_normalized_text": [row["bill_text_normalized_sha256"] if not row["bill_text_missing"] else "" for row in flags],
    }
    for duplicate_type, values in duplicate_specs.items():
        groups, counts = duplicate_groups(values, duplicate_type)
        duplicate_summary[duplicate_type] = counts
        for row, group in zip(flags, groups):
            for name, value in group.items():
                row[duplicate_type + "_" + name] = value
        if duplicate_type == "candidate_key":
            for row, group in zip(crosswalk, groups):
                for name, value in group.items():
                    row[duplicate_type + "_" + name] = value

    tables = {
        "raw_evidence.csv": raw_evidence,
        "base_inputs.csv": base_inputs,
        "candidate_predictors.csv": predictors,
        "quality_flags.csv": flags,
        "bill_identity_crosswalk.csv": crosswalk,
        "date_correction_record.csv": dates,
    }
    schemas = {filename: write_csv(output / filename, rows) for filename, rows in tables.items()}
    with (output / "raw_evidence.csv").open(encoding="utf-8", newline="") as stream:
        raw_roundtrip = list(csv.DictReader(stream))
    original_values = [{name: row[name] for name in columns} for row in raw_roundtrip]
    raw_values_preserved = original_values == raw_rows
    if not raw_values_preserved:
        raise RuntimeError("Written raw evidence failed original-value roundtrip verification")
    checksum_after = sha256_bytes(source.read_bytes())
    if checksum_after != checksum_before:
        raise RuntimeError("Preserved source changed during intake")
    contract = make_column_contract(columns, schemas, observed_party_codes)
    write_json(output / "column_contract.json", contract)
    artifacts = {}
    for filename in (*tables, "column_contract.json"):
        artifact_path = output / filename
        artifacts[filename] = {"sha256": sha256_bytes(artifact_path.read_bytes()), "bytes": artifact_path.stat().st_size}
        if filename in tables:
            artifacts[filename].update({"rows": len(tables[filename]), "columns": len(schemas[filename])})
    boolean_checks = {name: sum(row[name] is True for row in flags) for name in flags[0]
                      if any(isinstance(row[name], bool) for row in flags)}
    summary = {
        "artifact_status": "shared_preparation_all_source_records_retained",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"path_relative_to_preparation": Path(os.path.relpath(source.resolve(), HERE.resolve())).as_posix(),
                   "sha256_before": checksum_before, "sha256_after": checksum_after,
                   "unchanged": checksum_before == checksum_after, "bytes": source.stat().st_size,
                   "rows": len(raw_rows), "columns": columns,
                   "source_record_url": "https://zenodo.org/records/20781731",
                   "source_retrieval_date_reported": "2026-09-03", "source_v4_capture_date_recorded": "2026-09-14",
                   "freshness_note": "Local execution time is not source observation time. No source refresh or external verification occurred."},
        "provenance": {"pipeline_sha256": sha256_bytes(Path(__file__).read_bytes()),
                       "python_version": sys.version.split()[0],
                       "logical_csv_row_definition": "Header is record 1; first data record is 2. Embedded newlines do not advance the record count.",
                       "raw_value_preservation": "CSV string values preserved exactly; CSV quoting/serialization bytes may differ. Original source bytes stay unchanged.",
                       "normalization": "Unicode NFC, collapse Unicode whitespace to single ASCII space, trim; preserve case/punctuation/numbers/negations and administrative headers.",
                       "date_parsing": "Explicit month/day/year and ISO year-month-day only; successful parse is not historical verification."},
        "checks": {"all_rows_retained": all(len(rows) == len(raw_rows) for rows in tables.values()),
                   "original_values_roundtrip_preserved": raw_values_preserved,
                   "row_locators_unique": len({row[JOIN_COLUMN] for row in flags}) == len(raw_rows),
                   "raw_input_sha256_matches_expected": expected_sha256 is None or checksum_before == expected_sha256,
                   "rows_dropped": 0, "rows_merged": 0, "target_labels_encoded": False,
                   "splits_created": False, "learned_transformations_fitted": False,
                   "external_corrections_applied": 0, "verified_session_keys": 0,
                   "verified_terminal_outcomes": 0, "near_duplicate_or_family_review_performed": False},
        "boolean_flag_counts": boolean_checks,
        "missing_raw_fields": {name: sum(not clean_text(row[name]) for row in raw_rows) for name in columns},
        "date_parse_counts": {"introduction": dict(Counter(row["introduction_date_parse_format"] for row in flags)),
                              "version": dict(Counter(row["version_date_parse_format"] for row in flags))},
        "date_ranges": {"introduction": date_range(dates, "introduction_date_iso"), "version": date_range(dates, "version_date_iso")},
        "sponsor_parse_counts": dict(Counter(row["sponsor_parse_state"] for row in flags)),
        "party_parse_counts": dict(Counter(row["party_parse_state"] for row in flags)),
        "observed_party_codes": observed_party_codes,
        "party_code_indicator_mapping": {code: party_indicator_name(code) for code in observed_party_codes},
        "source_status_prefix_counts_evidence_only": dict(status_prefix_counts),
        "publisher_classification_status_counts_evidence_only": dict(publisher_status_counts),
        "duplicates": duplicate_summary,
        "output_artifacts": artifacts,
        "checksum_scope": "Every emitted CSV and column_contract.json; quality_summary.json excludes itself to avoid a circular hash. Notebook is separately executed and validated.",
        "limitations": [
            "The script does not verify bill histories against external sources.",
            "State/bill/year is a lookup key, not a verified legislative session identifier.",
            "Recorded statuses are preserved; pending bills are not encoded as failures.",
            "Sponsor-party arrays are parsed without assigning code meanings or primary-sponsor order.",
            "Bill text and titles retain headers, identifiers and possible outcome clues.",
            "No rows are excluded or merged, and no targets, splits or models are created.",
        ],
    }
    write_json(output / "quality_summary.json", summary)
    return summary


def date_range(rows: list[dict], column: str) -> dict:
    values = [row[column] for row in rows if row[column]]
    return {"minimum": min(values) if values else "", "maximum": max(values) if values else "", "parsed_rows": len(values)}


def make_column_contract(input_columns: list[str], schemas: dict, party_codes: list[str]) -> dict:
    descriptions = {
        "row_locator": "Join/provenance only; immutable source SHA256 plus logical CSV record, never a model feature.",
        "bill_text_normalized": "Candidate text after NFC/whitespace only; still contains possible source headers/outcome clues. Leakage review required before modeling.",
        "bill_title_normalized": "Candidate source title after NFC/whitespace only; semantic accuracy and leakage require review.",
        "jurisdiction_normalized": "Source jurisdiction label; predictor use requires agreement on meaning and timing.",
        "measure_code_normalized": "Source measure code; no resolution or eligibility mapping applied.",
        "state_political_control_normalized": "Observed source control code; meaning and historical availability unverified.",
        "regional_cluster_normalized": "Source regional label; derivation and feature use require agreement.",
        "introduction_date_iso": "Parsed source introduction date; not a verified official filed date or approved cohort date.",
        "introduction_year_parsed": "Year extracted from parsed source introduction date; not session identity.",
    }
    original_fields = {}
    for name in input_columns:
        original_fields[name] = {"role": "raw", "source_role": source_role(name), "retained_in": "raw_evidence.csv", "raw_values_changed": False,
            "candidate_export_eligible": name in {"Bill_Text", "Bill_Title"},
            "intended_use": "candidate text subject to leakage review" if name in {"Bill_Text", "Bill_Title"} else "evidence/provenance or metadata needing agreement; excluded from candidate_predictors.csv"}
    output_fields = {}
    for filename, columns in schemas.items():
        output_fields[filename] = {}
        for name in columns:
            if filename == "raw_evidence.csv" and name in input_columns:
                role = "raw"
            elif name == "row_locator":
                role = "evidence"
            elif filename in {"base_inputs.csv", "candidate_predictors.csv"} and name in {"bill_text_normalized", "bill_title_normalized"}:
                role = "candidate_predictor"
            elif filename == "base_inputs.csv":
                role = "needs_agreement"
            elif name.endswith("_raw"):
                role = "raw"
            else:
                role = "evidence"
            output_fields[filename][name] = {"role": role, "use_in_model_now": False,
                "description": descriptions.get(name, "Source provenance or diagnostic evidence only; never silently promoted to model input.")}
            if filename == "raw_evidence.csv" and name in input_columns:
                output_fields[filename][name]["source_role"] = source_role(name)
    return {"contract_version": 1, "roles": ["raw", "evidence", "candidate_predictor", "needs_agreement"],
            "status": "shared preparation; no model inputs or targets selected",
            "input_columns": original_fields, "output_columns": output_fields,
            "candidate_predictor_export": {"file": "candidate_predictors.csv", "join_only": ["row_locator"],
                "candidate_features": ["bill_text_normalized", "bill_title_normalized"],
                "model_ready": False, "excluded_source_columns": list(EXCLUDED_INPUTS)},
            "observed_party_code_semantics": {code: {"indicator": party_indicator_name(code), "semantic_mapping": "unverified", "role": "evidence"} for code in party_codes},
            "boundary": "No target labels, split assignments, eligibility filters, semantic party mapping, verified sessions or model fitting."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = run_pipeline(args.source, args.output)
    print(json.dumps({"source_rows": summary["source"]["rows"], "source_unchanged": summary["source"]["unchanged"],
                      "output": str(args.output.resolve()), "checks": summary["checks"],
                      "chronology": {name: summary["boolean_flag_counts"][name] for name in (
                          "version_after_introduction", "version_before_introduction", "source_year_differs_version_year")},
                      "duplicates": summary["duplicates"]}, indent=2))


if __name__ == "__main__":
    main()
