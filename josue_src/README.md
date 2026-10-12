# Shared data preparation

Prepare one common table for the supervised and topic analyses. The output keeps
all 2,571 source records and 29 original fields, then adds normalized text, parsed
dates and review flags. The full table has 152 columns, including audit fields.

## Run the preparation

From the repository root:

```powershell
python josue_src/prepare.py
```

The core uses only Python's standard library. It reads `data/raw/Final_Database.csv`
and writes to `data/processed/common_intake/`. Use `--source` and `--output` to select
other paths. The source must match the saved snapshot's checksum, schema and row count.

[prepare.py](prepare.py) runs four steps: read and normalize, audit, assemble the
common table, and validate the outputs. The original CSV stays unchanged.

## Load the prepared table

Run this example from the repository root. pandas is optional for analysis; the
loader itself returns a list of records and a column dictionary.

```python
import sys

import pandas as pd

sys.path.insert(0, "josue_src")
from common_records import load_common_records

records, contract = load_common_records()
common_df = pd.DataFrame.from_records(records)
common_df[["row_locator", "Bill_Number", "Jurisdiction", "Bill_Status"]].head()
```

Values load as strings. Blank cells stay empty strings, so pandas `dropna()` does
not remove them. Use `cell_category__*` when choosing missing-value rules.
Convert types and select fields in the analysis notebook. Keep `row_locator` to
join results back to the source; the full table is not a list of model features.

## Find the outputs

All generated files are under `data/processed/common_intake/`.

| File | Use |
| --- | --- |
| `common_records.csv` | Main table: original values, normalized forms, parsed dates and review flags. |
| `common_records_contract.json` | Meaning, source and role of each column. See the [field guide](common-data-contract.md). |
| `column_missingness.csv`, `text_coverage.csv` | Check populated fields, empty strings, whitespace and literal markers. |
| `review_records.csv` | Records flagged for date, title or repeated-text review. One record can have several reasons. |
| `validation_receipt.json` | Record counts, source checks and output checksums. |

The other CSVs hold supporting raw values, normalized text and diagnostic details.
`candidate_predictors.csv` is a narrow text/title export; use `common_records.csv`
when you need the complete table. Generated data and review notes stay local.

## Choose inputs for each analysis

- Keep `Bill_Text`, `NCSL_Summary`, `summary` and `bill_extracts` separate. A blank
  summary does not mean bill text is missing.
- Use `Bill_Status` and `Bill_Status_Grouped` for recorded legislative outcomes.
  Lowercase `status` describes the publisher's processing.
- Review text versions and dates before choosing prediction inputs. Later text
  can reveal an outcome. Repeated wording does not necessarily mean duplicate bills.
- Choose filtering, target definitions and model features in the relevant analysis.
  Shared preparation keeps every record, including those flagged for review.

Normalization standardizes Unicode and whitespace. It preserves case, punctuation,
numbers, negation and headers. The [field guide](common-data-contract.md) explains
the source fields and added columns. The optional [review log](review_tools/README.md)
keeps notes separate so preparation reruns do not overwrite them.

## Explore the notebook

[preprocessing.ipynb](preprocessing.ipynb) runs preparation and shows text/date
examples, field coverage, review flags and a loading example.
Use Python 3.11 or newer. Install the notebook dependencies, then execute the saved notebook:

```powershell
python -m pip install -r josue_src/notebook-requirements.txt
python josue_src/run_notebook.py
```

The runner uses the current Python environment. Optional `--source` and `--output`
arguments select different locations. It saves executed cells in the notebook.

## Run the checks

```powershell
python -m unittest discover -s josue_src/tests -v
python -m unittest discover -s josue_src/review_tools/tests -v
python josue_src/validate_outputs.py
```

These checks cover original values, source order, multiline text, date parsing,
missing-value markers, review flags and output consistency.

## Source

`data/raw/Final_Database.csv` mirrors `Final_Database_10.csv` from
[U.S. State AI Legislation Corpus, version 4](https://zenodo.org/records/20781731),
by Hemant K. Bhargava and Mark Soliman, published June 21, 2026.
The 2,571 records and 29 original fields remain unchanged.
The snapshot SHA256 is
`188aba4f4e50c6d0acb3532d143b9a81d9cccdf7c0729ba7ded6410399eff232`.
