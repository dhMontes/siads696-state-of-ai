# Source validation

These tables document source checks without changing the published
data or main-model labels. The original sample contains 18 bills, six each from
California, Colorado and Texas. Two sponsor cases extend the identity and
text-version checks to 20 records. This convenience sample does not estimate
error rates for the full corpus.

[Notebook 04](../../notebooks/04_source_validation.ipynb) compares the saved
observations and screens the raw text headers. It runs offline with the existing
project dependencies; no API key or new source request is needed.

The larger [source-outcome audit](source_outcome_audit.csv) matches 1,523 ordinary
bills to LegiScan histories retrieved October 25, 2026. [Notebook 08](../../notebooks/08_source_sensitivity.ipynb)
uses this saved evidence for a separate, retrospective development comparison.
It supports 39 Pending-to-Passed corrections: 18 through the training cutoff of
December 31, 2024 and 21 through the evaluation cutoff of December 31, 2025.
Five veto cases with pending consideration lack dated closure evidence by their
cutoffs and retain their source labels. A current session-closure flag is not a
historical closure date. Of the matched bills, 311 have independently resolved
outcomes; the other 1,212 retain unverified source labels.

The audit stores the source row, matched bill/session IDs, source URL, retrieval
time, cutoff, outcome evidence and text-version dates. A blank corrected label
means no conclusive update was applied. Notebook 08 reproduces the comparisons
from these saved observations without API access; it does not rerun live retrieval
or replace the original 2026 evaluation. LegiScan supplies the linked bill histories;
the source corpus remains the Zenodo dataset described in the root README.

## Files

| File | Contents and check date |
| --- | --- |
| [bill_status_observations.csv](bill_status_observations.csv) | October 13, 2026 official-source observations for 18 bills, including coverage limits and unresolved conflicts. |
| [legiscan_comparison.csv](legiscan_comparison.csv) | October 19 LegiScan bill/session identities, provider stages and history actions for those 18 records. |
| [closed_session_review.csv](closed_session_review.csv) | October 19 official-history and session-closure review of seven intermediate-stage bills. |
| [deduplication_review.csv](deduplication_review.csv) | Four removed-to-retained source-row pairs from shared preparation. |
| [sponsor_review.csv](sponsor_review.csv) | October 19 official-source checks of two duplicate pairs with conflicting sponsor lists. |
| [sponsor_resolution.csv](sponsor_resolution.csv) | Current rosters for those two cases, with historical text versions and sponsor-role differences kept separate. |
| [text_version_review.csv](text_version_review.csv) | References for 20 records: 79 available versions, 19 introduced references and one undated Delaware Draft. |
| [source_text_review.csv](source_text_review.csv) | October 20 date/header review of those 20 source texts, linked to the raw file and saved October 19 version evidence. |
| [source_outcome_audit.csv](source_outcome_audit.csv) | October 25 LegiScan observations for 1,523 matched pre-2026 ordinary bills, with dated outcome evidence and explicit unresolved cases. |

`source_row` is the one-based record position in `data/raw/Final_Database.csv`,
not a unique-bill identifier or model input. The raw file preserves the published
`Final_Database_10.csv`: 2,571 records, 29 fields and MD5
`397a13c53e719e64e52725e7995fd8ca`. Bill identity also requires state and session.

## Reading the fields

| Fields | Meaning |
| --- | --- |
| `source_status`, `Bill_Status` | Outcome recorded in the preserved corpus. |
| `api_stage_code`, `api_stage`, `api_stage_date` | LegiScan's stage and stage date. Code 4 is called Passed; it does not alone establish enactment. |
| `api_first_history_date` | First available event, which can be pre-session filing rather than the source introduction date. |
| `api_last_action_date`, `last_action_date` | Latest available action, not automatically an enactment or failure date. |
| `session_sine_die`, `session_closed_date`, `outcome_review` | Provider closure flag, verified closure date and case-level outcome interpretation. Texas's inferred basis is stated explicitly. |
| `signing_or_chaptering_evidence` | Explicit signing or chaptering history, separate from the provider stage. |
| `review_state`, `*_checked_at_utc`, `checked_at_utc` | Observation coverage and check time, separate from event dates or model eligibility. |
| `api_date_raw`, `document_date`, `date_basis` | Original provider date, verified document date and the basis for that date. |
| `current_api_roster`, `introduced_author_list`, `later_or_observed_author_list` | Current sponsor metadata versus author lists printed in particular text versions. |

