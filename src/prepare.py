"""Prepare shared bill data with cleaned text, dates and sponsor features."""

import argparse
import ast
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


def parse_sponsor_parties(value):
    """Read sponsor parties from their stored list representation."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, SyntaxError):
            return []
    return []


def count_parties(parties):
    """Count Democratic, Republican, other and unknown sponsor entries."""
    if not isinstance(parties, list):
        return [0, 0, 0, 0]

    parties = [
        str(p).strip().upper() if p is not None else "UNKNOWN"
        for p in parties
    ]

    d_count = parties.count("D")
    r_count = parties.count("R")
    unknown_count = sum(
        p in ["UNKNOWN", "U", "", "NONE", "NAN"]
        for p in parties
    )
    other_count = len(parties) - d_count - r_count - unknown_count

    return [d_count, r_count, other_count, unknown_count]


def prepare_data(source=DEFAULT_SOURCE, output=DEFAULT_OUTPUT):
    """Remove repeated cleaned bill text, add shared features and save the table."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or (output.exists() and source.samefile(output)):
        raise ValueError("Output must not overwrite the source CSV.")

    # Read every cell as text so blanks and literal markers such as N/A survive.
    original = pd.read_csv(source, dtype=str, keep_default_na=False, skip_blank_lines=False)
    added_columns = (
        ["source_row"]
        + [name + "_clean" for name in TEXT_COLUMNS]
        + ["introduction_date_iso", "version_date_iso"]
    )
    if original.columns.intersection(added_columns).size:
        raise ValueError("Source already contains a preparation column.")

    prepared = original.copy()
    # Keep the original CSV record number for joins after filtering.
    prepared["source_row"] = range(1, len(original) + 1)
    for name in TEXT_COLUMNS:
        prepared[name + "_clean"] = original[name].map(clean_text)
    prepared["introduction_date_iso"] = parse_dates(original["Introduction_Date"])
    prepared["version_date_iso"] = parse_dates(original["Version_Date"])

    # Keep the last source row for each repeated cleaned bill text.
    prepared = prepared.drop_duplicates(subset=["Bill_Text_clean"], keep="last")

    prepared["Sponsor_Party"] = prepared["Sponsor_Party"].apply(parse_sponsor_parties)

    # Count sponsors by party.
    columns = ["D_Count", "R_Count", "Other_Count", "Unknown_Count"]

    prepared[columns] = pd.DataFrame(
        prepared["Sponsor_Party"].apply(count_parties).tolist(),
        index=prepared.index,
        columns=columns
    )

    # Derive sponsor totals, bipartisan support and party ratios.
    prepared["Total_Sponsors"] = (
        prepared["D_Count"]
        + prepared["R_Count"]
        + prepared["Other_Count"]
        + prepared["Unknown_Count"]
    )

    prepared["Bipartisan_Support"] = (
        (prepared["D_Count"] > 0)
        & (prepared["R_Count"] > 0)
    ).astype(int)

    prepared["Democrat_Sponsor_Ratio"] = (
        prepared["D_Count"]
        / prepared["Total_Sponsors"].replace(0, float("nan"))
    )

    prepared["Republican_Sponsor_Ratio"] = (
        prepared["R_Count"]
        / prepared["Total_Sponsors"].replace(0, float("nan"))
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(output, index=False)
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
