# State AI Policy

SIADS 696: Milestone II · University of Michigan, Master of Applied Data Science

This project studies U.S. state AI legislation through two analyses: identifying
recurring policy themes across states and classifying recorded legislative
outcomes using bill information.

**Current progress:** Shared preparation and an executable NCSL-summary topic
analysis are implemented. The topic notebook includes the requested eight-topic
NMF baseline, representative measures, category/state plots, eight stored-text
case reviews, sensitivity checks and a bounded LDA comparison. The combined
project report and independent human validation are still pending.

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

### 4. Run the topic analysis

```shell
jupyter lab notebooks/03_topic_analysis.ipynb
```

Run all cells. Only `NCSL_Summary_clean` enters the models; existing categories
and jurisdictions are compared after fitting, and `Bill_Text` supports the eight
case reviews. All prepared records with nonempty NCSL summaries are retained; counts and removal mappings are recorded in `data_audit.json`. One summary has no terms after
vectorization and is marked unassigned. The 484 missing publisher-generated
summaries do not cause exclusions.

Generated CSV tables, figures, model objects and provenance metadata are written
to `outputs/topic_analysis/` (ignored by Git). The notebook includes executed
outputs. To re-execute and export an HTML copy from the repository root:

```shell
python src/execute_notebook.py notebooks/03_topic_analysis.ipynb --html outputs/topic_analysis/03_topic_analysis.html
```

The full run takes about one minute. Key outputs, with baseline versions also saved
for each refined table or figure:

| Question | Files in `outputs/topic_analysis/` |
| --- | --- |
| What are the topics? | `refined_topic_summary.csv`, `refined_leading_words.png`, `refined_representative_bills.csv` (eight topics times five records) |
| How many topics? | `k_selection.png`, `baseline_k_selection.csv`, `refined_k_selection.csv`, `model_comparison.csv` |
| How do states differ? | `refined_state_mean_topic_shares.png` (proposal rule: mean normalized weights with counts), `refined_state_topic_proportions.png` (dominant topic) |
| How do introduction cohorts differ? | `refined_cohort_mean_topic_shares.png` and `.csv` |
| How do topics relate to source categories? | `refined_topic_category_heatmap.png` |
| Which provisions connect bills? | `case_analysis.csv`, `case_stability_summary.csv`, `collapsed_duplicate_runs.csv` |

The legal-word refinement is documented separately from the exact requested
baseline. `INCLUDE_LDA` in the notebook controls the secondary LDA comparison;
NMF remains the main analysis.

**Topic count.** The reviewed models use k=8. The notebook's topic-count check
fits each k from 5 to 12 from five starts and applies a stated rule (best
matched-topic stability among counts within 0.01 of the best mean NPMI). It
favors k=9 for the baseline and k=10 for the refined variant at every tolerance
from 0.005 to 0.03. Refined k=10 restores a standalone task-force topic and
isolates ceremonial commendations. The rule was written after the k=8 review,
so adopting another count requires re-reviewing labels and case references.

**Cohorts** use the year of `introduction_date_iso`, as in notebook 02. Early
cohorts are small, and 2026 runs only to 2026-04-02.

The cases suggest shared human-oversight requirements across employment and
health coverage, related assessment/notice provisions in housing and lending,
and study/reporting institutions across workforce, education and justice.
The selected pair relationships persist across all 12 distinct NMF solutions,
but LDA does not reproduce all of them. Runs that converge to practically the
same solution (assignment ARI >= 0.99 within one method, variant and k) are
counted once. These are purposive, version-specific findings;
they are not current-law assertions or prevalence estimates. State counts and
proportions describe source coverage, not how much a state values a policy.
NMF factor scaling also affects dominant-topic counts. The notebook now compares
raw weights with an equivalent unit-component-mass convention and exports
`nmf_scaling_sensitivity.csv`, `case_pair_scaling_sensitivity.csv`, and alternative
state tables. The requested raw-weight baseline is retained.

After running the notebook, verify the analysis and saved artifacts with:

```shell
python -m unittest discover -s tests -v
```

The regression checks cover category parsing, zero-vector records, denominators,
source/preparation integrity, the LDA-off report, factor-scaling invariance,
representative rankings, original evidence spans, saved-table consistency,
mean-share reconstruction for states and cohorts, the topic-count rule, and
duplicate-solution collapsing.

## Prepared data

