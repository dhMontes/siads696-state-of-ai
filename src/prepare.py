"""Preserve source records and add cleaned text and ISO dates for notebooks."""

import argparse
from pathlib import Path
import unicodedata
import ast

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
SPONSOR_FEATURES = (
    "D_Count", "R_Count", "Other_Count", "Unknown_Count", "Total_Sponsors",
    "Bipartisan_Support", "Democrat_Sponsor_Ratio", "Republican_Sponsor_Ratio",
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

# Make sure the Sponsor_Party column is a list, even if it is stored as a string representation of a list
def parse_sponsor_parties(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, SyntaxError):
            return []
    return []

# Count the number of Democratic, Republican, Other, and Unknown parties in a list of parties
def count_parties(parties):
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
    """Write common records and verify original values and record order."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or (output.exists() and source.samefile(output)):
        raise ValueError("Output must not overwrite the source CSV.")

    # Read every cell as text so blanks and literal markers such as N/A survive.
    original = pd.read_csv(source, dtype=str, keep_default_na=False, skip_blank_lines=False)
    added_columns = ["source_row", *(name + "_clean" for name in TEXT_COLUMNS),
                     "introduction_date_iso", "version_date_iso", *SPONSOR_FEATURES]
    if original.columns.intersection(added_columns).size:
        raise ValueError("Source already contains a preparation column.")

    prepared = original.copy()
    # Record positions remain useful when a quoted CSV value spans several lines.
    prepared["source_row"] = range(1, len(original) + 1)
    for name in TEXT_COLUMNS:
        prepared[name + "_clean"] = original[name].map(clean_text)
    prepared["introduction_date_iso"] = parse_dates(original["Introduction_Date"])
    prepared["version_date_iso"] = parse_dates(original["Version_Date"])

    #Remove duplicate rows based on bill text now that all text has been cleaned.
    prepared = prepared.drop_duplicates(subset=['Bill_Text_clean'], keep='last')
    

    # Parse a copy of Sponsor_Party; the original text is kept unchanged in the output.
    parties = prepared["Sponsor_Party"].apply(parse_sponsor_parties)


    # Feature engineering: Create 4 new features to count the number of Democratic, Republican, Other, and Unknown parties in the Sponsor_Party column.
    columns = ["D_Count", "R_Count", "Other_Count", "Unknown_Count"]

    prepared[columns] = pd.DataFrame(
        parties.apply(count_parties).tolist(),
        index=prepared.index,
        columns=columns
    )

    # Create 4 new features representing Total Sponsors, Bipartisan Support and overall Democratic and Republican sponsor ratios.
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
    saved = pd.read_csv(output, dtype=str, keep_default_na=False, skip_blank_lines=False)
    pd.testing.assert_index_equal(original.columns, saved.columns[:len(original.columns)])
    # Deduplication keeps the original index, so retained rows are checked value-for-value.
    retained = original.loc[prepared.index].reset_index(drop=True)
    pd.testing.assert_frame_equal(retained, saved[original.columns])
    pd.testing.assert_series_equal(prepared["source_row"].astype(str).reset_index(drop=True), saved["source_row"])
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
