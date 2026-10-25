# State AI Policy

SIADS 696: Milestone II · University of Michigan, Master of Applied Data Science

We study U.S. state AI legislation from two angles: recurring policy themes
across states and the bill information associated with recorded outcomes.
The project combines NMF and LDA topic models with Logistic Regression,
Linear SVM and XGBoost classifiers.

[Data](#data) · [Setup](#setup-and-running-the-project) · [Notebooks](#notebooks) · [Report assets](report-assets/README.md) · [Limitations](#interpreting-the-results) · [Related work](#related-work)

To review the analyses, start with [03 · Topic analysis](notebooks/03_topic_analysis.ipynb)
and [06 · Model evaluation](notebooks/06_model_evaluation.ipynb). The
[report assets](report-assets/README.md) contain selected figures and tables.
[07 · Final evaluation](notebooks/07_final_evaluation.ipynb) is the workflow for
the team's chosen configuration; its 2026 evaluation has not been run.

## Workflow

```text
            Published legislation CSV
                       |
             Shared data preparation
                       |
          +------------+------------+
          |                         |
  Outcome classification     Topic analysis
          |                         |
          +------------+------------+
                       |
              Findings and report
```

Both analyses use the same prepared table, with additional filtering and
features chosen for each analysis.

## Data

Our source is Bhargava and Soliman's
[U.S. State AI Legislation Corpus, version 4](https://zenodo.org/records/20781731).
The published file, `Final_Database_10.csv`, is preserved as
[data/raw/Final_Database.csv](data/raw/Final_Database.csv). It contains
**2,571 records and 29 columns**, including bill text, state information,
dates, recorded statuses and publisher-generated classifications.

[src/prepare.py](src/prepare.py) creates a table with **2,567 rows and 45 columns**.
It adds cleaned text, standardized dates, a source-row locator and eight sponsor
features. Four rows with identical cleaned bill text are removed, keeping the
last occurrence in source order. This rule does not establish which record has
the most accurate metadata; the [deduplication review](data/validation/deduplication_review.csv)
shows the four pairs. The raw file is unchanged.

The classifiers use the publisher's `Bill_Status_Grouped` labels:

| Group | Prepared records | Source statuses included |
| --- | --- | --- |
| Failed | 764 | Failed and Vetoed |
| Passed | 323 | Enacted and Adopted |
| Pending | 1,480 | Pending, To Governor and Override Pending |

These groups describe the source snapshot. Pending includes unresolved bills;
Passed does not mean every record is an enacted law. The lowercase `status`
column tracks publisher processing and is not a legislative outcome.

Records with blank summary or extract fields remain in the shared table.
`source_row` identifies a record's one-based position in the raw CSV; it is
neither a unique-bill identifier nor a model input. Notebook
[01](notebooks/01_data_preparation.ipynb) explains the column changes and checks
text coverage, dates and bill versions. It creates the review flags separately
from the preparation script.

## Setup and running the project

Use Python 3.12 and run commands from the repository root.

### 1. Create and activate an environment

```shell
python -m venv .venv
```

| Shell | Activation command |
| --- | --- |
| PowerShell | `.venv\Scripts\Activate.ps1` |
| macOS/Linux | `source .venv/bin/activate` |

### 2. Install packages and prepare the data

```shell
python -m pip install -r requirements.txt
python -m ipykernel install --sys-prefix --name state-ai-policy --display-name "State AI Policy"
python src/prepare.py
```

### 3. Run the notebooks

```shell
python -m jupyter lab
```

Select the **State AI Policy** kernel and run an opened notebook from top to bottom.
After `prepare.py`, notebooks 03 and 06 can each run independently. The supporting
notebooks in the table below document inspection, preparation and validation;
they are not prerequisites for those two analyses. The source-validation
notebook uses saved evidence and runs offline; no API key is needed.

Optional: to execute the full collection, including the supporting notebooks:

```shell
python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.kernel_name=state-ai-policy --ExecutePreprocessor.timeout=1800 "notebooks/*.ipynb"
```

Model runs can take several minutes. This command replaces the saved notebook
outputs in your local copy.

### Generated files

| Location | Contents |
| --- | --- |
| `data/processed/common_intake/common_records.csv` | Shared prepared table from `prepare.py` |
| `data/processed/common_intake/analysis_rows.csv` | Notebook 01's record checks and split eligibility |
| `outputs/topic_analysis/` | Topic tables and figures |
| `data/processed/model_evaluation/` | Evaluation tables and figures |
| `data/processed/final_evaluation/` | Final scores, predictions and settings after selecting a configuration in notebook 07 |

These outputs are excluded from Git and regenerated locally.
Selected existing figures and tables are also available in
[report-assets/](report-assets/README.md) for report assembly.

To load the prepared table while preserving blank cells as empty strings:

```python
import pandas as pd

common = pd.read_csv(
    "data/processed/common_intake/common_records.csv",
    dtype=str,
    keep_default_na=False,
)
```

## Notebooks

| Notebook | Role | Contents |
| --- | --- | --- |
| [00 · Source inspection](notebooks/00_source_inspection.ipynb) | Supporting | Raw-data preview, columns and types |
| [01 · Data preparation](notebooks/01_data_preparation.ipynb) | Supporting | Shared preparation, text coverage, date checks and split eligibility |
| [02 · Split exploration](notebooks/02_data_split_exploration.ipynb) | Supporting | Class balance and introduction-year splits |
| [03 · Topic analysis](notebooks/03_topic_analysis.ipynb) | Core analysis | NMF and LDA models, figures and bill-text examples |
| [04 · Source validation](notebooks/04_source_validation.ipynb) | Supporting | Selected outcome checks, text-version review and raw-header screening |
| [05 · Classification baselines](notebooks/05_classification_baselines.ipynb) | Supporting | Logistic Regression, Linear SVM and XGBoost input comparisons |
| [06 · Model evaluation](notebooks/06_model_evaluation.ipynb) | Core analysis | Matched classifier and input comparisons, topic features, related-text sensitivity and SVM errors |
| [07 · Final evaluation](notebooks/07_final_evaluation.ipynb) | Final workflow | One selected configuration trained through 2025 and evaluated on 2026 |

Reusable functions are in [src/topic_analysis.py](src/topic_analysis.py) and
[src/classification_helpers.py](src/classification_helpers.py). Dependencies
are listed in [requirements.txt](requirements.txt). Dated source checks and
their definitions are documented in [data/validation/](data/validation/README.md).

[Notebook 06](notebooks/06_model_evaluation.ipynb) compares classifier inputs
with and without NMF/LDA summary topics. Vocabulary and topics fit on training
bills inside each pipeline, then transform validation bills. NMF uses TF-IDF;
LDA uses word counts. Both use English and legal stopwords and eight topics.
The descriptive LDA model in notebook 03 uses English stopwords only, so its
vocabulary differs. Its full-corpus topic exports are not classifier inputs.

In notebook 07, enter the team's chosen configuration before running the final
evaluation. With no configuration selected, the notebook skips fitting and scoring.
Choose the settings from the development comparisons before evaluating 2026.

## Interpreting the results

The supervised task classifies **recorded outcomes**, rather than predicting a
bill's fate at introduction. Some source texts and sponsor lists reflect later
stages, and the dataset does not establish a common observation date for all
outcomes. The source checks document later observations separately without
replacing the baseline labels. See the
[text-review findings](data/validation/README.md#using-the-text-review).

Classifiers train on 2019–2024 bills and validate on 2025; the 2026 bills are
saved for final testing. Notebook 06 also compares earlier-year folds. Small
early folds, changing class proportions and related bill texts limit how far
these results generalize. Chronological splits do not guarantee that related
bills stay together; the text-similarity check is a separate sensitivity analysis. Topic patterns and model coefficients describe
associations, not causes of legislative outcomes.

The notebooks contain the current comparisons. Final model selection, the
2026 evaluation and the written report are still in progress.

## Related work

- [Yano, Smith and Wilkerson (2012)](https://aclanthology.org/N12-1097/)
  compare metadata and introduced bill text for federal committee survival,
  informing our input comparisons and attention to text versions.
- [Nay (2017)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0176999)
  compares text, context and combined inputs for congressional enactment using
  chronological evaluation.
- [Quinn and colleagues (2010)](https://doi.org/10.1111/j.1540-5907.2009.00427.x)
  use topic models to study U.S. Senate speeches, providing a comparison for
  interpreting themes in our state-bill analysis.

These studies concern different legislative populations; their results do not
establish performance on our dataset.
