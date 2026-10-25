"""Refresh the report figures and tables from notebooks 03, 06 and 07."""

from pathlib import Path
import shutil

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOPIC_OUTPUTS = PROJECT_ROOT / "outputs" / "topic_analysis"
MODEL_OUTPUTS = PROJECT_ROOT / "outputs" / "model_evaluation"
FINAL_OUTPUTS = PROJECT_ROOT / "outputs" / "final_evaluation"
REPORT_ASSETS = PROJECT_ROOT / "report-assets"

COPIES = {
    MODEL_OUTPUTS / "family_comparison.png": "classifier_families.png",
    MODEL_OUTPUTS / "matched_svm_inputs.png": "svm_inputs.png",
    TOPIC_OUTPUTS / "refined_leading_words.png": "nmf_leading_words.png",
    TOPIC_OUTPUTS / "refined_state_mean_topic_shares.png": "nmf_state_topic_weights.png",
    TOPIC_OUTPUTS / "lda_leading_words.png": "lda_leading_words.png",
    TOPIC_OUTPUTS / "lda_state_mean_topic_weights.png": "lda_state_topic_weights.png",
    MODEL_OUTPUTS / "best_historical_candidate_per_family.csv": "historical_family_comparison.csv",
    FINAL_OUTPUTS / "scores.csv": "final_scores.csv",
    FINAL_OUTPUTS / "classification_report.csv": "final_classification_report.csv",
    FINAL_OUTPUTS / "confusion_matrix.png": "final_confusion_matrix.png",
}
TOPIC_RUNS = [
    "nmf_baseline_k8_seed42_nndsvda",
    "nmf_legal_k8_seed42_nndsvda",
    "lda_baseline_k8_seed42_batch",
]
TOPIC_COLUMNS = [
    "run_id", "method", "variant", "topics",
    "document_npmi_top12", "top12_term_diversity", "mean_top12_jaccard",
]


def main():
    comparison_file = TOPIC_OUTPUTS / "model_comparison.csv"
    required_files = [*COPIES, comparison_file]
    missing = [path.relative_to(PROJECT_ROOT) for path in required_files if not path.is_file()]
    if missing:
        raise SystemExit(
            "Run notebooks 03, 06 and 07 before exporting report assets. Missing:\n"
            + "\n".join(str(path) for path in missing)
        )

    # Keep the saved precision and the same three eight-topic runs as the report table.
    comparison = pd.read_csv(comparison_file, dtype=str, keep_default_na=False)
    topic_table = comparison.set_index("run_id", drop=False).loc[TOPIC_RUNS, TOPIC_COLUMNS]

    REPORT_ASSETS.mkdir(exist_ok=True)
    for source, filename in COPIES.items():
        shutil.copyfile(source, REPORT_ASSETS / filename)
    topic_table.to_csv(REPORT_ASSETS / "topic_method_comparison.csv", index=False)
    print("Updated seven figures and four tables in report-assets/.")


if __name__ == "__main__":
    main()
