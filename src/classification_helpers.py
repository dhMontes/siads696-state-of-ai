"""Classification helper functions to simplify baseline model generation and evaluation"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import (
    OneHotEncoder,
    StandardScaler,
    FunctionTransformer,
    LabelEncoder
)
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    precision_score,
    recall_score,
    balanced_accuracy_score,
    f1_score
)


from xgboost import XGBClassifier

RANDOM_STATE = 42

def flatten_text(values):
    """Convert a single-column array into a 1D text array."""
    return np.asarray(values).ravel().astype(str)

def create_preprocessor(
    feature_set,
    model_type,
    feature_groups,
    feature_sets,
    tfidf_params=None,
):
    """Create preprocessing for any supported model/feature set."""

    if feature_set not in feature_sets:
        raise ValueError(f"Unknown feature set: {feature_set}")

    if model_type not in {
        "logistic_regression", "linear_svm", "xgboost"
    }:
        raise ValueError(f"Unknown model: {model_type}")

    is_tree_model = model_type == "xgboost"

    categorical_transformer = OneHotEncoder(
        handle_unknown="ignore"
    )

    numeric_steps = [
        ("imputer", SimpleImputer(
            strategy="constant",
            fill_value=0,
            add_indicator=True,
        ))
    ]

    if not is_tree_model:
        numeric_steps.append(
            ("scaler", StandardScaler())
        )

    numeric_transformer = Pipeline(numeric_steps)

    binary_transformer = SimpleImputer(
        strategy="most_frequent"
    )

    transformers = [
        (
            "categorical",
            categorical_transformer,
            feature_groups["categorical"],
        ),
        (
            "numeric",
            numeric_transformer,
            feature_groups["numeric"],
        ),
        (
            "ratio",
            Pipeline(numeric_steps),
            feature_groups["ratio"],
        ),
        (
            "binary",
            binary_transformer,
            feature_groups["binary"],
        ),
    ]

    text_column = feature_sets[feature_set]

    if text_column is not None:
        text_transformer = Pipeline([
            ("imputer", SimpleImputer(
                strategy="constant",
                fill_value=""
            )),
            ("flatten", FunctionTransformer(
                flatten_text, validate=False
            )),
            ("tfidf", TfidfVectorizer(
                **(tfidf_params or {})
            )),
        ])

        transformers.append(
            ("text", text_transformer, [text_column])
        )

    return ColumnTransformer(
        transformers=transformers,
        remainder="drop",
        sparse_threshold=1.0,
    )

def create_model(
    model_type,
    model_params=None,
    n_classes=None,
):
    """Initialize a classifier with baseline settings."""

    if model_type == "logistic_regression":
        model = LogisticRegression(
            C=1.0,
            l1_ratio=0,
            solver="lbfgs",
            class_weight=None,
            max_iter=2000,
            random_state=RANDOM_STATE,
        )

    elif model_type == "linear_svm":
        model = LinearSVC(
            C=1.0,
            penalty="l2",
            loss="squared_hinge",
            dual="auto",
            class_weight=None,
            max_iter=5000,
            random_state=RANDOM_STATE,
        )

    elif model_type == "xgboost":
        if n_classes is None:
            raise ValueError(
                "n_classes is required for XGBoost."
            )

        model = XGBClassifier(
            objective="multi:softprob",
            num_class=n_classes,
            n_estimators=100,
            max_depth=3,
            learning_rate=0.1,
            subsample=1.0,
            colsample_bytree=1.0,
            min_child_weight=1,
            reg_lambda=1.0,
            tree_method="hist",
            eval_metric="mlogloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )

    else:
        raise ValueError(f"Unknown model: {model_type}")

    if model_params:
        model.set_params(**model_params)

    return model


def create_pipeline(
    model_type,
    feature_set,
    feature_groups,
    feature_sets,
    tfidf_params=None,
    model_params=None,
    n_classes=None,
):
    """Build an unfitted, end-to-end sklearn pipeline."""

    preprocessor = create_preprocessor(
        feature_set=feature_set,
        model_type=model_type,
        feature_groups=feature_groups,
        feature_sets=feature_sets,
        tfidf_params=tfidf_params,
    )

    classifier = create_model(
        model_type=model_type,
        model_params=model_params,
        n_classes=n_classes,
    )

    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", classifier),
    ])


def evaluate_model(
    model_name,
    feature_set,
    y_train,
    train_pred,
    y_val,
    val_pred,
    positive_class="Passed",
):
    """Return consistent training and validation metrics."""

    return {
        "Model": model_name,
        "Feature_Set": feature_set,

        "Train_Macro_F1": f1_score(
            y_train, train_pred,
            average="macro", zero_division=0
        ),

        "Val_Macro_F1": f1_score(
            y_val, val_pred,
            average="macro", zero_division=0
        ),

        "Val_Macro_Precision": precision_score(
            y_val, val_pred,
            average="macro", zero_division=0
        ),

        "Val_Macro_Recall": recall_score(
            y_val, val_pred,
            average="macro", zero_division=0
        ),

        "Val_Weighted_F1": f1_score(
            y_val, val_pred,
            average="weighted", zero_division=0
        ),

        "Val_Balanced_Accuracy": balanced_accuracy_score(
            y_val, val_pred
        ),

        "Passed_Precision": precision_score(
            y_val, val_pred,
            labels=[positive_class],
            average="macro", zero_division=0
        ),

        "Passed_Recall": recall_score(
            y_val, val_pred,
            labels=[positive_class],
            average="macro", zero_division=0
        ),
    }


def run_experiment(
    model_type,
    feature_set,
    train_df,
    val_df,
    target,
    feature_groups,
    feature_sets,
    tfidf_params=None,
    model_params=None,
    positive_class="Passed",
):
    """Train and evaluate one classification experiment."""

    # 1. Select the required features
    features = [
        col
        for columns in feature_groups.values()
        for col in columns
    ]

    text_column = feature_sets[feature_set]

    if text_column is not None:
        features.append(text_column)

    features = list(dict.fromkeys(features))

    X_train = train_df[features].copy()
    X_val = val_df[features].copy()

    y_train = train_df[target].copy()
    y_val = val_df[target].copy()

    # 2. Encode target for XGBoost when required
    label_encoder = None

    if model_type == "xgboost":
        label_encoder = LabelEncoder()
        y_train_fit = label_encoder.fit_transform(y_train)
        n_classes = len(label_encoder.classes_)
    else:
        y_train_fit = y_train
        n_classes = None

    # 3. Build and fit the pipeline
    pipeline = create_pipeline(
        model_type=model_type,
        feature_set=feature_set,
        feature_groups=feature_groups,
        feature_sets=feature_sets,
        tfidf_params=tfidf_params,
        model_params=model_params,
        n_classes=n_classes,
    )

    pipeline.fit(X_train, y_train_fit)

    # 4. Generate predictions
    train_pred = pipeline.predict(X_train)
    val_pred = pipeline.predict(X_val)

    # Restore original class labels for XGBoost
    if label_encoder is not None:
        train_pred = label_encoder.inverse_transform(train_pred)
        val_pred = label_encoder.inverse_transform(val_pred)

    # 5. Evaluate
    results = evaluate_model(
        model_name=model_type,
        feature_set=feature_set,
        y_train=y_train,
        train_pred=train_pred,
        y_val=y_val,
        val_pred=val_pred,
        positive_class=positive_class,
    )

    # 6. Return everything needed for analysis
    return {
        "pipeline": pipeline,
        "metrics": results,
        "train_predictions": train_pred,
        "val_predictions": val_pred,
        "y_train": y_train,
        "y_val": y_val,
        "label_encoder": label_encoder,
    }

def plot_model_comparison(
    results_df,
    metric="Val_Macro_F1",
    title=None
):
    """Compare algorithms across feature sets."""

    fig, ax = plt.subplots(figsize=(11, 5))

    sns.barplot(
        data=results_df,
        x="Feature_Set",
        y=metric,
        hue="Model",
        errorbar=None,
        ax=ax
    )

    for container in ax.containers:
        ax.bar_label(
            container,
            fmt="%.3f",
            padding=3,
            fontsize=9,
        )

    ax.set_title(title or f"Model comparison: {metric}")
    ax.set_xlabel("Feature set")
    ax.set_ylabel(metric)
    ax.legend(title="Algorithm")
    plt.tight_layout()
    plt.show()


def plot_generalization_gap(results_df):
    """Compare training and validation Macro F1 gaps."""

    data = results_df.copy()
    data["F1_Gap"] = (
        data["Train_Macro_F1"]
        - data["Val_Macro_F1"]
    )

    fig, ax = plt.subplots(figsize=(11, 5))

    sns.barplot(
        data=data,
        x="Feature_Set",
        y="F1_Gap",
        hue="Model",
        errorbar=None,
        ax=ax
    )

    for container in ax.containers:
        ax.bar_label(
            container,
            fmt="%.3f",
            padding=3,
            fontsize=9,
        )

    ax.set_title("Training–Validation Generalization Gap")
    ax.set_xlabel("Feature set")
    ax.set_ylabel("Macro F1 difference")
    plt.tight_layout()
    plt.show()


def plot_passed_recall(results_df):
    """Compare recall for Passed legislation."""

    plot_model_comparison(
        results_df,
        metric="Passed_Recall",
        title="Passed Class Recall by Model",
    )

