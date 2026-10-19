"""Summary-only exploratory topic analysis; metadata is used after fitting.

Run notebooks/03_topic_analysis.ipynb for the analysis and interpretation.
Source-row identifiers follow prepare.py (one-based record positions).
"""
from pathlib import Path
from itertools import combinations
import ast
import hashlib
import json
import re
import time
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.decomposition import NMF, LatentDirichletAllocation
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics import adjusted_rand_score
from sklearn.metrics.pairwise import cosine_similarity
from threadpoolctl import threadpool_limits
from .prepare import clean_text, TEXT_COLUMNS

TEXT = "NCSL_Summary_clean"
IDENTIFIERS = ["source_row", "Jurisdiction", "Bill_Number", "Year"]
VECTOR_SETTINGS = dict(ngram_range=(1, 2), min_df=3, max_df=0.85)
LEGAL_STOPWORDS = {
    "relates": "Dominated baseline topic 5; introductory summary formula, not an obligation.",
    "provides": "Generic summary verb among top terms in baseline topics 2 and 3.",
    "act": "Generic instrument/title word among top terms in baseline topics 1 and 2.",
    "section": "Statutory navigation word; paired with act in the limited format-word ablation.",
}
# Fixed geography lexicon: not learned from Jurisdiction or used as model features.
GEOGRAPHIC_NAMES = (
    "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|"
    "District of Columbia|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|"
    "Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|"
    "Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|"
    "North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|"
    "South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|"
    "West Virginia|Wisconsin|Wyoming"
).split("|")
GEO_PATTERN = re.compile(r"\b(?:" + "|".join(
    re.escape(x) for x in sorted(GEOGRAPHIC_NAMES, key=len, reverse=True)) + r")\b", re.I)
CATEGORY_REPAIRS = {
    "Effect on Labor/Employment Government Use": "Effect on Labor/Employment; Government Use",
    "Effect on Labor/Employment Studies": "Effect on Labor/Employment; Studies",
    "Notification Private Sector Use": "Notification; Private Sector Use",
}
CATEGORY_ALIASES = {"Government use": "Government Use", "Health use": "Health Use",
                    "Private Sector": "Private Sector Use"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def split_categories(value):
    """Handle the two observed separators without splitting slash-bearing labels.

    Associated Bills and Summary are scraping spillover, not categories. Three
    observed missing separators and three aliases are repaired explicitly;
    exports retain the original field.
    """
    value = re.split(r"\b(?:Associated Bills|Summary)\s*:", value, maxsplit=1, flags=re.I)[0]
    for original, repaired in CATEGORY_REPAIRS.items():
        value = value.replace(original, repaired)
    return sorted(set(CATEGORY_ALIASES.get(x.strip(), x.strip())
                      for x in re.split(r"[;,]", value) if x.strip()))


def validate_intake(prepared, raw):
    """Reject stale/edited preparation rather than attaching evidence to wrong rows."""
    try:
        raw = raw.reset_index(drop=True).copy()
        raw.index = pd.Index([str(i) for i in range(1, len(raw) + 1)], name="source_row")
        cleaned = raw.Bill_Text.map(clean_text)
        expected = raw.loc[~cleaned.duplicated(keep="last")]
        assert prepared.source_row.tolist() == expected.index.tolist()
        actual = prepared.set_index("source_row")
        for column in raw.columns:
            if column == "Sponsor_Party":
                def parties(value):
                    parsed = ast.literal_eval(value)
                    assert isinstance(parsed, list)
                    return parsed
                pd.testing.assert_series_equal(actual[column].map(parties), expected[column].map(parties))
            else:
                pd.testing.assert_series_equal(actual[column], expected[column])
        for column in TEXT_COLUMNS:
            pd.testing.assert_series_equal(actual[column + "_clean"],
                expected[column].map(clean_text).rename(column + "_clean"))
        retained = {cleaned.loc[sr]: sr for sr in expected.index}
        removed = []
        for sr in raw.index.difference(expected.index, sort=False):
            keep = retained[cleaned.loc[sr]]
            assert cleaned.loc[sr] == cleaned.loc[keep]
            removed.append({"removed_source_row": sr, "retained_source_row": keep,
                            "raw_text_identical": raw.loc[sr, "Bill_Text"] == raw.loc[keep, "Bill_Text"],
                            "removed_raw_sha256": hashlib.sha256(raw.loc[sr, "Bill_Text"].encode()).hexdigest(),
                            "retained_raw_sha256": hashlib.sha256(raw.loc[keep, "Bill_Text"].encode()).hexdigest(),
                            "clean_text_sha256": hashlib.sha256(cleaned.loc[sr].encode()).hexdigest()})
        return removed
    except (AssertionError, KeyError, ValueError, SyntaxError) as error:
        raise ValueError("Common intake does not match the raw source/preparation rules. "
                         "Run python src/prepare.py before the analysis.") from error


def load_common(root):
    path = Path(root) / "data/processed/common_intake/common_records.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = [TEXT, "NCSL_Category", "Bill_Text", "summary", "Bill_URL", "Version_Date",
                "Bill_Status", *IDENTIFIERS]
    if set(required) - set(df):
        raise ValueError(f"Missing required fields: {set(required) - set(df)}")
    if not df.source_row.is_unique:
        raise ValueError("source_row must uniquely locate a source record")
    raw = pd.read_csv(Path(root) / "data/raw/Final_Database.csv", dtype=str,
                      keep_default_na=False, skip_blank_lines=False)
    removed = validate_intake(df, raw)
    included = df[TEXT].str.strip().ne("")
    work = df.loc[included].reset_index(drop=True).copy()
    work["categories"] = work.NCSL_Category.map(split_categories)
    audit = {
        "raw_records": len(raw), "prepared_columns": len(df.columns),
        "removed_fulltext_duplicates": removed, "source_records": len(df), "included_records": len(work),
        "excluded_empty_ncsl_summary": int((~included).sum()),
        "empty_other_summary_retained": int(work.summary.str.strip().eq("").sum()),
        "blank_category_field": int(work.NCSL_Category.str.strip().eq("").sum()),
        "no_category_after_parsing": int(work.categories.map(len).eq(0).sum()),
        "category_associated_bills_spillover": int(work.NCSL_Category.str.contains("Associated Bills:").sum()),
        "category_summary_spillover": int(work.NCSL_Category.str.contains("Summary:").sum()),
        "category_missing_separator_repairs": int(work.NCSL_Category.map(
            lambda x: any(k in x for k in CATEGORY_REPAIRS)).sum()),
        "duplicate_clean_summary_extra_records": int(work[TEXT].duplicated().sum()),
        "jurisdictions_including_dc": work.Jurisdiction.nunique(),
        "empty_bill_text": int(work.Bill_Text.str.strip().eq("").sum()),
    }
    return work, audit


