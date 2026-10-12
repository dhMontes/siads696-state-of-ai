# State AI Policy

SIADS 696: Milestone II · University of Michigan, Master of Applied Data Science

This project examines U.S. state AI legislation from two angles: which policy
themes recur across states, and which bill information distinguishes recorded
legislative outcomes. The team combines supervised outcome classification with
unsupervised topic analysis.

Shared data preparation is implemented. Trained models, topic results and the
final report are not yet included in this repository.

## Project workflow

```text
                Published legislation corpus
                             |
                             v
                Shared preparation and review
                             |
                +------------+-------------+
                |                          |
                v                          v
       Supervised analysis           Topic analysis
       Recorded outcomes             Themes across states
                |                          |
                +------------+-------------+
                             |
                             v
                 Combined findings and report
```

The two analyses are planned around the same source snapshot. Shared preparation keeps the
original records; each analysis makes its own feature and eligibility choices.

## Data source

The starting point is Bhargava and Soliman's
[U.S. State AI Legislation Corpus, version 4](https://zenodo.org/records/20781731).
The main file on Zenodo is `Final_Database_10.csv`; its unchanged repository copy
is [data/raw/Final_Database.csv](data/raw/Final_Database.csv).

The snapshot contains 2,571 records and 29 original fields, including bill text,
state information, dates, recorded outcomes and publisher-supplied
classifications. A source record is not automatically a verified unique bill.

`Bill_Status` and `Bill_Status_Grouped` describe recorded legislative outcomes.
The lowercase `status` field describes publisher processing, not a bill outcome.

## Run the shared preparation

Use Python with pip. Run these commands from the repository root:

```shell
python -m pip install -r requirements.txt
python src/prepare.py
```

The script writes `data/processed/common_intake/common_records.csv`: all 2,571
records and 29 original fields, plus eight additions for a 37-column table.
These additions are five cleaned text fields, two dates in year-month-day format,
and `source_row`, the record's one-based position in this source snapshot.

Cleaning normalizes Unicode and whitespace while preserving case, punctuation,
numbers and negation. Original values remain alongside the cleaned fields.
The script checks that the saved original fields and record order match the source.

For the explanation and coverage checks, open the preparation notebook:

```shell
jupyter lab notebooks/01_data_preparation.ipynb
```

Run its cells from top to bottom. Generated tables stay local and are excluded
from Git; teammates reproduce them with the preparation command.

## Load the prepared table

From the repository root:

```python
import pandas as pd

common = pd.read_csv(
    "data/processed/common_intake/common_records.csv",
    dtype=str,
    keep_default_na=False,
)
```

Blank cells remain empty strings. `source_row` is a source locator, not a model
feature or a unique-bill identifier.

## Repository guide

| File or folder | Purpose |
| --- | --- |
| [data/raw/Final_Database.csv](data/raw/Final_Database.csv) | Preserved source snapshot. |
| [src/prepare.py](src/prepare.py) | Reusable shared preparation. |
| [notebooks/00_source_inspection.ipynb](notebooks/00_source_inspection.ipynb) | Initial raw-data preview and schema inspection. |
| [notebooks/01_data_preparation.ipynb](notebooks/01_data_preparation.ipynb) | Preparation walkthrough, text coverage and date/text review checks. |
| [requirements.txt](requirements.txt) | Packages used by the committed script and notebooks. |

## Preparation boundaries

Records with blank summaries or extracts, date differences and repeated wording
remain in the shared table. The notebook shows these findings for review.
Preparation does not select the target, remove records, deduplicate bills,
vectorize text, split the data or train models.

Supervised and topic-analysis notebooks will document their inputs, filtering,
methods and results as those stages are completed. Their findings and the final
report will be linked here for the submitted project.
