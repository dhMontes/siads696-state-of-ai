# Source validation

These tables document a frozen 18-record diagnostic sample: six records each from
California, Colorado and Texas. They keep source values, later observations and
interpretations separate. They are not replacement training labels or a national
error-rate estimate.

Open [the source-validation notebook](../../notebooks/04_source_validation.ipynb)
for the comparisons and interpretation. It runs offline from the repository root
or `notebooks/`, using the existing project dependencies.

## Files

| File | Contents and check date |
| --- | --- |
| [bill_status_observations.csv](bill_status_observations.csv) | Original October 13, 2026 official-source observations, with coverage limits and unresolved conflicts. Preserved unchanged. |
| [legiscan_comparison.csv](legiscan_comparison.csv) | October 19, 2026 LegiScan identities, session identifiers, provider stages and available history actions for the same 18 records. |
| [closed_session_review.csv](closed_session_review.csv) | October 19 official-history and closure review of seven intermediate-stage bills in closed sessions. |

`source_row` is the one-based record position in `data/raw/Final_Database.csv`.
The raw file has 2,571 records and 29 fields, with MD5
`397a13c53e719e64e52725e7995fd8ca`. It is unchanged from the published
`Final_Database_10.csv`. A row locator is not a unique-bill identifier or model
feature. Bill identity also requires state and legislative session.

## Findings

- All 18 sampled records match LegiScan state, bill and session identities.
- Seven bills have API Introduced or Engrossed stages in closed sessions. All
  seven source statuses already say `Failed - Adjourned`; no status correction
  or exclusion is justified by that stage distinction alone.
- Four source-Pending bills have signing or chaptering evidence. These were
  already observed October 13 and are confirmed by October 19 API histories.
  Keep them as later evidence, separate from the original-source baseline.
- California AB2291 has no established terminal outcome in this check.
  Colorado HB26-1210's API veto agrees with the earlier history observation;
  the earlier official-page Signed Act/summary wording conflict remains recorded.
- Texas HB4448 has a misleading source short title. Its raw text header supports
  identity with the official bill, but full-text/version equivalence is unverified.

For Texas, failure at session close is an inference from incomplete official
histories and the official closure rule. Colorado HB25B-1008's page records Lost.
The CSVs retain primary links and check times so the evidence can be inspected.

## Field meanings

| Fields | Meaning |
| --- | --- |
| `source_status`, `Bill_Status` | Status recorded in the preserved corpus. Neither table overwrites it. |
| `api_stage_code`, `api_stage`, `api_stage_date` | LegiScan's provider stage and stage date. Code 4 is named Passed, which alone is not an enacted target. |
| `api_first_history_date` | First available history event, including pre-session filing in Texas; not necessarily the source's introduction-date definition. |
| `api_last_action_date`, `last_action_date` | Date of the latest available action, not automatically a failure or enactment date. |
| `session_sine_die`, `session_closed_date` | Provider closure flag or separately verified session closure date. Closure alone does not establish every bill's outcome. |
| `signing_or_chaptering_evidence` | Explicit signing or chaptering history exists in the API response; retained separately from its stage label. |
| `*_checked_at_utc` | Retrieval/check time, separate from legislative event dates. |
| `outcome_review` | Evidence-based interpretation for the seven reviewed cases. Texas's inferred basis is stated explicitly. |

The supervised analysis owns target definitions, eligibility and any separately
reported experiment using later outcomes. These tables do not change raw data,
prepared inputs, features, splits or models. No API key or API request is needed
to use them.

## Sources and attribution

- Bhargava and Soliman, [U.S. State AI Legislation Corpus v4](https://zenodo.org/records/20781731).
- [LegiScan](https://legiscan.com/) API metadata/history, retrieved October 19,
  2026, under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
  `legiscan_comparison.csv` selects, reorganizes and renames provider fields and
  adds source linkage and comparison fields. Stage labels follow the
  [LegiScan API manual](https://api.legiscan.com/dl/LegiScan_API_User_Manual.pdf),
  Status/Progress section, printed page 42.
- Official bill-history URLs appear in the CSVs. Session-closure evidence comes
  from the [Texas Legislative Reference Library's post-session FAQ](https://www.lrl.texas.gov/whatsNew/client/index.cfm/2025/6/3/Whats-Next-PostSession-FAQ-and-Bill-Statistics-89th-RS)
  and [Colorado's extraordinary-session journal](https://content.leg.colorado.gov/sites/default/files/2025_house_journal.pdf),
  printed page 76 (PDF page 80). All seven official bill histories were directly
  retrieved October 19. The Texas FAQ was read through its official web result
  after a direct request returned 403; that route does not imply a direct HTTP read.