def features(texts, variant="baseline", method="NMF"):
    if variant not in {"baseline", "legal", "geography", "legal_geography"}:
        raise ValueError(variant)
    texts = texts.copy()
    if "geography" in variant:
        texts = texts.map(lambda s: GEO_PATTERN.sub(" ", s))
    stopwords = (sorted(set(ENGLISH_STOP_WORDS) | LEGAL_STOPWORDS.keys())
                 if "legal" in variant else "english")
    cls = TfidfVectorizer if method == "NMF" else CountVectorizer
    vectorizer = cls(stop_words=stopwords, **VECTOR_SETTINGS)
    return vectorizer, vectorizer.fit_transform(texts)


def fit_model(X, method="NMF", k=8, seed=42, init="nndsvda"):
    if method == "NMF":
        model = NMF(n_components=k, init=init, random_state=seed, max_iter=500)
    elif method == "LDA":
        model = LatentDirichletAllocation(n_components=k, random_state=seed,
            learning_method="batch", max_iter=30, evaluate_every=5, n_jobs=1)
    else:
        raise ValueError(method)
    started = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught, threadpool_limits(limits=2):
        warnings.simplefilter("always", ConvergenceWarning)
        W = model.fit_transform(X)
    # LDA would otherwise return only its prior for an empty vector.
    W[X.getnnz(axis=1) == 0] = 0
    return model, W, time.perf_counter() - started, [str(w.message) for w in caught]


def dominant_topics(W):
    # Never silently assign an all-zero document to topic 0.
    return np.where(W.sum(axis=1) > 0, W.argmax(axis=1), -1)


