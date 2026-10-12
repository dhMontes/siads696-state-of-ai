"""Keep human review notes outside the reproducible common-intake outputs.

Run ``init --source ... --audit ... --queue ... --output ...`` once, then
edit only status, note, evidence_reference and reviewed_at in that CSV.
Run ``validate --source ... --audit ... --queue ... --decisions ...`` to
check it. Both commands require the current preserved source and audit.
The log must be outside the directories containing the generated evidence.
Review statuses record follow-up only; they never change analysis inputs.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import re
import sys


QUEUE_COLUMNS = (
    "row_locator", "logical_csv_row", "review_reason", "review_status",
    "jurisdiction_raw", "bill_number_raw", "source_year_raw",
    "introduction_date_raw", "version_date_raw", "introduction_date_iso",
    "version_date_iso", "normalized_text_group_id", "normalized_text_group_size",
)
REVIEW_REASONS = (
    "version_before_introduction", "version_after_introduction",
    "bill_title_missing", "exact_normalized_text_duplicate_flag",
)
STATUSES = (
    "unreviewed", "reviewed_no_change", "needs_source_check", "needs_team_decision",
)
DECISION_COLUMNS = (
    "source_sha256", "queue_sha256", "row_locator", "review_reason",
    "status", "note", "evidence_reference", "reviewed_at",
)


@dataclass(frozen=True)
class VerifiedQueue:
    source_sha256: str
    queue_sha256: str
    keys: tuple[tuple[str, str, str], ...]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(label + " must be a nonnegative integer")
    return value


def _read_csv(data: bytes, fields: tuple[str, ...], label: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
    if reader.fieldnames != list(fields):
        raise ValueError(label + " columns do not match the required schema")
    rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(label + " contains a malformed CSV record")
    return rows


def load_verified_queue(source: Path, audit: Path, queue: Path) -> VerifiedQueue:
    """Check current bytes and the audit's exact source/queue identity contract."""
    try:
        saved = json.loads(audit.read_text(encoding="utf-8"))
        source_meta = saved["source"]
        artifact = saved["output_artifacts"]["review_records.csv"]
        queue_meta = saved["review_queue"]
        source_sha = source_meta["sha256_before"]
        if (source_meta["sha256_after"] != source_sha or source_meta["unchanged"] is not True
                or saved["checks"]["source_unchanged"] is not True):
            raise ValueError("Audit does not establish unchanged source bytes")
        source_rows = _count(source_meta["rows"], "Audit source rows")
        queue_sha = artifact["sha256"]
        queue_rows = _count(artifact["rows"], "Audit queue rows")
        entries = _count(queue_meta["record_reason_entries"], "Audit review entries")
        records = _count(queue_meta["distinct_source_records"], "Audit review records")
        reasons = queue_meta["reason_counts"]
        if artifact["columns"] != list(QUEUE_COLUMNS):
            raise ValueError("Audit queue columns do not match the required schema")
        if not isinstance(reasons, dict) or set(reasons) != set(REVIEW_REASONS):
            raise ValueError("Audit review reasons do not match the required schema")
        expected_reasons = {name: _count(reasons[name], "Audit reason count")
                            for name in REVIEW_REASONS}
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Audit is missing required source or queue metadata") from error

    queue_data = queue.read_bytes()
    # Comparing the actual digest also rejects missing or malformed saved hashes.
    if hashlib.sha256(queue_data).hexdigest() != queue_sha:
        raise ValueError("Queue checksum does not match the audit")
    rows = _read_csv(queue_data, QUEUE_COLUMNS, "Queue")
    keys = []
    for entry, row in enumerate(rows, start=1):
        logical_row = row["logical_csv_row"]
        if re.fullmatch(r"[1-9][0-9]*", logical_row) is None:
            raise ValueError(f"Queue has an invalid logical source row at entry {entry}")
        if not 2 <= int(logical_row) <= source_rows + 1:
            raise ValueError(f"Queue source row is outside the source at entry {entry}")
        if row["row_locator"] != f"sha256:{source_sha}#csv-record={logical_row}":
            raise ValueError(f"Queue locator does not match the source at entry {entry}")
        if row["review_reason"] not in REVIEW_REASONS:
            raise ValueError(f"Queue has an unknown review reason at entry {entry}")
        if row["review_status"] != "unreviewed_retained":
            raise ValueError(f"Queue has a modified generated review status at entry {entry}")
        keys.append((source_sha, row["row_locator"], row["review_reason"]))
    if len(set(keys)) != len(keys):
        raise ValueError("Queue contains duplicate record/reason keys")
    actual_reasons = Counter(row["review_reason"] for row in rows)
    if (len(rows) != queue_rows or len(rows) != entries
            or len({row["row_locator"] for row in rows}) != records
            or any(actual_reasons[name] != expected_reasons[name] for name in REVIEW_REASONS)):
        raise ValueError("Queue counts do not match the audit")
    if _hash_file(source) != source_sha:
        raise ValueError("Source checksum does not match the audit")
    return VerifiedQueue(source_sha, queue_sha, tuple(keys))


