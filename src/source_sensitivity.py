"""Offline, exploratory comparisons using the saved pre-2026 source audit.

The original final evaluation is separate. These helpers never load its models
or predictions, and reject 2026 rows before fitting supplemental models.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

from .classification_helpers import create_pipeline
from .topic_analysis import LEGAL_STOPWORDS


CLASSES = ["Failed", "Passed", "Pending"]
FEATURE_GROUPS = {
    "categorical": ["measure_code", "Jurisdiction", "State_Political_Control"],
    "numeric": ["D_Count", "R_Count", "Other_Count", "Unknown_Count", "Total_Sponsors"],
    "ratio": ["Democrat_Sponsor_Ratio", "Republican_Sponsor_Ratio"],
    "binary": ["Bipartisan_Support"],
}
FEATURES = [column for group in FEATURE_GROUPS.values() for column in group]
NO_SPONSORS = {**FEATURE_GROUPS, "numeric": [], "ratio": [], "binary": []}
NO_STATE = {
    **FEATURE_GROUPS,
    "categorical": [c for c in FEATURE_GROUPS["categorical"] if c != "Jurisdiction"],
}
MODEL_PARAMS = {"C": 10, "class_weight": "balanced", "max_iter": 20000, "random_state": 42}
TFIDF_PARAMS = {
    "max_features": 5000, "ngram_range": (1, 2), "min_df": 2,
    "max_df": 0.95, "sublinear_tf": True, "stop_words": sorted(LEGAL_STOPWORDS),
}
STATUS_LABELS = {
    "Failed": "Failed", "Vetoed": "Failed", "Enacted": "Passed", "Adopted": "Passed",
    "Pending": "Pending", "ToGovernor": "Pending", "OverridePending": "Pending",
}


def load_cohort(repo):
    """Join verified ordinary bills one-to-one and apply dated audited labels.

    Original 2019–2025 source dates establish eligibility. Training corrections
    stop at 2024-12-31 and evaluation corrections at 2025-12-31. Unresolved rows
    retain the published label; the audit does not certify those labels.
    """
    repo = Path(repo)
    source = pd.read_csv(repo / "data/processed/common_records.csv", usecols=[
        "source_row", "Bill_Number", "Bill_Status", "Introduction_Date",
        "Bill_Text_clean", "NCSL_Summary_clean", *FEATURES,
    ])
    source["source_date"] = pd.to_datetime(source.Introduction_Date, errors="coerce")
    source = source.loc[source.source_date.dt.year.between(2019, 2025)].copy()
    prefix = source.Bill_Number.str.extract(r"^\s*([A-Za-z]+)", expand=False).str.upper()
    source = source.loc[~(prefix.str.len().ge(2) & prefix.str[-1].isin(["R", "M"]))].copy()
    status = source.Bill_Status.str.split(" - ").str[0].str.replace(r"\s+", "", regex=True)
    source["original_label"] = status.map(STATUS_LABELS)

    audit = pd.read_csv(repo / "data/validation/source_outcome_audit.csv", keep_default_na=False)
    verified = audit.verified_identity.astype(str).str.lower().isin(["true", "1"])
    data = source.merge(audit.loc[verified], on="source_row", how="inner", validate="one_to_one")
    if data.empty or data.original_label.isna().any():
        raise ValueError("The matched cohort is empty or contains unmapped source outcomes.")
    session_year = pd.to_numeric(data.source_identity.str.slice(2, 6), errors="coerce")
    if session_year.isna().any() or session_year.ge(2026).any():
        raise ValueError("Matched audit identities must belong to sessions before 2026.")
    if not pd.to_datetime(data.source_intro_date).eq(data.source_date).all():
        raise ValueError("Audit source dates do not match the prepared rows.")
    if not data.source_label.eq(data.original_label).all():
        raise ValueError("Audit source labels do not match the prepared rows.")

    corrected_date = pd.to_datetime(data.corrected_intro_date, errors="coerce")
    if (data.corrected_intro_date.ne("") & corrected_date.isna()).any():
        raise ValueError("An introduction-date correction is not a valid date.")
    data["analysis_date"] = corrected_date.fillna(data.source_date)
    data = data.loc[data.analysis_date.dt.year.between(2019, 2025)].copy()
    data["year"] = data.analysis_date.dt.year
    data["split"] = np.where(data.year.eq(2025), "evaluation", "training")
    data["date_changed"] = data.analysis_date.ne(data.source_date)
    data["cohort_changed"] = data.year.ne(data.source_date.dt.year)
    proposed = data.corrected_train_label.where(data.split.eq("training"), data.corrected_eval_label)
    has_repair = proposed.ne("")
    evidence_date = pd.to_datetime(data.correction_evidence_date, errors="coerce")
    cutoff = pd.to_datetime(np.where(data.split.eq("training"), "2024-12-31", "2025-12-31"))
    if not pd.to_datetime(data.cutoff).eq(cutoff).all():
        raise ValueError("An audit cutoff differs from the training/evaluation cutoff.")
    if (has_repair & (~proposed.isin(CLASSES) | evidence_date.isna() | evidence_date.gt(cutoff))).any():
        raise ValueError("A label repair is invalid or uses evidence beyond its split cutoff.")
    data["repaired_label"] = proposed.where(has_repair, data.original_label)
    data["label_changed"] = data.repaired_label.ne(data.original_label)
    data["independently_resolved"] = data.independently_resolved.astype(str).str.lower().isin(["true", "1"])
    if (data.independently_resolved & ~has_repair).any():
        raise ValueError("An independently resolved row needs a dated audited label.")
    return data.sort_values("source_row").reset_index(drop=True)


def screen_text_versions(data):
    """Keep source text versions dated by the 2024/2025 split cutoff.

    This screens the saved text version; it does not reconstruct historical
    features or impose earlier 2022–2024 fold cutoffs.
    """
    version = pd.to_datetime(data.source_version_date, errors="coerce")
    eligible = version.notna() & version.le(pd.to_datetime(data.cutoff))
    return data.loc[eligible].copy(), data.loc[~eligible].copy()


def score_predictions(truth, predicted):
    """Score observed true classes and retain all three per-class diagnostics."""
    precision, recall, f1, support = precision_recall_fscore_support(
        truth, predicted, labels=CLASSES, zero_division=0,
    )
    scores = {
        "Rows": len(truth), "Accuracy": accuracy_score(truth, predicted),
        "Balanced_accuracy": recall[support > 0].mean(),
        "Macro_F1": f1_score(truth, predicted, labels=np.unique(truth), average="macro", zero_division=0),
        "Scored_classes": len(np.unique(truth)),
    }
    by_class = [
        {"Class": name, "Precision": precision[i], "Recall": recall[i],
         "F1": f1[i], "Support": int(support[i])}
        for i, name in enumerate(CLASSES)
    ]
    return scores, by_class


def compare_models(training, evaluation, configurations, comparison, include_resolved=False):
    """Fit explicit configurations on identical rows and return three tidy tables.

    Each configuration provides a name and optional text_column, feature_groups,
    target, or C. Imputation, scaling, encoding, and vocabulary fit on training
    rows through the same create_pipeline helper as the main analysis.
    """
    if training.empty or evaluation.empty:
        raise ValueError("Both training and evaluation rows are required.")
    if not training.year.between(2019, 2025).all() or not evaluation.year.between(2019, 2025).all():
        raise ValueError("Supplemental comparisons cannot use rows outside 2019–2025.")
    if training.year.max() >= evaluation.year.min():
        raise ValueError("Training years must precede evaluation years.")
    if set(training.source_row) & set(evaluation.source_row):
        raise ValueError("Training and evaluation rows overlap.")
    scores, class_scores, predictions = [], [], []
    for config in configurations:
        name = config["name"]
        groups = config.get("feature_groups", FEATURE_GROUPS)
        text_column = config.get("text_column")
        target = config.get("target", "repaired_label")
        columns = [c for group in groups.values() for c in group]
        if text_column:
            columns.append(text_column)
        model = create_pipeline(
            model_type="linear_svm", feature_set="features", feature_groups=groups,
            feature_sets={"features": text_column}, tfidf_params=TFIDF_PARAMS,
            model_params={**MODEL_PARAMS, "C": config.get("C", 10)},
        )
        model.fit(training[columns], training[target])
        predicted = model.predict(evaluation[columns])
        training_accuracy = accuracy_score(training[target], model.predict(training[columns]))
        identity = {"Comparison": comparison, "Model": name, "Year": int(evaluation.year.min())}
        prediction = evaluation[["source_row", "Bill_Number", "Jurisdiction",
                                 "original_label", "repaired_label", "independently_resolved"]].copy()
        prediction = prediction.assign(**identity, Predicted=predicted)
        predictions.append(prediction)
        subsets = {"All matched bills": np.ones(len(evaluation), dtype=bool)}
        if include_resolved:
            subsets["Independently resolved"] = evaluation.independently_resolved.to_numpy()
        for subset, mask in subsets.items():
            if not mask.any():
                continue
            summary, classes = score_predictions(evaluation.repaired_label.to_numpy()[mask], predicted[mask])
            metadata = {**identity, "Subset": subset, "Training_rows": len(training)}
            scores.append({**metadata, "Training_accuracy": training_accuracy, **summary})
            class_scores.extend({**metadata, **row} for row in classes)
    return pd.DataFrame(scores), pd.DataFrame(class_scores), pd.concat(predictions, ignore_index=True)


def paired_state_bootstrap(predictions, original="Original labels", repaired="Repaired labels",
                           resamples=2000, seed=42):
    """Resample states, retaining paired fixed predictions for every selected bill.

    The 95% percentile interval conditions on fitted models and this development
    cohort. It omits training uncertainty, audit uncertainty, and model selection.
    """
    baseline = predictions.loc[predictions.Model.eq(original)].set_index("source_row")
    updated = predictions.loc[predictions.Model.eq(repaired)].set_index("source_row")
    if baseline.index.has_duplicates or updated.index.has_duplicates or set(baseline.index) != set(updated.index):
        raise ValueError("The paired comparison requires identical unique source rows.")
    updated = updated.loc[baseline.index]
    if not baseline.repaired_label.equals(updated.repaired_label):
        raise ValueError("The paired models must use the same evaluation labels.")
    codes = {label: i for i, label in enumerate(CLASSES)}
    truth = baseline.repaired_label.map(codes).to_numpy()
    original_pred = baseline.Predicted.map(codes).to_numpy()
    repaired_pred = updated.Predicted.map(codes).to_numpy()

    def macro_f1(actual, predicted):
        matrix = np.bincount(actual * 3 + predicted, minlength=9).reshape(3, 3)
        denominator = matrix.sum(axis=0) + matrix.sum(axis=1)
        return np.divide(2 * np.diag(matrix), denominator, out=np.zeros(3), where=denominator != 0).mean()

    groups = [np.flatnonzero(baseline.Jurisdiction.eq(state).to_numpy())
              for state in sorted(baseline.Jurisdiction.unique())]
    random = np.random.default_rng(seed)
    differences = []
    for _ in range(resamples):
        rows = np.concatenate([groups[i] for i in random.integers(0, len(groups), size=len(groups))])
        differences.append(macro_f1(truth[rows], repaired_pred[rows]) - macro_f1(truth[rows], original_pred[rows]))
    lower, upper = np.quantile(differences, [0.025, 0.975])
    return pd.DataFrame([{
        "Comparison": "Label repair", "Method": "Paired state-cluster bootstrap",
        "Resamples": resamples, "Seed": seed, "State_clusters": len(groups),
        "Macro_F1_difference": macro_f1(truth, repaired_pred) - macro_f1(truth, original_pred),
        "Lower_95": lower, "Upper_95": upper,
        "Predictions_changed": int((original_pred != repaired_pred).sum()),
    }])
