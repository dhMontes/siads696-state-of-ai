# Shared data preparation

Start with [preprocessing.ipynb](preprocessing.ipynb). It prepares one common table and shows the text coverage, date differences and repeated wording worth reviewing.

## Run it

From the repository root, install the packages and open JupyterLab:

```powershell
python -m pip install -r josue_src/requirements.txt
jupyter lab josue_src/preprocessing.ipynb
```

Run the notebook from top to bottom. To prepare the CSV without opening the notebook:

```powershell
python josue_src/prepare.py
```

The input is `data/raw/Final_Database.csv`. The output is
`data/processed/common_intake/common_records.csv`. Optional `--source` and
`--output` arguments select the input and output CSV paths.

## What the table contains

All 2,571 source records and 29 original fields remain. Eight added fields make a 37-column table:

| Added fields | Purpose |
| --- | --- |
| `source_row` | One-based record position in the source snapshot. |
| `Bill_Text_clean`, `Bill_Title_clean`, `NCSL_Summary_clean`, `summary_clean`, `bill_extracts_clean` | Unicode and whitespace normalization; originals remain alongside them. |
| `introduction_date_iso`, `version_date_iso` | Dates in year-month-day format, parsed from the source's month/day/year values. |

Cleaning preserves case, punctuation, numbers and negation. Unexpected date values raise an error for review. The script rereads its output and checks the original fields against the source, including record order.

## Load the output

From the repository root:

```python
import pandas as pd

common = pd.read_csv(
    "data/processed/common_intake/common_records.csv",
    dtype=str,
    keep_default_na=False,
)
common[["source_row", "Bill_Number", "Jurisdiction", "Bill_Status"]].head()
```

Blank cells remain empty strings. `source_row` links to a position in this source file; it is not a model feature or a verified unique-bill key. Choose the fields needed for each analysis.

The notebook calculates coverage and review counts directly from the table. It keeps records with blank summaries or extracts, later text versions and repeated wording. These findings guide review rather than automatic removal.

`Bill_Status` and `Bill_Status_Grouped` describe recorded legislative outcomes. Lowercase `status` describes publisher processing. David and Meng handle the additional filtering, features and models for their analyses.

## Source

The repository CSV mirrors `Final_Database_10.csv` from Bhargava and Soliman's
[U.S. State AI Legislation Corpus, version 4](https://zenodo.org/records/20781731).
The raw file remains unchanged.