def topic_tables(work, model, W, vectorizer, run_id, top_n=5):
    terms = vectorizer.get_feature_names_out()
    dominant = dominant_topics(W)
    topics, representatives = [], []
    for topic, h in enumerate(model.components_):
        words = terms[np.argsort(-h, kind="stable")[:12]].tolist()
        topics.append({"run_id": run_id, "topic_id": topic, "keywords": ", ".join(words),
                       "dominant_records": int((dominant == topic).sum())})
        for rank, i in enumerate(np.argsort(-W[:, topic], kind="stable")[:top_n], 1):
            row = work.iloc[i]
            representatives.append({"run_id": run_id, "topic_id": topic, "rank": rank,
                "topic_weight_raw": float(W[i, topic]), "dominant_topic": int(dominant[i]),
                **row[[*IDENTIFIERS, "NCSL_Category", TEXT]].to_dict(),
                "parsed_categories": "; ".join(row.categories)})
    return pd.DataFrame(topics), pd.DataFrame(representatives)


def topic_metrics(X, model):
    """In-sample, document-level NPMI; descriptive diagnostic, not model selection."""
    top = np.argsort(-model.components_, axis=1, kind="stable")[:, :12]
    vocabulary = np.unique(top)
    B = (X[:, vocabulary] > 0).astype(np.int64)
    cooccurrence = (B.T @ B).toarray() / X.shape[0]
    frequencies = np.asarray(B.mean(axis=0)).ravel()
    lookup = {int(t): i for i, t in enumerate(vocabulary)}
    npmi = []
    for topic in top:
        scores = []
        for a, b in combinations(topic, 2):
            i, j = lookup[int(a)], lookup[int(b)]
            p = cooccurrence[i, j]
            scores.append(-1.0 if p == 0 else (0.0 if p == 1 else
                          np.log(p / (frequencies[i] * frequencies[j])) / -np.log(p)))
        npmi.append(float(np.mean(scores)))
    sets = [set(x.tolist()) for x in top]
    overlap = [len(a & b) / len(a | b) for a, b in combinations(sets, 2)]
    return {"document_npmi_top12": float(np.mean(npmi)),
            "top12_term_diversity": len(vocabulary) / top.size,
            "mean_top12_jaccard": float(np.mean(overlap)),
            "max_top12_jaccard": float(max(overlap))}


def align_topics(reference, candidate):
    # Project both component matrices onto their union vocabulary, then match.
    rt = reference["vectorizer"].get_feature_names_out()
    ct = candidate["vectorizer"].get_feature_names_out()
    union = sorted(set(rt) | set(ct))
    index = {term: i for i, term in enumerate(union)}
    matrices = []
    for terms, bundle in [(rt, reference), (ct, candidate)]:
        H = np.zeros((bundle["model"].n_components, len(union)))
        H[:, [index[t] for t in terms]] = bundle["model"].components_
        matrices.append(H)
    similarity = cosine_similarity(*matrices)
    rows, cols = linear_sum_assignment(-similarity)
    aligned = [{"reference_topic": int(a), "candidate_topic": int(b),
                "component_cosine": float(similarity[a, b])} for a, b in zip(rows, cols)]
    return aligned