def _check_log_location(path: Path, audit: Path, queue: Path) -> None:
    resolved = path.resolve()
    if any(resolved.is_relative_to(item.parent.resolve()) for item in (audit, queue)):
        raise ValueError("Review log must be outside generated evidence directories")


def _summary(evidence: VerifiedQueue, rows: list[dict[str, str]]) -> dict:
    counts = Counter(row["status"] for row in rows)
    return {"record_reason_entries": len(evidence.keys),
            "distinct_source_records": len({key[1] for key in evidence.keys}),
            "status_counts": {status: counts[status] for status in STATUSES}}


def initialize_review_log(source: Path, audit: Path, queue: Path, output: Path) -> dict:
    """Create a complete unreviewed log; refuse every existing output path."""
    _check_log_location(output, audit, queue)
    evidence = load_verified_queue(source, audit, queue)
    rows = [{"source_sha256": key[0], "queue_sha256": evidence.queue_sha256,
             "row_locator": key[1], "review_reason": key[2], "status": "unreviewed",
             "note": "", "evidence_reference": "", "reviewed_at": ""}
            for key in evidence.keys]
    # Exclusive creation prevents replacing any existing human notes.
    try:
        with output.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=DECISION_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    except FileExistsError as error:
        raise ValueError("Review log already exists; initialization refuses overwrite") from error
    return _summary(evidence, rows)


def validate_review_log(source: Path, audit: Path, queue: Path, decisions: Path) -> dict:
    """Require exact current-queue coverage and validate only the note schema."""
    _check_log_location(decisions, audit, queue)
    evidence = load_verified_queue(source, audit, queue)
    rows = _read_csv(decisions.read_bytes(), DECISION_COLUMNS, "Review log")
    expected = set(evidence.keys)
    seen = set()
    for entry, row in enumerate(rows, start=1):
        if row["source_sha256"] != evidence.source_sha256:
            raise ValueError(f"Review log has a stale source checksum at entry {entry}")
        if row["queue_sha256"] != evidence.queue_sha256:
            raise ValueError(f"Review log has a stale queue checksum at entry {entry}")
        key = (row["source_sha256"], row["row_locator"], row["review_reason"])
        if key in seen:
            raise ValueError(f"Review log has a duplicate key at entry {entry}")
        if key not in expected:
            raise ValueError(f"Review log has an unknown key at entry {entry}")
        seen.add(key)
        if row["status"] not in STATUSES:
            raise ValueError(f"Review log has an invalid status at entry {entry}")
        reviewed_at = row["reviewed_at"]
        if row["status"] == "unreviewed":
            if reviewed_at:
                raise ValueError(f"Unreviewed entry has a review date at entry {entry}")
        else:
            try:
                if date.fromisoformat(reviewed_at).isoformat() != reviewed_at:
                    raise ValueError("noncanonical date")
            except ValueError as error:
                raise ValueError(f"Reviewed entry needs an ISO YYYY-MM-DD date at entry {entry}") from error
    if seen != expected:
        raise ValueError(f"Review log is missing {len(expected - seen)} current queue entries")
    return _summary(evidence, rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "validate"):
        command = commands.add_parser(name)
        command.add_argument("--source", type=Path, required=True)
        command.add_argument("--audit", type=Path, required=True)
        command.add_argument("--queue", type=Path, required=True)
        command.add_argument("--output" if name == "init" else "--decisions",
                             type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            summary = initialize_review_log(args.source, args.audit, args.queue, args.output)
        else:
            summary = validate_review_log(args.source, args.audit, args.queue, args.decisions)
    except (ValueError, OSError, UnicodeError, csv.Error) as error:
        print("Review log check failed: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
