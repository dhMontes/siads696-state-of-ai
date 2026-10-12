# Optional record review log

Use this CSV log to track decisions about flagged records. Notes stay outside the
generated outputs, so rerunning preparation preserves them. The log does not change
the prepared data.

## Create the log

First [run the preparation](../README.md#run-the-preparation). Then run these
PowerShell commands from the repository root:

```powershell
New-Item -ItemType Directory -Force data/private_review

python josue_src/review_tools/review_decisions.py init `
  --source data/raw/Final_Database.csv `
  --audit data/processed/common_intake/common_input_audit.json `
  --queue data/processed/common_intake/review_records.csv `
  --output data/private_review/review_decisions.csv
```

Initialization creates one entry per source record and review reason. It refuses
to overwrite an existing log, so existing notes are preserved.

## Add notes

Edit only `status`, `note`, `evidence_reference` and `reviewed_at`.
Keep the source and record identifiers unchanged so each note stays linked to its flag.

| Status | Use when |
| --- | --- |
| `unreviewed` | The record still needs inspection. Leave `reviewed_at` blank. |
| `reviewed_no_change` | Review found no change needed. |
| `needs_source_check` | The original source needs checking. |
| `needs_team_decision` | The team needs to agree on an analysis choice. |

For reviewed entries, set `reviewed_at` to an ISO date such as `2026-10-11`.
Use `note` for the finding and `evidence_reference` for its source.

## Check the log

```powershell
python josue_src/review_tools/review_decisions.py validate `
  --source data/raw/Final_Database.csv `
  --audit data/processed/common_intake/common_input_audit.json `
  --queue data/processed/common_intake/review_records.csv `
  --decisions data/private_review/review_decisions.csv
```

Validation checks row coverage, identifiers, statuses and dates. It does not judge
the review conclusions. If the source or review queue changes, create a separate
log and reconcile the existing notes. Keep logs local in `data/private_review/`.

Sources: [review log implementation](review_decisions.py),
[review log tests](tests/test_review_decisions.py).
