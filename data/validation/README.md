# Source validation

These tables keep source values, later observations and interpretations
separate. The original diagnostic sample contains 18 records: six each from
California, Colorado and Texas. Two sponsor cases extend the API identity and
text-version checks to 20 retained records. This convenience sample does not
estimate national error rates or provide replacement training labels.

Open [the source-validation notebook](../../notebooks/04_source_validation.ipynb)
for the comparisons and interpretation. It runs offline from the repository root
or `notebooks/`, using the existing project dependencies.

## Files

| File | Contents and check date |
| --- | --- |
| [bill_status_observations.csv](bill_status_observations.csv) | Original October 13, 2026 official-source observations, with coverage limits and unresolved conflicts. Preserved unchanged. |
| [legiscan_comparison.csv](legiscan_comparison.csv) | October 19, 2026 LegiScan identities, session identifiers, provider stages and available history actions for the same 18 records. |
| [closed_session_review.csv](closed_session_review.csv) | October 19 official-history and closure review of seven intermediate-stage bills in closed sessions. |
| [deduplication_review.csv](deduplication_review.csv) | Four removed-to-retained source row pairs from the current preparation run. |
| [sponsor_review.csv](sponsor_review.csv) | October 19 official-source checks of the two duplicate pairs with different sponsor-party lists. |
| [sponsor_resolution.csv](sponsor_resolution.csv) | Two current sponsor rosters reconciled with official sources, with historical text and role differences preserved. |
| [text_version_review.csv](text_version_review.csv) | Version-reference checks for 20 records: 79 available references, 19 introduced references and one undated Delaware Draft. |
| [source_text_review.csv](source_text_review.csv) | October 20 offline date/header review of those 20 source texts, linked to the unchanged raw file and cached October 19 version evidence. |

`source_row` is the one-based record position in `data/raw/Final_Database.csv`.
The raw file has 2,571 records and 29 fields, with MD5
`397a13c53e719e64e52725e7995fd8ca`. It is unchanged from the published
`Final_Database_10.csv`. A row locator is not a unique-bill identifier or model
feature. Bill identity also requires state and legislative session.

## Findings

- All 18 original sampled records and both sponsor cases match LegiScan
  state, bill and session identities. The union is 20 of 2,567 prepared
  records; the remaining 2,547 have not been checked through these tables.
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
| `review_state`, `checked_at_utc` | Observation coverage and check time for one retained source row; a review state does not establish final model eligibility. |
| `api_date_raw`, `document_date`, `date_basis` | Preserve the provider date separately from any verified document date and its stated source. |
| `current_api_roster`, `introduced_author_list`, `later_or_observed_author_list` | Keep current sponsor metadata distinct from author blocks printed in particular text versions. |

Target definitions, eligibility and experiments using later outcomes are
outside the scope of these source-validation tables. These tables do not change
raw data, prepared inputs, features, splits or models. No API key or API request
is needed to use them.

## Sources and attribution

