# State AI Policy

SIADS 696: Milestone II · University of Michigan, Master of Applied Data Science

This project studies U.S. state AI legislation through two analyses: identifying
recurring policy themes across states and classifying recorded legislative
outcomes using bill information.

**Current progress:** Shared data preparation and the topic analysis are
implemented. Supervised models and the final report are not yet included in this repository.

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

Both analyses will start from the same source snapshot. Shared preparation keeps the original
records; each analysis chooses its own features and which records to include.

## Data source

The starting point is Bhargava and Soliman's
[U.S. State AI Legislation Corpus, version 4](https://zenodo.org/records/20781731).

| Snapshot | Details |
| --- | --- |
| Published file | `Final_Database_10.csv` |
| Repository copy | [data/raw/Final_Database.csv](data/raw/Final_Database.csv), unchanged from the published file |
| Dimensions | 2,571 records and 29 original fields |
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

The output keeps 2,567 of the 2,571 source records; four records whose cleaned
bill text repeats a later record are removed. Its 45 columns contain the 29
original fields and 16 additions:

| Field group | Count | Purpose |
| --- | --- | --- |
| Original fields | 29 | Preserve the source values and original record order |
| Cleaned text copies (`*_clean`) | 5 | Normalize Unicode and whitespace while retaining the originals |
| Dates in year-month-day format | 2 | Make the available introduction and version dates easier to compare |
| `source_row` | 1 | Identify the record's one-based position in this source snapshot |
| Sponsor Party counts, proportions totals| 7| Engineered features from Sponsor Party to best utilize available data.|
|Bipartisan Support|1|Flag for bills that are sponsored with members of both major parties derived from Sponsor Party counts.|

The script checks that the saved original fields and record order match the
source. These 45 columns are a shared working table, not a prescribed list of
model inputs. `source_row` is a source locator, not a model feature or a unique-bill
identifier.

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
| [notebooks/03_topic_analysis.ipynb](notebooks/03_topic_analysis.ipynb) | Topic models, figures and provision-level case review |
| [src/topic_analysis.py](src/topic_analysis.py) | Helpers used by the topic notebook |
| [tests/](tests/) | Checks for the topic analysis and its saved results |
| [requirements.txt](requirements.txt) | Packages used by the committed script and notebooks |

## Scope and next stages

Shared preparation retains records with blank summaries or extracts, date
differences and repeated wording. The notebook presents these findings for review.

Target selection, record filtering, text vectorization, data splits and model
training belong to the analysis stages. They are not applied by the shared
preparation script.

Duplicate rows are removed and sponsor features are added within shared
preparation, so all members start from the same records and features.

The topic-analysis notebook documents its inputs, methods and results. The
supervised notebook and the final report will be linked here for the submitted
project.
