"""Preserve source records and add cleaned text and ISO dates for notebooks."""

import argparse
from pathlib import Path
import unicodedata

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "data" / "raw" / "Final_Database.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "common_intake" / "common_records.csv"
TEXT_COLUMNS = (
    "Bill_Text",
    "Bill_Title",
    "NCSL_Summary",
    "summary",
    "bill_extracts",
)


def clean_text(value):
    """Normalize Unicode and whitespace without removing words or punctuation."""
    return " ".join(unicodedata.normalize("NFKC", value).split())


def parse_dates(values):
    """Parse nonblank month/day/year dates, leaving blank dates blank."""
    dates = pd.Series("", index=values.index, dtype=str)
    nonblank = values.str.strip().ne("")
    dates.loc[nonblank] = pd.to_datetime(
        values.loc[nonblank].str.strip(), format="%m/%d/%Y", errors="raise"
    ).dt.strftime("%Y-%m-%d")
    return dates


def prepare_data(source=DEFAULT_SOURCE, output=DEFAULT_OUTPUT):
    """Write common records and verify original values and record order."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or (output.exists() and source.samefile(output)):
        raise ValueError("Output must not overwrite the source CSV.")

    # Read every cell as text so blanks and literal markers such as N/A survive.
    original = pd.read_csv(source, dtype=str, keep_default_na=False, skip_blank_lines=False)
    added_columns = ["source_row", *(name + "_clean" for name in TEXT_COLUMNS),
                     "introduction_date_iso", "version_date_iso"]
    if original.columns.intersection(added_columns).size:
        raise ValueError("Source already contains a preparation column.")

    prepared = original.copy()
    # Record positions remain useful when a quoted CSV value spans several lines.
    prepared["source_row"] = range(1, len(original) + 1)
    for name in TEXT_COLUMNS:
        prepared[name + "_clean"] = original[name].map(clean_text)
    prepared["introduction_date_iso"] = parse_dates(original["Introduction_Date"])
    prepared["version_date_iso"] = parse_dates(original["Version_Date"])

    output.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(output, index=False)
    saved = pd.read_csv(output, dtype=str, keep_default_na=False, skip_blank_lines=False)
    pd.testing.assert_index_equal(original.columns, saved.columns[:len(original.columns)])
    pd.testing.assert_frame_equal(original, saved[original.columns])
    pd.testing.assert_series_equal(prepared["source_row"].astype(str), saved["source_row"])
    return prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    prepared = prepare_data(args.source, args.output)
    print(f"Prepared {len(prepared)} rows and {len(prepared.columns)} columns: {args.output}")


if __name__ == "__main__":
    main()