def run_experiments(work, baseline, out, include_lda=True):
    """Same records across runs; only summaries enter any fit."""
    specs = [("NMF", "baseline", k, 42, "nndsvda") for k in [5, 6, 8, 10, 12]]
    specs += [("NMF", "baseline", k, seed, "nndsvda") for k in [6, 8, 10] for seed in [7, 21]]
    specs += [("NMF", "baseline", 8, seed, "random") for seed in [7, 21]]
    specs += [("NMF", variant, 8, 42, "nndsvda") for variant in ["legal", "geography", "legal_geography"]]
    if include_lda:
        specs += [("LDA", "baseline", k, 42, "batch") for k in [5, 8, 10, 12]]
    bundles, metrics, all_topics, all_reps, alignment = {}, [], [], [], []
    cache = {("NMF", "baseline"): (baseline["vectorizer"], baseline["X"])}
    for method, variant, k, seed, init in specs:
        run_id = f"{method.lower()}_{variant}_k{k}_seed{seed}_{init}"
        if (method, variant) not in cache:
            cache[method, variant] = features(work[TEXT], variant, method)
        vectorizer, X = cache[method, variant]
        if method == "NMF" and variant == "baseline" and k == 8 and seed == 42:
            model, W = baseline["model"], baseline["W"]
            seconds, messages = baseline.get("seconds", 0), baseline.get("warnings", [])
        else:
            model, W, seconds, messages = fit_model(X, method, k, seed, init)
        bundle = dict(model=model, W=W, vectorizer=vectorizer, X=X)
        bundles[run_id] = bundle
        topics, reps = topic_tables(work, model, W, vectorizer, run_id)
        all_topics.append(topics)
        all_reps.append(reps)
        metrics.append({"run_id": run_id, "method": method, "variant": variant, "topics": k,
            "seed": seed, "initialization": init, "records": len(work), "features": X.shape[1],
            "iterations": model.n_iter_, "fit_seconds": seconds,
            "zero_feature_rows": int((X.getnnz(axis=1) == 0).sum()),
            "unassigned_records": int((dominant_topics(W) == -1).sum()),
            "convergence_warnings": " | ".join(messages),
            "nmf_reconstruction_error": model.reconstruction_err_ if method == "NMF" else np.nan,
            "lda_training_perplexity": model.bound_ if method == "LDA" else np.nan,
            "ari_vs_baseline": adjusted_rand_score(dominant_topics(baseline["W"]), dominant_topics(W)),
            **topic_metrics(X, model)})
        for row in align_topics(baseline, bundle):
            alignment.append({"run_id": run_id, **row})
        print(f"{run_id}: {seconds:.1f}s, {model.n_iter_} iterations", flush=True)
    comparison = pd.DataFrame(metrics)
    topic_df, reps_df = pd.concat(all_topics, ignore_index=True), pd.concat(all_reps, ignore_index=True)
    comparison.to_csv(out / "model_comparison.csv", index=False)
    topic_df.to_csv(out / "all_run_topics.csv", index=False)
    reps_df.to_csv(out / "all_run_representatives.csv", index=False)
    pd.DataFrame(alignment).to_csv(out / "topic_alignment.csv", index=False)
    return bundles, comparison, topic_df, reps_df


def distributions(work, W, out, prefix="baseline"):
    assignments = work[IDENTIFIERS + ["NCSL_Category"]].copy()
    assignments["dominant_topic"] = dominant_topics(W)
    sums = W.sum(axis=1, keepdims=True)
    normalized = np.divide(W, sums, out=np.zeros_like(W), where=sums > 0)
    for t in range(W.shape[1]):
        assignments[f"topic_{t}_raw"] = W[:, t]
        assignments[f"topic_{t}_share"] = normalized[:, t]
    assignments.to_csv(out / f"{prefix}_document_topics.csv", index=False)
    topic_columns = list(range(W.shape[1]))
    if (assignments.dominant_topic == -1).any():
        topic_columns += [-1]
    state = pd.crosstab(assignments.Jurisdiction, assignments.dominant_topic).reindex(
        columns=topic_columns, fill_value=0)
    state_totals = assignments.groupby("Jurisdiction").size()
    state_share = state.div(state_totals, axis=0)
    state.to_csv(out / f"{prefix}_state_topic_counts.csv")
    state_share.to_csv(out / f"{prefix}_state_topic_proportions.csv")
    long = state.stack().rename("topic_records").reset_index()
    long["jurisdiction_records"] = long.Jurisdiction.map(state_totals)
    long["within_jurisdiction_proportion"] = long.topic_records / long.jurisdiction_records
    long.to_csv(out / f"{prefix}_state_topic_long.csv", index=False)
    categories = assignments[["source_row", "dominant_topic"]].copy()
    categories["category"] = work.categories.map(lambda x: x or ["[Uncategorized]"])
    categories = categories.explode("category", ignore_index=True)
    category_counts = pd.crosstab(categories.dominant_topic, categories.category).reindex(
        index=topic_columns, fill_value=0)
    topic_totals = assignments.groupby("dominant_topic").size().reindex(topic_columns, fill_value=0)
    category_proportions = category_counts.div(topic_totals.replace(0, np.nan), axis=0).fillna(0)
    category_counts.to_csv(out / f"{prefix}_topic_category_counts.csv")
    category_proportions.to_csv(out / f"{prefix}_topic_category_proportions.csv")
    categories.to_csv(out / f"{prefix}_category_membership.csv", index=False)
    assert np.allclose(state_share.sum(axis=1), 1), "Unassigned rows require explicit denominator review"
    assert state.to_numpy().sum() == len(work)
    assert category_proportions.le(1).all().all()
    return state, state_share, category_counts, category_proportions