The current output has 2,567 records and 45 columns: 29 source fields, eight text/date/locator additions, and eight sponsor features. Four cleaned-full-text duplicates are removed with `keep="last"`; `source_row` preserves original positions. The topic audit records the current dimensions and every removed-to-retained mapping:

| Field group | Count | Purpose |
| --- | --- | --- |
| Original fields | 29 | Preserve the source values and original record order |
| Cleaned text copies (`*_clean`) | 5 | Normalize Unicode and whitespace while retaining the originals |
| Dates in year-month-day format | 2 | Make the available introduction and version dates easier to compare |
| `source_row` | 1 | Identify the record's one-based position in this source snapshot |
| Sponsor Party counts, proportions totals| 7| Engineered features from Sponsor Party to best utilize available data.|
|Bipartisan Support|1|Flag for bills that are sponsored with members of both major parties derived from Sponsor Party counts.|

Shared preparation verifies that every retained record keeps its original values (including the `Sponsor_Party` text) and `source_row`; sponsor counts are computed from a parsed copy. The topic intake independently repeats these checks against the raw snapshot and confirms each removed record duplicates a retained cleaned full text. These columns are a shared working table, not a prescribed list of
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
| [notebooks/02_data_split_exploration.ipynb](notebooks/02_data_split_exploration.ipynb) | Duplicate review, target classes and the introduction-year train/validation/test split |
| [notebooks/03_topic_analysis.ipynb](notebooks/03_topic_analysis.ipynb) | Executed summary-only topic analysis, plots and provision-level case review |
| [src/topic_analysis.py](src/topic_analysis.py) | Reusable fitting, diagnostic, category parsing, export and evidence-check helpers |
| [src/execute_notebook.py](src/execute_notebook.py) | Re-execute a notebook with progress output and export HTML |
| [notebooks/topic_labels.json](notebooks/topic_labels.json) | Post-fit topic names, interpretations and review limitations |
| [notebooks/topic_case_review.json](notebooks/topic_case_review.json) | Eight purposive cases, exact text anchors, provision differences and pair definitions |
| [tests/](tests/) | Regression checks and independent saved-artifact audits |
| [requirements.txt](requirements.txt) | Packages used by the committed script and notebooks |

## Scope and next stages

Shared preparation retains records with blank summaries or extracts, date
differences and repeated wording. The notebook presents these findings for review.

Shared preparation removes duplicate cleaned full texts and engineers sponsor features. Target selection, additional filtering or family-level deduplication, vectorization, data splits and model training belong to the analysis stages.

The topic notebook documents its inputs, case-selection decisions, model
comparisons and limitations. Independent case review and family-aware validation
remain follow-up work. Its whole-corpus topic weights must not be reused as
leakage-free supervised features: refit the vocabulary and topic model within
each training split before adding topics to the outcome classifier.

### Topic refresh and supervised handoff

`03_topic_analysis.ipynb` checks reviewed top terms and aligns models with the previous saved run before applying labels. Unexpected renumbering or term changes stop execution. The reviewed migration is pinned to the old model hash and current input hash. Baseline health/formula topics exchanged IDs; the refined study-body theme merged into state/education. `previous_run_topic_alignment.csv` records the comparison.

`outputs/topic_analysis/supervised_topic_features.csv` joins on `source_row`. Following notebook 02, splits use the year of `introduction_date_iso`, not NCSL `Year`. Its vocabulary and NMF fit only introduction years 2019-2024; 2025 and 2026 are transform-only validation and test sets. The export retains both `Year` and `introduction_date_iso`, adds `introduction_year`, and marks missing, invalid or out-of-range introduction dates as `excluded`, matching notebook 02. Excluded rows are transformed for join completeness but never fitted or assigned to train/validation/test. `supervised_metadata.json` records the date column and split counts, and `supervised_topic_model.joblib` stores the fitted model. IDs are independent of the descriptive model. Refit within training folds for cross-validation; temporal fitting does not remove cross-year companion bills or repeated summaries.

`summary_dedup_*` compares a model fit on unique cleaned summaries with the baseline on the same full evaluation population. `*_topic_bipartisan_counts.csv` and `*_topic_sponsor_summary.csv` report post-fit associations, with observed-ratio denominators. They do not support causal or party-effect conclusions.

Local pre-refresh outputs are preserved in `outputs/archive_2571_pre_pr4/`. Notebook 04 and crawler work remain local and should be reviewed and submitted separately from 03; crawling remains paused.
