"""Prepare and validate all common intake artifacts with one command.
"""

import argparse
import json
from pathlib import Path

import audit_common_inputs
import common_records
import pipeline
import validate_outputs


def prepare(source=pipeline.DEFAULT_SOURCE, output=pipeline.DEFAULT_OUTPUT,
            expected_sha256=pipeline.EXPECTED_SHA256, expected_rows=pipeline.EXPECTED_ROWS):
    """Run intake, audit, the common-table join and final validation in order."""
    pipeline.run_pipeline(source, output, expected_sha256, expected_rows)
    audit_common_inputs.run_audit(source, output, expected_sha256, expected_rows)
    common_records.build_common_records(source, output)
    return validate_outputs.validate(source, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=pipeline.DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=pipeline.DEFAULT_OUTPUT)
    args = parser.parse_args()
    receipt = prepare(args.source, args.output)
    print(json.dumps({"source_rows": receipt["source_rows"], "source_unchanged": receipt["source_unchanged"],
                      "validated_artifacts": len(receipt["artifact_sha256"]), "checks": receipt["checks"]}, indent=2))


if __name__ == "__main__":
    main()