- Bhargava and Soliman, [U.S. State AI Legislation Corpus v4](https://zenodo.org/records/20781731).
- [LegiScan](https://legiscan.com/) API metadata/history, retrieved October 19,
  2026, under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
  `legiscan_comparison.csv` selects, reorganizes and renames provider fields and
  adds source linkage and comparison fields. The sponsor and text-version
  tables similarly select provider fields, link them to source rows and add
  official-source observations. Stage labels follow the
  [LegiScan API manual](https://api.legiscan.com/dl/LegiScan_API_User_Manual.pdf),
  Status/Progress section, printed page 42.
- Official bill-history URLs appear in the CSVs. Session-closure evidence comes
  from the [Texas Legislative Reference Library's post-session FAQ](https://www.lrl.texas.gov/whatsNew/client/index.cfm/2025/6/3/Whats-Next-PostSession-FAQ-and-Bill-Statistics-89th-RS)
  and [Colorado's extraordinary-session journal](https://content.leg.colorado.gov/sites/default/files/2025_house_journal.pdf),
  printed page 76 (PDF page 80). The seven official histories were checked
  October 19. The Texas closure rule was checked in the official FAQ's available
  web text; the linked page was inaccessible.

## Duplicate and sponsor checks

[deduplication_review.csv](deduplication_review.csv) maps four removed source
records to the retained records. Each pair shares its encoded source bill
identifier and cleaned bill text. This supports the four observed matches;
identical text alone does not establish bill identity across the corpus.

[sponsor_review.csv](sponsor_review.csv) checks the two pairs with conflicting
party lists against official legislative sources:

- California SCR 82: the original committee analysis names Niello as author,
  but the retained record omits him and lists twelve other legislators.
- Delaware SCR 18: the removed record names primary sponsor Richardson.
  The retained six-name list differs from the inspected official sponsor list.

[sponsor_resolution.csv](sponsor_resolution.csv) reconciles the current
rosters: California SCR 82 has Niello, Fong and Sharp-Collins; Delaware SCR 18
has 20 sponsors. Historical lists remain separate. California's introduced
text names Niello alone, while its June 11, 2026 amendment adds the two
Assembly coauthors. Delaware's undated API Draft prints 19 names, omitting
Vanderwende from the current 20-name list. State and API sponsor-role labels
are preserved separately because their definitions differ.

These observations do not replace source lists or alter prepared sponsor
features. Official links, check times and version limits appear in the table.

## Text-version checks

[text_version_review.csv](text_version_review.csv) records available
references for 20 bills. Its 79 version references include 19 introduced
references and one selected, undated Delaware Draft. Three Colorado API
introduced dates are placeholders; the exact PDFs' dates are verified from
the official bill pages' version tables. Raw provider dates are preserved.

The check identifies available versions and their dates. It does not establish
full-text equivalence with the corpus, introduction-time availability for all
fields, or the final model cohort.

## Using the text review

[source_text_review.csv](source_text_review.csv) keeps the source outcome,
recorded version date, introduced reference, explicit text-stage evidence and
check scope separate. Nine of the 20 reviewed headers describe later stages:
five source-Pending bills, three source-Passed bills and one source-Failed bill.
Those are grouped outcomes; the CSV preserves the exact raw status wording too.

Colorado HB26-1195 has the same February 11, 2026 date as the introduced reference,
but its source header says PREAMENDED. The official introduced PDF says INTRODUCED.
Date equality alone would not catch that difference. Three cached Colorado PDFs
were extracted fully; formatting and line numbers prevent interpreting normalized
text nonmatches as proof of substantive change. The remaining 17 sample records
do not have full-body comparisons. No row is marked as verified introduced text.

The notebook checks these sample rows and screens all 2,571 raw headers for
explicit stage labels. This is a conservative text screen, not complete version
verification. An unknown header does not establish introduction-time eligibility.
The source-row locator and review flags must not become predictor features.

| Use | Recommended treatment |
| --- | --- |
| Shared table and descriptive topic analysis | Keep the nine rows and their source values. Describe the deposited corpus and its mixed text versions. |
| Initial recorded-outcome classification | Keep the frozen source baseline for comparability. Document administrative status clues, especially chaptered text, rather than interpreting them as policy content that predicts passage. |
| Optional sensitivity comparison | The supervised analysis can compare metadata and text on the same retained rows and existing split plan, using one documented header/version rule. Removing only nine convenience-selected cases is not a corpus-wide leakage fix. |
| Introduction-time forecasting | Require verified inputs available at introduction. These nine texts are not verified for that use; absence of a flag does not qualify the other rows. |

This review applies no filtering, header removal, text replacement or outcome changes.
Removing administrative headings alone would not establish historical timing
for the remaining text or metadata.

## Outcome timing recommendation

The main comparison uses **recorded outcomes from frozen Zenodo v4**, identified
by MD5 `397a13c53e719e64e52725e7995fd8ca`. A uniform outcome observation date is
undocumented. Publication, text-coverage and validation dates describe different
events and do not supply that missing date.

The four later enactment observations remain separate from the model labels.
Updating only successfully matched Pending records would mix observation windows across the corpus. The
seven closed-session checks support keeping the existing Failed/Adjourned labels.
For the current recorded-status task, Pending remains a snapshot state. For a
future final enactment task, Pending and governor-stage cases remain unresolved,
not failed. Adopted resolutions and enacted statutes also need distinct treatment.

If the team later adds a separate outcome refresh, **October 19, 2026, end of day
in America/New_York** is a proposed event cutoff aligned with this pilot. It is
not an applied or team-approved cutoff. Such a comparison would need each
included bill's status through that date, separate retrieval times, explicit
unresolved/unmatched cases, and finality rules by state/session and measure type.
The current evidence supports 18 selected bills checked October 13–19, not a whole-corpus
October 19 target. A different agreed date can be used with the same requirements.

Shared preparation supplies linked source-validation evidence without changing
the supervised or topic-analysis methods.
