"""Regression checks for analysis failures that can silently alter conclusions."""
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.prepare import TEXT_COLUMNS, clean_text
from src.topic_analysis import (
    GEO_PATTERN, dominant_topics, distributions, split_categories,
    stability_report, unit_mass_weights, validate_intake, check_topic_identity,
    mean_topic_shares, recommend_k, introduction_years, distinct_solutions,
    recorded_outcomes, mantel_haenszel, wilson_interval,
)


class TopicAnalysisTests(unittest.TestCase):
    def test_outcomes_map_status_and_flag_resolutions_and_memorials(self):
        work = pd.DataFrame({"Bill_Status": ["Enacted", "Failed - Adjourned", "Pending - Carryover", "Vetoed",
                                             "Adopted", "To Governor"],
                             "Bill_Number": ["H 1", "SB 2", "HSB 3", "SCR 4", "HJM 5", "LD 6"]})
        result = recorded_outcomes(work)
        self.assertEqual(result.outcome.tolist(), ["passed", "failed", "unresolved", "failed", "passed", "unresolved"])
        self.assertEqual(result.resolution.tolist(), [False, False, False, True, True, False])

    def test_mantel_haenszel_pools_strata_and_skips_uninformative_ones(self):
        # Two strata with odds ratio 16 each; a third stratum has no unexposed records.
        exposed = np.array([1, 1, 1, 1, 1, 0, 0, 0, 0, 0] * 2 + [1, 1], dtype=bool)
        y = np.array([1, 1, 1, 1, 0, 1, 0, 0, 0, 0] * 2 + [1, 0], dtype=bool)
        strata = ["a"] * 10 + ["b"] * 10 + ["c"] * 2
        ratio, p = mantel_haenszel(y, exposed, strata)
        self.assertAlmostEqual(ratio, 16.0)
        self.assertTrue(0 < p < 1)
        low, high = wilson_interval(4, 5)
        self.assertTrue(low < .8 < high)

    def test_duplicate_solutions_are_counted_once_within_the_same_k(self):
        same = np.array([[1., 0.], [0., 1.], [1., 0.], [0., 1.]])
        other = np.array([[1., 0.], [1., 0.], [0., 1.], [0., 1.]])
        bundles = {"nmf_baseline_k2_seed42_nndsvda": {"W": same},
                   "nmf_baseline_k2_seed7_nndsvda": {"W": same * 3},
                   "nmf_baseline_k2_seed7_random": {"W": other},
                   "nmf_baseline_k3_seed42_nndsvda": {"W": same}}
        kept, collapsed = distinct_solutions(bundles)
        self.assertEqual(list(kept), ["nmf_baseline_k2_seed42_nndsvda", "nmf_baseline_k2_seed7_random",
                                      "nmf_baseline_k3_seed42_nndsvda"])
        self.assertEqual(collapsed.to_dict("records")[0]["duplicate_of"], "nmf_baseline_k2_seed42_nndsvda")

    def test_mean_shares_average_normalized_weights_and_skip_zero_rows(self):
        W = np.array([[1., 3.], [0., 0.], [2., 2.], [0., 5.]])
        means, counts = mean_topic_shares(W, pd.Series(["A", "A", "B", "B"], name="Jurisdiction"))
        np.testing.assert_allclose(means.loc["A"], [.25, .75])
        np.testing.assert_allclose(means.loc["B"], [.25, .75])
        self.assertEqual(counts.records.tolist(), [2, 2])
        self.assertEqual(counts.assigned_records.tolist(), [1, 2])

    def test_cohorts_use_introduction_dates_not_ncsl_year(self):
        work = pd.DataFrame({"Year": ["2025", "2025", "2026"],
                             "introduction_date_iso": ["2024-12-31", "", "2026-04-02"]})
        self.assertEqual(introduction_years(work).tolist(), [2024, pd.NA, 2026])

    def test_k_rule_prefers_stability_within_npmi_tolerance(self):
        table = pd.DataFrame({"topics": [8, 9, 10, 12], "npmi_mean": [.225, .232, .231, .200],
                              "matched_cosine_mean": [.868, .851, .921, .990]})
        self.assertEqual(recommend_k(table), 10)
        self.assertEqual(recommend_k(table.assign(matched_cosine_mean=.9)), 8)

    def test_multilabel_separators_deduplication_and_slashes(self):
        self.assertEqual(split_categories(
            "Health Use; Private Sector Use, Health Use; Effect on Labor/Employment"),
            ["Effect on Labor/Employment", "Health Use", "Private Sector Use"])

    def test_spillover_is_not_treated_as_categories(self):
        self.assertEqual(split_categories(
            "Health Use, Notification Associated Bills: FL S 344 - Identical; Studies"),
            ["Health Use", "Notification"])
        self.assertEqual(split_categories("Summary: Relates to schools, provides for reporting"), [])
        self.assertEqual(split_categories("Associated Bills: FL H 1007 - Similar"), [])

    def test_observed_missing_separator_and_alias_repairs(self):
        self.assertEqual(split_categories("Effect on Labor/Employment Studies; Government use"),
                         ["Effect on Labor/Employment", "Government Use", "Studies"])
        self.assertEqual(split_categories("Notification Private Sector Use; Health use"),
                         ["Health Use", "Notification", "Private Sector Use"])

    def test_geography_removes_complete_names_only(self):
        text = GEO_PATTERN.sub(" ", "West Virginia and North Carolina use a new school in a district.")
        self.assertNotIn("West", text)
        self.assertNotIn("North", text)
        self.assertIn("new school in a district", text)

    def test_zero_weight_document_is_unassigned(self):
        np.testing.assert_array_equal(dominant_topics(np.array([[0., 0.], [0., 1.]])), [-1, 1])

    def test_state_denominators_include_unassigned_and_categories_overlap(self):
        work = pd.DataFrame({"source_row": ["1", "2", "3"], "Jurisdiction": ["A", "A", "B"],
            "Bill_Number": ["H 1", "H 2", "S 1"], "Year": ["2025"] * 3,
            "NCSL_Category": ["Health Use; Notification", "", "Health Use"],
            "categories": [["Health Use", "Notification"], [], ["Health Use"]]})
        # Unit-test the arithmetic; test_topic_artifacts checks actual CSV writes.
        with patch.object(pd.DataFrame, "to_csv"):
            counts, shares, categories, proportions = distributions(
                work, np.array([[1., 0.], [0., 0.], [0., 1.]]), Path("unused-unit-test-output"))
            self.assertEqual(shares.loc["A", 0], .5)
            self.assertEqual(shares.loc["A", -1], .5)
            self.assertEqual(proportions.loc[0, "Health Use"], 1.)
            self.assertEqual(proportions.loc[0, "Notification"], 1.)
            self.assertEqual(counts.to_numpy().sum(), 3)
            self.assertEqual(categories.loc[-1, "[Uncategorized]"], 1)

    def intake_fixture(self):
        raw = pd.DataFrame({column: [" Ａ  summary\nvalue ", "second"] for column in TEXT_COLUMNS})
        prepared = raw.copy()
        prepared["source_row"] = ["1", "2"]
        for column in TEXT_COLUMNS:
            prepared[column + "_clean"] = raw[column].map(clean_text)
        return prepared, raw

    def test_valid_preparation_is_accepted(self):
        prepared, raw = self.intake_fixture()
        validate_intake(prepared, raw)

    def test_edited_model_input_is_rejected(self):
        prepared, raw = self.intake_fixture()
        prepared.loc[0, "NCSL_Summary_clean"] = "unrelated replacement"
        with self.assertRaisesRegex(ValueError, "Run python src/prepare.py"):
            validate_intake(prepared, raw)

    def test_reordered_source_indices_are_rejected(self):
        prepared, raw = self.intake_fixture()
        prepared["source_row"] = ["2", "1"]
        with self.assertRaises(ValueError):
            validate_intake(prepared, raw)

    def test_modified_original_text_is_rejected(self):
        prepared, raw = self.intake_fixture()
        prepared.loc[0, "Bill_Text"] = "wrong bill"
        with self.assertRaises(ValueError):
            validate_intake(prepared, raw)

    def test_dedup_requires_last_matching_fulltext_and_preserves_gaps(self):
        prepared, raw = self.intake_fixture()
        raw.loc[1, "Bill_Text"] = raw.loc[0, "Bill_Text"].replace("\n", " ")
        prepared.loc[1, "Bill_Text"] = raw.loc[1, "Bill_Text"]
        prepared.loc[1, "Bill_Text_clean"] = clean_text(raw.loc[1, "Bill_Text"])
        audit = validate_intake(prepared.iloc[[1]], raw)
        self.assertEqual(audit[0]["removed_source_row"], "1")
        self.assertEqual(audit[0]["retained_source_row"], "2")
        self.assertFalse(audit[0]["raw_text_identical"])
        with self.assertRaises(ValueError):
            validate_intake(prepared.iloc[[0]], raw)

    def test_nonduplicate_deletion_is_rejected(self):
        prepared, raw = self.intake_fixture()
        with self.assertRaises(ValueError):
            validate_intake(prepared.iloc[[1]], raw)

    def test_sponsor_quote_changes_allowed_but_party_changes_rejected(self):
        prepared, raw = self.intake_fixture()
        raw["Sponsor_Party"] = ['["R"]', '["D"]']
        prepared["Sponsor_Party"] = ["['R']", "['D']"]
        validate_intake(prepared, raw)
        prepared.loc[0, "Sponsor_Party"] = "['D']"
        with self.assertRaises(ValueError):
            validate_intake(prepared, raw)

    def test_topic_permutation_requires_review(self):
        from types import SimpleNamespace
        vectorizer = SimpleNamespace(get_feature_names_out=lambda: np.array(["alpha", "beta"]))
        old = dict(vectorizer=vectorizer, model=SimpleNamespace(n_components=2, components_=np.eye(2)))
        new = dict(vectorizer=vectorizer, model=SimpleNamespace(n_components=2, components_=np.eye(2)[::-1]))
        with self.assertRaisesRegex(ValueError, "numbering changed"):
            check_topic_identity(new, [], old)
        self.assertEqual(len(check_topic_identity(new, [], old, [1, 0])), 2)
        with self.assertRaisesRegex(ValueError, "content changed"):
            check_topic_identity(new, [{"topic_id": 0, "expected_keywords": ["alpha", "beta"]}])

    def test_disabling_lda_cannot_report_previous_lda_results(self):
        data = pd.DataFrame([{"run_id": "nmf_baseline_k8_seed42_nndsvda", "a": "1", "b": "2",
            "expected_relation": "similar", "same_dominant_topic": True}])
        report = stability_report(data)
        self.assertIn("LDA: not run in this execution", report)
        self.assertIn("1/1", report)
        self.assertNotIn("LDA: 4 distinct solutions", report)

    def test_failed_relationship_is_not_reported_as_stable(self):
        data = pd.DataFrame([{"run_id": "nmf_baseline_k8_seed42_nndsvda", "a": "1", "b": "2",
            "expected_relation": "similar", "same_dominant_topic": False}])
        self.assertIn("Shared dominant topic in 0/1", stability_report(data))

    def test_unit_mass_convention_is_invariant_to_factor_rescaling(self):
        W = np.array([[1., 2.], [0., 0.]])
        H = np.array([[1000., 0.], [0., 1.]])
        factors = np.array([.01, 100.])
        alternative_W, alternative_H = W / factors, H * factors[:, None]
        np.testing.assert_allclose(W @ H, alternative_W @ alternative_H)
        self.assertNotEqual(W[0].argmax(), alternative_W[0].argmax())
        np.testing.assert_allclose(unit_mass_weights(W, H), unit_mass_weights(alternative_W, alternative_H))
        np.testing.assert_array_equal(dominant_topics(unit_mass_weights(W, H)), [0, -1])


if __name__ == "__main__":
    unittest.main()
