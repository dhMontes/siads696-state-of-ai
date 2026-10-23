# State AI Policy

SIADS 696: Milestone II · University of Michigan, Master of Applied Data Science

This project studies U.S. state AI legislation through two analyses: identifying
recurring policy themes across states and classifying recorded legislative
outcomes using bill information.

**Current progress:** Shared preparation, source-validation checks, NMF/LDA
topic analysis and classification baselines are available in this repository.

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
All six notebooks ran successfully with Python 3.12.

Create a project environment first:

```shell
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` in PowerShell, or
`source .venv/bin/activate` on macOS/Linux.

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

### 3. Run the notebooks

```shell
python -m jupyter lab
```

Select the project environment's Python kernel. Run each notebook from top to
bottom, in numbered order from `00` through `05`. Notebook `01` regenerates the
shared table and checks which records fall within the current split windows.
Notebooks `02`, `03` and `05` read that prepared table. Notebook `04` reviews
the saved source evidence offline; no API key is needed for these runs.

For a command-line run of all six notebooks:

```shell
python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 "notebooks/*.ipynb"
```

This refreshes notebook outputs locally. Topic and classification runs can
take several minutes. Generated tables and topic exports remain outside Git.

## Prepared data

The current script produces **2,567 rows and 45 columns** from the unchanged
2,571-row, 29-column raw file. It keeps the last source occurrence of each
identical `Bill_Text_clean` value, removing four rows across four pairs.
The retained rows remain in source order; `source_row` retains their original positions.

| Recorded outcome group | Raw records | Prepared records |
| --- | --- | --- |
| Failed | 766 | 764 |
| Passed | 324 | 323 |
| Pending | 1,481 | 1,480 |

These are source-recorded groups. The four-row reduction reflects
deduplication, not an outcome update.

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
The walkthrough and review table explain the retained rows and column changes.

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
| [notebooks/02_data_split_exploration.ipynb](notebooks/02_data_split_exploration.ipynb) | Supervised exploration of class balance, bill dates and time-based splits |
| [notebooks/03_topic_analysis.ipynb](notebooks/03_topic_analysis.ipynb) | Topic models, figures and provision-level case review |
| [src/topic_analysis.py](src/topic_analysis.py) | Helpers used by the topic notebook |
| [notebooks/04_source_validation.ipynb](notebooks/04_source_validation.ipynb) | Offline outcome checks, a 20-bill text review and a raw-file header screen |
| [notebooks/05_classification_baselines.ipynb](notebooks/05_classification_baselines.ipynb) | Logistic Regression, Linear SVM and XGBoost input comparisons |
| [src/classification_helpers.py](src/classification_helpers.py) | Preprocessing, model fitting and comparison plots used by the baseline notebook |
| [data/validation/README.md](data/validation/README.md) | Dated observations, comparison tables, field definitions and source attribution |
| [data/validation/deduplication_review.csv](data/validation/deduplication_review.csv) | Four removed-to-retained source-row pairs and their metadata differences |
| [requirements.txt](requirements.txt) | Packages used by the committed script and notebooks |

## Related work

- [Yano, Smith and Wilkerson (2012)](https://aclanthology.org/N12-1097/)
  compare metadata and introduced bill text for federal committee survival,
  informing our input comparisons and attention to text versions.
- [Nay (2017)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0176999)
  compares text, context and combined inputs for congressional enactment
  using chronological evaluation.
- [Quinn and colleagues (2010)](https://doi.org/10.1111/j.1540-5907.2009.00427.x)
  use topic modeling to study themes in U.S. Senate speeches. We use their
  work as a comparison for our topic analysis of state AI bills.

These studies concern different legislative populations and do not establish
performance on our state AI corpus.

## Text versions and outcome dates

The [source-validation notebook](notebooks/04_source_validation.ipynb) separates
recorded dates from text-stage evidence. In the 20-bill review, nine source
headers identify later stages. Matching the introduction date does not prove
that the deposited text is the introduced version. The notebook also screens
all raw headers; an unrecognized header remains unknown.

We keep the original table and recorded outcomes for the initial retrospective
comparison. The source does not establish one observation date for every outcome.
The review flags are evidence for input checks, not model features or automatic
row exclusions. See the [input and cutoff recommendations](data/validation/README.md#using-the-text-review)
before changing text or labels.

## Scope and next stages

Our shared preparation keeps records with blank summaries or extracts and
flags date differences. It removes repeated cleaned bill text and adds eight
sponsor features.

Our supervised and topic analyses use the records, text features, splits and
methods suited to each question. We document these choices and results in
the corresponding notebooks.

We are keeping the source outcomes for the initial baseline. Any comparison
using updated outcomes will need a consistent observation date and outcome
definition. The dated source checks stay separate from the prepared inputs.

We will link our findings and final report here.
