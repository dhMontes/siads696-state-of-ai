# State AI Policy

SIADS 696: Milestone II · University of Michigan, Master of Applied Data Science

This project studies U.S. state AI legislation through two analyses: identifying
recurring policy themes across states and classifying recorded legislative
outcomes using bill information.

**Current progress:** Shared data preparation is implemented. Trained models,
topic results and the final report are not yet included in this repository.

[Workflow](#project-workflow) · [Data source](#data-source) · [Quickstart](#quickstart) · [Files](#repository-guide) · [Scope](#scope-and-next-stages)

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

Both analyses start from the same source snapshot. Shared preparation normalizes text,
removes repeated cleaned bill text and adds sponsor features. Each analysis chooses
its inputs and any additional eligibility rules.

## Data source

The starting point is Bhargava and Soliman's
[U.S. State AI Legislation Corpus, version 4](https://zenodo.org/records/20781731).

| Snapshot | Details |
| --- | --- |
| Published file | `Final_Database_10.csv` |
| Repository copy | [data/raw/Final_Database.csv](data/raw/Final_Database.csv), unchanged from the published file |
| Raw dimensions | 2,571 records and 29 original fields |
| Raw file MD5 | `397a13c53e719e64e52725e7995fd8ca` |
| Contents | Bill text, state information, dates, recorded outcomes and publisher-supplied classifications |

The record count is not a verified count of unique bills.
`Bill_Status` and `Bill_Status_Grouped` describe recorded legislative outcomes.
The lowercase `status` field describes publisher processing, not a bill outcome.

## Quickstart

Run these commands from the repository root, using Python with pip.

### 1. Install packages

```shell
python -m pip install -r requirements.txt
```

### 2. Prepare the shared data

```shell
python src/prepare.py
```

The script creates `data/processed/common_intake/common_records.csv`.
Generated tables are excluded from Git; each teammate runs this step locally.

### 3. Open the walkthrough

```shell
jupyter lab notebooks/01_data_preparation.ipynb
```

Run the notebook cells from top to bottom for the preparation explanation,
text-coverage checks and date/text review findings.

## Prepared data

The current script produces **2,567 rows and 45 columns** from the unchanged
2,571-row, 29-column raw file. It keeps the last source occurrence of each
identical `Bill_Text_clean` value, removing four rows across four pairs.
The retained rows remain in source order; `source_row` retains their original positions.

| Field group | Count | Purpose |
| --- | --- | --- |
| Source fields | 29 | Retain source columns for each surviving record; `Sponsor_Party` is parsed as a list |
| Cleaned text copies (`*_clean`) | 5 | Normalize Unicode and whitespace without replacing the original text |
| Dates in year-month-day format | 2 | Compare available introduction and version dates |
| `source_row` | 1 | Locate the record's one-based position in this raw snapshot |
| Sponsor features | 8 | Describe party counts, sponsor totals, party ratios and bipartisan sponsorship |

The [four-pair deduplication review](data/validation/deduplication_review.csv)
maps each removed source row to the retained row. Within each pair, the source
URLs encode the same bill identifier, although bill-number formatting and some
metadata differ. This supports a same-bill interpretation within the file; it
does not verify the records against the legislature. Keeping the last row is a
position rule, not proof that its metadata are newer or more accurate.

The prepared CSV serializes parsed `Sponsor_Party` lists differently from the raw
CSV, for example `["R"]` becomes `['R']`. The raw file remains unchanged. Other
source fields match the corresponding surviving rows in the checked output.
The script checks column order; the walkthrough and review table explain row changes.

### Field roles

These are available fields, not a prescribed feature set for either analysis.

| Role | Fields | How to use them |
| --- | --- | --- |
| Text candidates | `Bill_Text_clean`, `Bill_Title_clean`, `NCSL_Summary_clean`, `summary_clean`, `bill_extracts_clean` | Select text appropriate to the question; summary and extract coverage differs from full text |
| Recorded outcomes | `Bill_Status`, `Bill_Status_Grouped` | Source-snapshot labels; distinguish them from later dated observations |
| Identity and timing | `Bill_Number`, `Jurisdiction`, `Year`, `Bill_URL`, `introduction_date_iso`, `version_date_iso` | Check identity and whether text timing fits the analysis |
| Source locator | `source_row` | Reconnect a prepared row to this exact raw snapshot; not a model feature or unique-bill identifier |
| Sponsor counts | `D_Count`, `R_Count`, `Other_Count`, `Unknown_Count` | Counts derived from parsed `Sponsor_Party` entries |
| Sponsor totals and mix | `Total_Sponsors`, `Bipartisan_Support`, `Democrat_Sponsor_Ratio`, `Republican_Sponsor_Ratio` | Total entries, presence of both major parties, and party shares of all entries |
| Publisher processing and annotations | `status`, `retry_attempts`, `analyst_results`, taxonomy score columns | Processing or publisher-generated classifications; `status` is not a legislative outcome |
| Dated validation evidence | [data/validation/](data/validation/README.md) | Separate observations and comparison tables; not automatically substituted training labels |

### Load the table

From the repository root:

```python
import pandas as pd

common = pd.read_csv(
    "data/processed/common_intake/common_records.csv",
    dtype=str,
    keep_default_na=False,
)
```

Blank cells remain empty strings.

## Repository guide

| File | Purpose |
| --- | --- |
| [data/raw/Final_Database.csv](data/raw/Final_Database.csv) | Preserved source snapshot |
| [src/prepare.py](src/prepare.py) | Reusable shared preparation |
| [notebooks/00_source_inspection.ipynb](notebooks/00_source_inspection.ipynb) | Initial raw-data preview and schema inspection |
| [notebooks/01_data_preparation.ipynb](notebooks/01_data_preparation.ipynb) | Preparation walkthrough, text coverage and date/text review checks |
| [notebooks/04_source_validation.ipynb](notebooks/04_source_validation.ipynb) | Offline 18-bill source validation and seven closed-session reviews |
| [data/validation/README.md](data/validation/README.md) | Dated observations, comparison tables, field definitions and source attribution |
| [data/validation/deduplication_review.csv](data/validation/deduplication_review.csv) | Four removed-to-retained source-row pairs and their metadata differences |
| [docs/related_work_evidence.md](docs/related_work_evidence.md) | Three published-study comparisons and upstream corpus notes, with inspected coverage and limitations |
| [docs/data_readiness.md](docs/data_readiness.md) | Reproduction commands, prepared counts, text coverage and remaining analysis decisions |
| [requirements.txt](requirements.txt) | Packages used by the committed script and notebooks |

## Scope and next stages

Shared preparation keeps records with blank summaries or extracts and date
differences. It removes identical cleaned bill text using the positional rule
above and adds the eight sponsor features.

Target selection, further record filtering, text vectorization, data splits and
model training belong to the analysis stages. Before changing recorded outcomes,
choose a consistent observation cutoff and outcome rule. Later source checks stay
separate so results remain interpretable against the original snapshot.

The supervised and topic-analysis notebooks will document their inputs,
filtering, methods and results as those stages are completed. Their findings
and the final report will be linked here for the submitted project.
