# Common-record field guide

`common_records.csv` contains 2,571 records and 152 columns. It preserves all 29
original fields and adds values used for preparation and review. The generated
`common_records_contract.json` describes every column.

## Original fields

Original column names contain unchanged CSV strings. Roles group fields by purpose;
they do not choose a final set of model inputs.

| Role | Original fields | Meaning |
| --- | --- | --- |
| Candidate | `Bill_Text`, `Bill_Title`, `measure_code`, `Jurisdiction`, `State_Political_Control`, `Regional_Cluster_ID`, `Sponsor`, `Sponsor_Party`, `Introduction_Date` | Bill text and metadata to consider in the analyses. |
| Evidence | `Bill_Number`, `Bill_URL`, `Version_Date`, `Year`, `NCSL_Summary`, `NCSL_Category` | Lookup information, dates and NCSL descriptions/categories. |
| Outcome | `Bill_Status`, `Bill_Status_Grouped` | Recorded legislative status and grouping. |
| Publisher derived | `bill_extracts`, `summary`, `analyst_results`, `retry_attempts`, `status`, `product_safety_score`, `ai_inputs_ip_score`, `market_structure_score`, `specific_use_score`, `societal_risks_score`, `institutional_processes_score`, `ai_advancement_score` | Publisher summaries, extracts, classifications, scores and processing metadata. |

`NCSL_Summary`, `summary` and `bill_extracts` remain separate fields. Lowercase
`status` describes publisher processing; `Bill_Status` describes the bill's outcome.
Field names alone do not establish how or when a description was written.

## Added columns

| Columns | Meaning |
| --- | --- |
| `row_locator`, `source_sha256`, `logical_csv_row` | Source file identity and record position. Use for joins, not model features. |
| `normalized__*` | Unicode NFC normalization, whitespace collapse and trimming. Original strings remain available. |
| `introduction_date_iso`, `introduction_year_parsed` | Parsed introduction date and year. |
| `version_date_iso`, `version_year_parsed` | Parsed text-version date and year. |
| `cell_category__*` | Whether a cell is populated, empty, whitespace-only or an exact literal marker. |
| `review__*`, `review_reasons_json`, `review_status` | Date, sponsor-array, repeated-text and other diagnostic observations. |

For example, `normalized__Bill_Text` is the cleaned version of `Bill_Text`.
Normalization preserves case, punctuation, numbers, negation and administrative headers.
It does not fill missing summaries or replace original text.

`row_locator` combines the source checksum with the logical CSV record number.
The header is record 1, so the first data record is 2. A multiline bill text still
belongs to one record. This identifies a source row, not a verified unique bill.

Sponsor and party fields retain their original strings. Parsed arrays in
`review__sponsor_array_json` and `review__party_array_json` preserve null items;
malformed arrays remain unavailable. Scores and retry counts also load as strings.

## Analysis choices

The table retains every record, including date conflicts and repeated text.
Review flags identify cases to inspect; they do not remove, merge or correct rows.
Human notes can be recorded in the optional [review log](review_tools/README.md).

Choose conversions, filtering, targets and features within each analysis.
Text versions and dates need particular attention because later text can reveal
an outcome. The contract's `use_in_model_now` field is false for every column:
preparation records column roles without selecting model features.

Sources: [source roles and normalization](pipeline.py),
[table builder and loader](common_records.py), [output validation](validate_outputs.py).
