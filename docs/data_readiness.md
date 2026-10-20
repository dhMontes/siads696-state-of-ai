# Shared data readiness

The shared preparation runs from the preserved raw CSV to a traceable,
2,567-record table. The source-inspection, preparation and offline-validation
notebooks also run from top to bottom. This is the observed prepared population,
not the final set of records for either model.

Checked October 19, 2026, using the preparation code and source snapshot in this
repository. No API account or key is needed to reproduce these local steps.

## Reproduce the handoff

From the repository root, after installing [requirements.txt](../requirements.txt):

```shell
python src/prepare.py
python -m nbconvert --execute --to notebook --output-dir data/processed/checks notebooks/00_source_inspection.ipynb
python -m nbconvert --execute --to notebook --output-dir data/processed/checks notebooks/01_data_preparation.ipynb
python -m nbconvert --execute --to notebook --output-dir data/processed/checks notebooks/04_source_validation.ipynb
```

The first command creates
`data/processed/common_intake/common_records.csv`. The notebook commands write
executed copies under the Git-ignored `data/processed/checks` folder without
replacing the committed notebooks. Run them in the Python environment where the
requirements are installed. The checked
execution completed 3 nonempty source-inspection cells, 7 preparation cells and
6 source-validation cells, with no cell errors.

## What changes between source and prepared data

```text
Raw snapshot                Shared preparation                Each analysis
2,571 records / 29 fields -> 2,567 records / 45 fields       -> eligibility,
                            source-row links retained         inputs and splits
                            four repeated-text rows removed
```

The raw file remains unchanged: MD5 `397a13c53e719e64e52725e7995fd8ca`.
Preparation normalizes five text fields, parses two dates, records source-row
positions and adds eight sponsor features. It keeps the last source row for each
identical cleaned bill text. It parses `Sponsor_Party` as a list; the other
source fields match their retained raw rows. See the
[field guide](../README.md#prepared-data) and
[four-pair mapping](../data/validation/deduplication_review.csv).

| Source-snapshot outcome group | Raw records | Prepared records |
| --- | --- | --- |
| Failed | 766 | 764 |
| Passed | 324 | 323 |
| Pending | 1,481 | 1,480 |
| Total | 2,571 | 2,567 |

These are recorded outcome groups, not a final prediction target. The four-row
reduction reflects deduplication, not a status update.

| Text field | Raw populated / blank | Prepared populated / blank |
| --- | --- | --- |
| Bill text | 2,571 / 0 | 2,567 / 0 |
| NCSL description | 2,571 / 0 | 2,567 / 0 |
| Separate summary | 2,087 / 484 | 2,083 / 484 |
| Separate extract | 2,087 / 484 | 2,083 / 484 |

The same 484 prepared records lack both the separate summary and extract.
They still have bill text and NCSL descriptions, so shared preparation keeps them.
Field-specific analyses decide their own eligibility.

## Review decisions before modeling

- All 18 dated-validation records still link to the prepared table through
  `source_row`. The [validation notebook](../notebooks/04_source_validation.ipynb)
  reproduces the saved comparisons offline; it does not refresh live sources.
- Two deduplicated pairs have conflicting sponsor lists. The
  [official-source sponsor review](../data/validation/sponsor_review.csv)
  documents these disagreements. Keeping the last row does not establish the
  most accurate sponsor list; the existing features remain unchanged.
- Thirteen prepared text versions precede their introduction dates; 946 follow
  them. These are review flags, not automatic exclusions or proof of leakage.
  Historical prediction needs inputs available at the chosen prediction time.
- A common observation cutoff and outcome rule remain to be agreed. Dated
  validation observations stay separate from the source labels. The selected
  18-bill pilot does not establish accuracy across all 2,571 source records.

Next: agree on the outcome cutoff and eligible records before constructing the
final model comparisons.

Sources: [preserved corpus](../README.md#data-source), executed preparation and
walkthrough, and [dated validation tables](../data/validation/README.md).