## Findings and outcome dates

All 20 reviewed records match the checked bill and session identities. The other
2,547 prepared records have not received these detailed text/sponsor checks. Seven intermediate-stage
bills in closed sessions already have source status `Failed - Adjourned`; the
checks support keeping those labels. Four source-Pending bills have later
signing or chaptering evidence, which remains separate from the model labels.

California AB2291 has no established terminal outcome in this check. Colorado
HB26-1210's API veto agrees with its history observation; the conflicting
official-page Signed Act/summary wording remains recorded. Texas HB4448's source
short title is misleading, although its raw header supports the bill identity.
Notebook 04 shows these comparisons and their coverage limits.

The main comparison keeps the published outcome labels. A uniform outcome
observation date is undocumented; publication and retrieval dates do not supply
it. Pending remains an unresolved snapshot state. Updating only the successfully
matched bills would mix observation windows across the corpus.

## Duplicate and sponsor checks

The four removed records share cleaned text and encoded bill identifiers with
their retained partners. These observed pairs do not establish that identical
text always identifies the same bill elsewhere in the corpus.

The sponsor tables distinguish the original conflicts from later roster checks:

- California SCR 82: the introduced text names Niello alone; its June 11, 2026
  amendment adds Fong and Sharp-Collins. The retained source list differs from
  that verified three-person roster.
- Delaware SCR 18: the current roster has 20 sponsors. The undated API Draft
  prints 19 names, omitting Vanderwende; the retained six-name source list also
  differs. Current rosters and historical author blocks are separate evidence.

These checks preserve official links, check times and sponsor-role definitions.
They do not replace the source lists or the prepared sponsor features.

## Using the text review

Nine of the 20 reviewed headers show later stages: five source-Pending, three
source-Passed and one source-Failed. Dates alone are insufficient: Colorado
HB26-1195 matches the introduced reference's February 11, 2026 date, but its
source header says PREAMENDED while the official introduced PDF says INTRODUCED.

Three Colorado PDFs have full-body comparisons; the other 17 records do not.
Formatting differences prevent treating normalized text nonmatches as proof of
substantive changes. No reviewed row is verified as introduced text. The version
table preserves three placeholder API dates separately from verified PDF dates.

Notebook 04 also screens all 2,571 raw headers for explicit stage labels. This
does not verify every text version or establish introduction-time availability.
The checks support retrospective interpretation of the recorded-status task;
neither an absent flag nor removing administrative headings proves that a bill
was available in that form at introduction. Source locators and review flags
are not predictor features. These tables apply no filtering, text replacement
or outcome changes.

## Sources and attribution

- Bhargava and Soliman, [U.S. State AI Legislation Corpus v4](https://zenodo.org/records/20781731).
- [LegiScan](https://legiscan.com/) API metadata/history, retrieved October 19 and 25,
  2026, under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
  The comparison tables select, rename and reorganize provider fields, link them
  to source rows and add official-source observations. Stage labels follow the
  [API manual](https://api.legiscan.com/dl/LegiScan_API_User_Manual.pdf),
  Status/Progress section, printed page 42.
- Official bill-history links and check times appear in the CSVs. Session-closure
  evidence uses the [Texas Legislative Reference Library post-session FAQ](https://www.lrl.texas.gov/whatsNew/client/index.cfm/2025/6/3/Whats-Next-PostSession-FAQ-and-Bill-Statistics-89th-RS)
  and [Colorado extraordinary-session journal](https://content.leg.colorado.gov/sites/default/files/2025_house_journal.pdf),
  printed page 76 (PDF page 80). The seven histories were checked October 19.
  Texas closure is inferred from incomplete histories and the official closure
  rule; Colorado HB25B-1008's page records Lost. The Texas rule was checked in
  available official FAQ web text; its linked page was inaccessible.
