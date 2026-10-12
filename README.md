# siads696-state-of-ai

Milestone 2 Project Repo

## Shared data preparation

[josue_src](josue_src/README.md) prepares the shared data for SIADS 696: Milestone II.
It keeps the original records and adds cleaned text, parsed dates and review flags.

Run from the repository root:

```powershell
python josue_src/prepare.py
```

The command reads `data/raw/Final_Database.csv` and writes local outputs to
`data/processed/common_intake/`. Start with `common_records.csv` for either analysis.
The [package README](josue_src/README.md) shows how to load it and run the notebook.
