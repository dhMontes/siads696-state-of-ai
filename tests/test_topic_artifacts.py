"""Audit saved analysis artifacts against source data, independently of notebook assertions.

Run the notebook before this suite. Missing outputs are failures, not skipped tests.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import unittest

import nbformat
import numpy as np
import pandas as pd

from src.topic_analysis import split_categories

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/topic_analysis"


class TopicArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = pd.read_csv(ROOT / "data/raw/Final_Database.csv", dtype=str, keep_default_na=False)
        cls.raw.index = [str(i) for i in range(1, len(cls.raw) + 1)]
        cls.common = pd.read_csv(ROOT / "data/processed/common_intake/common_records.csv",
                                 dtype=str, keep_default_na=False).set_index("source_row")

    def test_all_notebook_cells_executed_without_errors(self):
        notebook = nbformat.read(ROOT / "notebooks/03_topic_analysis.ipynb", as_version=4)
        nbformat.validate(notebook)
        counts = []
        for cell in notebook.cells:
            if cell.cell_type == "code":
                counts.append(cell.execution_count)
                self.assertFalse(any(o.output_type == "error" for o in cell.outputs))
        self.assertEqual(counts, list(range(1, len(counts) + 1)))

    def test_state_counts_and_proportions_reconstruct_from_record_assignments(self):
        for prefix in ["baseline", "refined"]:
            assignments = pd.read_csv(OUT / f"{prefix}_document_topics.csv", dtype={"source_row": str})
            self.assertEqual(assignments.source_row.tolist(), self.common.index.tolist())
            self.assertTrue(assignments.source_row.is_unique)
            counts = pd.read_csv(OUT / f"{prefix}_state_topic_counts.csv", index_col=0)
            shares = pd.read_csv(OUT / f"{prefix}_state_topic_proportions.csv", index_col=0)
            expected = Counter(zip(assignments.Jurisdiction, assignments.dominant_topic))
            denominators = Counter(self.common.Jurisdiction)
            for state in counts.index:
                for topic in counts.columns:
                    self.assertEqual(counts.loc[state, topic], expected[state, int(topic)])
                    self.assertAlmostEqual(shares.loc[state, topic], expected[state, int(topic)] / denominators[state])
            self.assertEqual(int(counts.to_numpy().sum()), len(self.common))
            self.assertEqual(assignments.loc[assignments.source_row.eq("207"), "dominant_topic"].item(), -1)

    def test_multilabel_counts_reconstruct_from_original_categories(self):
        for prefix in ["baseline", "refined"]:
            assignments = pd.read_csv(OUT / f"{prefix}_document_topics.csv", dtype={"source_row": str})
            actual = pd.read_csv(OUT / f"{prefix}_topic_category_counts.csv", index_col=0)
            proportions = pd.read_csv(OUT / f"{prefix}_topic_category_proportions.csv", index_col=0)
            expected = Counter()
            totals = Counter(assignments.dominant_topic)
            for row in assignments.itertuples():
                for label in split_categories(self.raw.loc[row.source_row, "NCSL_Category"]) or ["[Uncategorized]"]:
                    expected[row.dominant_topic, label] += 1
            for topic in actual.index:
                for label in actual.columns:
                    self.assertEqual(actual.loc[topic, label], expected[topic, label])
                    self.assertAlmostEqual(proportions.loc[topic, label], expected[topic, label] / totals[topic])

    def test_representatives_are_actual_top_five_and_match_source(self):
        for prefix in ["baseline", "refined"]:
            reps = pd.read_csv(OUT / f"{prefix}_representative_bills.csv", dtype={"source_row": str})
            assignments = pd.read_csv(OUT / f"{prefix}_document_topics.csv", dtype={"source_row": str})
            self.assertEqual(len(reps), 40)
            for topic, group in reps.groupby("topic_id"):
                expected = assignments.sort_values(f"topic_{topic}_raw", ascending=False, kind="stable").head(5)
                self.assertEqual(group.source_row.tolist(), expected.source_row.tolist())
                np.testing.assert_allclose(group.topic_weight_raw, expected[f"topic_{topic}_raw"])
                for row in group.itertuples():
                    self.assertEqual(row.Bill_Number, self.raw.loc[row.source_row, "Bill_Number"])
                    self.assertEqual(row.NCSL_Summary_clean, self.common.loc[row.source_row, "NCSL_Summary_clean"])

    def test_all_evidence_spans_and_hashes_match_original_text(self):
        cases = pd.read_csv(OUT / "case_analysis.csv", dtype=str, keep_default_na=False)
        self.assertEqual(len(cases), 8)
        for row in cases.itertuples():
            text = self.raw.loc[row.source_row, "Bill_Text"]
            self.assertEqual(row.bill_text_sha256, hashlib.sha256(text.encode()).hexdigest())
            spans = json.loads(row.evidence_locations_json)
            excerpts = [text[s["start_char"]:s["end_char_exclusive"]] for s in spans]
            self.assertEqual(row.evidence, "\n\n[Next passage]\n\n".join(excerpts))

    def test_case_stability_summary_matches_exported_assignments(self):
        assignments = pd.read_csv(OUT / "case_assignments_all_runs.csv", dtype={"source_row": str})
        assignments = assignments.set_index(["run_id", "source_row"])
        pairs = pd.read_csv(OUT / "case_pair_stability.csv", dtype={"a": str, "b": str})
        for row in pairs.itertuples():
            a = assignments.loc[(row.run_id, row.a), "dominant_topic"]
            b = assignments.loc[(row.run_id, row.b), "dominant_topic"]
            self.assertEqual(row.same_dominant_topic, a >= 0 and a == b)
        summary = pd.read_csv(OUT / "case_stability_summary.csv", dtype={"a": str, "b": str})
        for row in summary.itertuples():
            group = pairs.loc[pairs.a.eq(row.a) & pairs.b.eq(row.b) & pairs.run_id.str.startswith(row.method.lower())]
            preserved = group.same_dominant_topic if row.expected_relation == "similar" else ~group.same_dominant_topic
            self.assertEqual(row.runs, len(group))
            self.assertEqual(row.preserved_runs, preserved.sum())

    def test_sponsor_counts_and_summary_dedup_population(self):
        counts = pd.read_csv(OUT / "baseline_topic_sponsor_summary.csv")
        self.assertEqual(counts.records.sum(), len(self.common))
        self.assertEqual(counts.bipartisan_records.sum(), pd.to_numeric(self.common.Bipartisan_Support).sum())
        audit = json.loads((OUT / "summary_dedup_audit.json").read_text())
        self.assertEqual(audit["unique_summaries"], self.common.NCSL_Summary_clean.nunique())
        self.assertEqual(audit["original_records"], len(self.common))

    def test_state_and_cohort_mean_shares_reconstruct_from_record_shares(self):
        years = pd.to_datetime(self.common.introduction_date_iso, format="%Y-%m-%d").dt.year
        for prefix in ["baseline", "refined"]:
            records = pd.read_csv(OUT / f"{prefix}_document_topics.csv", dtype={"source_row": str})
            records["introduction_year"] = records.source_row.map(years)
            shares = records.filter(regex=r"^topic_\d+_share$")
            assigned = shares.sum(axis=1).gt(0)
            for name, key in [("state", "Jurisdiction"), ("cohort", "introduction_year")]:
                saved = pd.read_csv(OUT / f"{prefix}_{name}_mean_topic_shares.csv", index_col=0)
                expected = shares[assigned].groupby(records.loc[assigned, key]).mean()
                np.testing.assert_allclose(saved.filter(like="_mean_share").to_numpy(), expected.to_numpy())
                self.assertEqual(saved.records.tolist(), records.groupby(key).size().tolist())
                self.assertEqual(int(saved.records.sum()), len(self.common))

    def test_k_selection_tables_cover_each_count_with_five_starts(self):
        for variant in ["baseline", "refined"]:
            table = pd.read_csv(OUT / f"{variant}_k_selection.csv")
            self.assertEqual(table.topics.tolist(), [5, 6, 7, 8, 9, 10, 11, 12])
            self.assertTrue(table.starts.eq(5).all())
        picks = json.loads((OUT / "run_metadata.json").read_text())["k_selection_rule_picks"]
        self.assertEqual(set(picks), {"Baseline", "Refined"})

    def test_topic_outcomes_reconstruct_from_assignments_and_status(self):
        from src.topic_analysis import recorded_outcomes
        records = pd.read_csv(OUT / "refined_document_topics.csv", dtype={"source_row": str})
        outcomes = recorded_outcomes(self.common.reset_index()).set_index(self.common.index)
        records = records.join(outcomes, on="source_row")
        bills = records.loc[records.outcome.ne("unresolved") & ~records.resolution & records.dominant_topic.ge(0)]
        table = pd.read_csv(OUT / "refined_topic_outcomes.csv").set_index("topic_id")
        for topic, group in bills.groupby("dominant_topic"):
            self.assertEqual(table.loc[topic, "resolved_bills"], len(group))
            self.assertEqual(table.loc[topic, "passed"], group.outcome.eq("passed").sum())

    def test_bill_families_span_required_jurisdictions(self):
        families = pd.read_csv(OUT / "bill_families.csv")
        members = pd.read_csv(OUT / "bill_family_members.csv", dtype={"source_row": str})
        self.assertTrue(families.jurisdictions.ge(4).all())
        self.assertEqual(members.groupby("family").Jurisdiction.nunique().sort_index().tolist(),
                         families.set_index("family").jurisdictions.sort_index().tolist())
        self.assertTrue(members.source_row.isin(self.common.index).all())

    def test_manifest_matches_current_source_code_and_review_files(self):
        metadata = json.loads((OUT / "run_metadata.json").read_text())
        paths = {"raw_sha256": "data/raw/Final_Database.csv",
                 "common_records_sha256": "data/processed/common_intake/common_records.csv",
                 "prepare_script_sha256": "src/prepare.py",
                 "analysis_script_sha256": "src/topic_analysis.py",
                 "review_sha256": "notebooks/topic_case_review.json", "labels_sha256": "notebooks/topic_labels.json"}
        for key, path in paths.items():
            self.assertEqual(metadata[key], hashlib.sha256((ROOT / path).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