def heatmap(frame, title, path, percent=False, size=None):
    fig, ax = plt.subplots(figsize=size or (13, max(5, .28 * len(frame))))
    values = frame.to_numpy() * (100 if percent else 1)
    im = ax.imshow(values, aspect="auto", cmap="Blues", vmin=0,
                   vmax=100 if percent else None)
    ax.set_xticks(range(frame.shape[1]), [str(c) for c in frame.columns], rotation=60, ha="right")
    ax.set_yticks(range(frame.shape[0]), [str(i) for i in frame.index])
    ax.set_title(title, loc="left", pad=16)
    fig.colorbar(im, ax=ax, label="Percent" if percent else "Records", fraction=.035, pad=.025)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    return fig


def case_evidence(work, case_specs, bundles, out):
    """Validate literal evidence spans against original Bill_Text, never generated summaries."""
    records = []
    indexed = work.set_index("source_row", drop=False)
    for spec in case_specs:
        source = indexed.loc[str(spec["source_row"])]
        raw = source.Bill_Text
        item = {k: v for k, v in spec.items() if k != "passages"}
        item.update(source[[*IDENTIFIERS, "NCSL_Category", TEXT, "Bill_URL", "Version_Date", "Bill_Status"]].to_dict())
        item["bill_text_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        evidence, locators = [], []
        for passage in spec["passages"]:
            if raw.count(passage["start"]) != 1:
                raise ValueError(f"Ambiguous evidence start in source_row {source.source_row}")
            start = raw.index(passage["start"])
            end = (raw.index(passage["end"], start) + len(passage["end"]))
            excerpt = raw[start:end]
            assert excerpt and excerpt == raw[start:end]
            evidence.append(excerpt)
            locators.append({"section": passage["section"], "start_char": start, "end_char_exclusive": end})
        item["evidence"] = "\n\n[Next passage]\n\n".join(evidence)
        item["evidence_locations_json"] = json.dumps(locators)
        item["reviewer"] = "Codex text review; independent human review pending"
        item["version_scope"] = "Stored corpus text only; not a verification of current law"
        records.append(item)
    cases = pd.DataFrame(records)
    positions = {str(sr): i for i, sr in enumerate(work.source_row)}
    assignments = []
    for name, bundle in bundles.items():
        for sr in cases.source_row:
            i = positions[sr]
            row = bundle["W"][i]
            assignments.append({"run_id": name, "source_row": sr,
                "dominant_topic": int(dominant_topics(bundle["W"])[i]),
                "top_two_topics": ";".join(map(str, np.argsort(-row)[:2])),
                "dominant_weight_share": float(row.max() / row.sum()) if row.sum() else 0})
    cases.to_csv(out / "case_analysis.csv", index=False)
    pd.DataFrame(assignments).to_csv(out / "case_assignments_all_runs.csv", index=False)
    return cases


def pair_stability(work, bundles, pair_specs, out):
    positions = {str(sr): i for i, sr in enumerate(work.source_row)}
    rows = []
    for name, bundle in bundles.items():
        W = bundle["W"]
        dominant = dominant_topics(W)
        for pair in pair_specs:
            a, b = positions[str(pair["a"])], positions[str(pair["b"])]
            rows.append({"run_id": name, **pair,
                "a_topic": int(dominant[a]), "b_topic": int(dominant[b]),
                "same_dominant_topic": bool(dominant[a] >= 0 and dominant[a] == dominant[b]),
                "topic_weight_cosine": float(cosine_similarity(W[a:a+1], W[b:b+1])[0, 0])})
    result = pd.DataFrame(rows)
    result.to_csv(out / "case_pair_stability.csv", index=False)
    return result


def stability_report(pair_results):
    """Report only results present in the current run, including LDA-off runs."""
    paragraphs = []
    for method in ["NMF", "LDA"]:
        subset = pair_results.loc[pair_results.run_id.str.startswith(method.lower() + "_")].copy()
        if subset.empty:
            paragraphs.append(f"**{method}: not run in this execution.** No current {method} stability result is reported.")
            continue
        similar = subset.loc[subset.expected_relation.eq("similar")]
        different = subset.loc[subset.expected_relation.eq("different")]
        n_pairs = similar[["a", "b"]].drop_duplicates().shape[0]
        runs = subset.run_id.nunique()
        paragraphs.append(
            f"**{method}: {runs} settings, {n_pairs} selected similarity pairs.** "
            f"Shared dominant topic in {int(similar.same_dominant_topic.sum())}/{len(similar)} "
            f"pair-setting checks. The contrasting pairs remain separated in "
            f"{int((~different.same_dominant_topic).sum())}/{len(different)} checks.")
    paragraphs.append("These are sensitivity results for cases selected after the initial fit, not "
        "validation of every topic boundary or independent confirmation. Topic-weight scaling, "
        "corpus coverage and limited LDA training remain limitations; provisions establish the specific commonalities.")
    return "\n\n".join(paragraphs)


def unit_mass_weights(W, H):
    """Equivalent NMF coordinates: each nonzero component of H has unit L1 mass.

    W @ H is unchanged. Unlike raw W argmax, these weights are invariant under
    positive reciprocal scaling of a component and its document weights.
    This is a sensitivity convention, not a probability calibration.
    """
    return W * H.sum(axis=1)


def scaling_sensitivity(work, bundles, pair_specs, out):
    rows, pair_rows = [], []
    positions = {str(sr): i for i, sr in enumerate(work.source_row)}
    selected = {"nmf_baseline_k8_seed42_nndsvda": "baseline",
                "nmf_legal_k8_seed42_nndsvda": "refined"}
    for name, bundle in bundles.items():
        if not isinstance(bundle["model"], NMF):
            continue
        W, H = bundle["W"], bundle["model"].components_
        scaled = unit_mass_weights(W, H)
        mass = H.sum(axis=1, keepdims=True)
        unit_H = np.divide(H, mass, out=np.zeros_like(H), where=mass > 0)
        assert np.allclose(W[:10] @ H, scaled[:10] @ unit_H)
        original, alternative = dominant_topics(W), dominant_topics(scaled)
        def counts(topics):
            return pd.crosstab(work.Jurisdiction, pd.Series(topics, name="dominant_topic")).reindex(
                columns=[*range(W.shape[1]), -1], fill_value=0)
        raw_counts, unit_counts = counts(original), counts(alternative)
        totals = work.groupby("Jurisdiction").size()
        delta = (raw_counts.div(totals, axis=0) - unit_counts.div(totals, axis=0)).abs()
        rows.append({"run_id": name, "records": len(work),
            "changed_dominant_records": int((original != alternative).sum()),
            "changed_fraction": float((original != alternative).mean()),
            "maximum_state_topic_shift_percentage_points": float(delta.to_numpy().max() * 100)})
        for pair in pair_specs:
            a, b = positions[str(pair["a"])], positions[str(pair["b"])]
            same = bool(alternative[a] >= 0 and alternative[a] == alternative[b])
            pair_rows.append({"run_id": name, **pair,
                "a_unit_mass_topic": int(alternative[a]), "b_unit_mass_topic": int(alternative[b]),
                "same_unit_mass_topic": same,
                "relationship_preserved": same if pair["expected_relation"] == "similar" else not same})
        if name in selected:
            prefix = selected[name]
            unit_counts.to_csv(out / f"{prefix}_unit_mass_state_topic_counts.csv")
            unit_counts.div(totals, axis=0).to_csv(out / f"{prefix}_unit_mass_state_topic_proportions.csv")
    summary, pairs = pd.DataFrame(rows), pd.DataFrame(pair_rows)
    summary.to_csv(out / "nmf_scaling_sensitivity.csv", index=False)
    pairs.to_csv(out / "case_pair_scaling_sensitivity.csv", index=False)
    return summary, pairs


def model_review_notes(comparison):
    """Post-fit, limited content review; never relabel numerical metrics as human ratings."""
    rows = []
    for r in comparison.itertuples():
        if r.method == "LDA":
            finding = {
                5: "Broad state/education and criminal/media mixtures; generic requires/provides recur across topics.",
                8: "Task-force vocabulary emerges with data/information; automated-decision cases split across topics.",
                10: "Task-force and election topics persist; an employment topic also contains sexual-exploitation terms.",
                12: "More narrow media/provenance terms but mixed intimate-imagery/rental vocabulary remains.",
            }[r.topics]
            coverage = "Top-12 keywords and highest-weight representative per topic inspected; top-five tables exported. Case-pair check completed."
            reason = "Bounded 30-iteration comparison; no LDA seed study, held-out evaluation or best-model claim."
        elif r.variant == "legal":
            finding = "Relates-formula topic disappears; rent-pricing representatives emerge. Generic AI and duplicate summaries persist."
            coverage = "All eight topics and all 40 top-five summaries inspected; eight case texts checked."
            reason = "Used for refined descriptive figures because an observed format artifact was removed; not claimed globally optimal."
        elif r.variant != "baseline":
            finding = "Case-pair relationships survive geography removal; general corpus assignments shift. Whole names may also remove substantive place references."
            coverage = "Top-12 terms and case assignments checked; not a complete independent representative review."
            reason = "Sensitivity analysis only; geography removal can alter meaning and is not adopted as the primary cleaning."
        elif r.initialization == "random":
            finding = "Chosen case pairs persist under random initialization; corpus-wide dominant assignments change."
            coverage = "Case pairs and component alignment checked; not a fresh full summary review."
            reason = "Stress check beyond the relatively similar NNDSVD initializations; finite seeds are not general guarantees."
        else:
            finding = {
                5: "Media and sexual-offense terms merge; health and administration mix. Task forces and decision systems remain.",
                6: "Health separates, but sexual-offense and synthetic-media content still share a topic.",
                8: "Task-force and automated-decision leads are interpretable; topic 5 is a formula artifact and topic 1 is generic.",
                10: "Pricing and a 19-record commendation theme emerge; generic and relates topics persist.",
                12: "Splits imagery/likeness and pricing further; generic AI language and a commendation theme persist.",
            }[r.topics]
            coverage = ("All eight topics and 40 top-five summaries inspected; eight case texts checked."
                        if r.topics == 8 and r.seed == 42 else
                        "Top-12 terms and case assignments inspected; top-one representatives inspected for k=5/10/12 seed=42. Top-five tables available.")
            reason = ("Requested reproducible starting point, retained as baseline; not a selected optimum."
                      if r.topics == 8 and r.seed == 42 else
                      "Sensitivity comparison; larger k alone does not establish a better substantive model.")
        rows.append({"run_id": r.run_id, "content_assessment": finding,
                     "review_coverage": coverage, "selection_reason": reason,
                     "independent_human_validation": False})
    return pd.DataFrame(rows)


def check_topic_identity(candidate, labels, reference=None, reviewed_mapping=None):
    """Fail before applying reviewed labels if numbering or content has changed."""
    if reference is not None:
        alignment = align_topics(reference, candidate)
        mapping = [r["candidate_topic"] for r in alignment]
        expected = reviewed_mapping if reviewed_mapping is not None else list(range(len(mapping)))
        if mapping != expected:
            raise ValueError(f"Topic numbering changed: {mapping}; review labels before exporting")
    else:
        alignment = []
    terms = candidate["vectorizer"].get_feature_names_out()
    for row in labels:
        words = terms[np.argsort(-candidate["model"].components_[row["topic_id"]], kind="stable")[:12]].tolist()
        if words != row["expected_keywords"]:
            raise ValueError(f"Topic {row['topic_id']} content changed; review labels before exporting")
    return alignment


def supervised_split(work):
    """Match notebook 02's introduction-year split; never substitute NCSL Year."""
    dates = pd.to_datetime(work["introduction_date_iso"], format="%Y-%m-%d", errors="coerce")
    years = dates.dt.year
    split = pd.Series("excluded", index=work.index, name="split")
    split.loc[years.between(2019, 2024)] = "train"
    split.loc[years.eq(2025)] = "validation"
    split.loc[years.eq(2026)] = "test"
    return split


def supplementary_analysis(work, baseline, out):
    """Train-only supervised features and post-fit descriptive sensitivities."""
    import joblib
    split = supervised_split(work)
    train = split.eq("train")
    v, X = features(work.loc[train, TEXT])
    m, _, _, messages = fit_model(X)
    all_X = v.transform(work[TEXT])
    with threadpool_limits(limits=2):
        W = m.transform(all_X)
    W[all_X.getnnz(axis=1) == 0] = 0
    output = work[IDENTIFIERS + ["introduction_date_iso"]].copy()
    output["introduction_year"] = pd.to_datetime(work.introduction_date_iso, format="%Y-%m-%d", errors="coerce").dt.year.astype("Int64")
    output["split"] = split
    for t in range(W.shape[1]):
        output[f"train_nmf_topic_{t}_raw"] = W[:, t]
    output["dominant_topic"] = dominant_topics(W)
    output.to_csv(out / "supervised_topic_features.csv", index=False)
    joblib.dump(dict(vectorizer=v, model=m, train_source_rows=work.loc[train, "source_row"].tolist()),
                out / "supervised_topic_model.joblib")
    meta = {"split_date_column": "introduction_date_iso",
            "split_reference": "notebooks/02_data_split_exploration.ipynb: Intro_Year",
            "fit_years": [2019, 2024], "validation_year": 2025, "test_year": 2026,
            "split_counts": split.value_counts().to_dict(),
            "excluded_source_rows": work.loc[split.eq("excluded"), "source_row"].tolist(),
            "excluded_policy": "Missing/invalid dates and introduction years outside 2019-2026 are transformed but excluded from supervised partitions, matching notebook 02", "input_column": TEXT,
            "warnings": messages, "topic_ids": "Independent train-only model; descriptive labels do not apply",
            "scope": "Temporal fit isolation only; repeated summaries across years may remain"}
    (out / "supervised_metadata.json").write_text(json.dumps(meta, indent=2))
    unique = work.drop_duplicates(TEXT, keep="first").reset_index(drop=True)
    v, X = features(unique[TEXT]); m, _, _, _ = fit_model(X)
    candidate = dict(vectorizer=v, model=m)
    aligned = align_topics(baseline, candidate)
    pd.DataFrame(aligned).to_csv(out / "summary_dedup_alignment.csv", index=False)
    with threadpool_limits(limits=2):
        W = m.transform(v.transform(work[TEXT]))
    W[v.transform(work[TEXT]).getnnz(axis=1) == 0] = 0
    mapping = {r["candidate_topic"]: r["reference_topic"] for r in aligned}
    predicted = np.array([mapping.get(t, -1) for t in dominant_topics(W)])
    original = dominant_topics(baseline["W"])
    sensitivity = {"original_records": len(work), "unique_summaries": len(unique),
                   "removed_extra_summaries": len(work)-len(unique),
                   "evaluation_population": "all original records transformed by both models",
                   "aligned_assignment_changes": int((predicted != original).sum()),
                   "adjusted_rand_index": float(adjusted_rand_score(original, predicted))}
    (out / "summary_dedup_audit.json").write_text(json.dumps(sensitivity, indent=2))
    pd.DataFrame({"source_row": work.source_row, "baseline_topic": original,
                  "dedup_aligned_topic": predicted}).to_csv(out / "summary_dedup_assignments.csv", index=False)
    topics, reps = topic_tables(unique, m, m.transform(X), v, "summary_deduplicated")
    topics.to_csv(out / "summary_dedup_topics.csv", index=False)
    reps.to_csv(out / "summary_dedup_representatives.csv", index=False)
    return meta, sensitivity


def sponsor_tables(work, bundle, out, prefix):
    frame = work[["source_row", "Bipartisan_Support", "Democrat_Sponsor_Ratio"]].copy()
    frame["topic_id"] = dominant_topics(bundle["W"])
    frame["Bipartisan_Support"] = pd.to_numeric(frame.Bipartisan_Support, errors="raise")
    frame["Democrat_Sponsor_Ratio"] = pd.to_numeric(frame.Democrat_Sponsor_Ratio.replace("", np.nan), errors="raise")
    pd.crosstab(frame.topic_id, frame.Bipartisan_Support).to_csv(out / f"{prefix}_topic_bipartisan_counts.csv")
    frame.groupby("topic_id").agg(records=("source_row", "size"),
        bipartisan_records=("Bipartisan_Support", "sum"), bipartisan_share=("Bipartisan_Support", "mean"),
        observed_democrat_ratios=("Democrat_Sponsor_Ratio", "count"),
        mean_democrat_ratio=("Democrat_Sponsor_Ratio", "mean"),
        median_democrat_ratio=("Democrat_Sponsor_Ratio", "median")).to_csv(out / f"{prefix}_topic_sponsor_summary.csv")
