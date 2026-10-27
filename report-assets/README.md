# Report assets

Selected figures and tables from the project notebooks, ready to use in the
report. The development comparisons use historical folds and 2025 bills;
the final evaluation uses 2026 bills.

## Topic analysis

These figures and the comparison table come from [notebook 03](../notebooks/03_topic_analysis.ipynb).

| File | Content |
| --- | --- |
| [nmf_leading_words.png](nmf_leading_words.png) | Leading terms for the eight reviewed NMF topics |
| [nmf_state_topic_weights.png](nmf_state_topic_weights.png) | Mean NMF topic weights for all states in the data |
| [lda_leading_words.png](lda_leading_words.png) | Leading terms for eight LDA topics |
| [lda_state_topic_weights.png](lda_state_topic_weights.png) | Mean LDA topic weights for the 15 states with the most records |
| [topic_method_comparison.csv](topic_method_comparison.csv) | Baseline NMF, refined NMF and baseline LDA with eight topics and seed 42 |

The state percentages are mean normalized topic weights among records with
nonzero text features, not percentages of bills assigned to a topic. These
descriptive models use the full corpus; their weights are not classifier inputs.

The topic table includes run IDs, vocabulary variants, NPMI coherence, term
diversity and mean topic overlap. Higher coherence and diversity and lower
overlap are preferred on these measures. The table compares methods at eight topics,
not their separately optimized counts. See notebook 03, section 4, for the
count choices and comparisons at other counts.

## Classifier comparisons

These files come from [notebook 06](../notebooks/06_model_evaluation.ipynb) and
cover historical folds and the 2025 development set.

| File | Content |
| --- | --- |
| [classifier_families.png](classifier_families.png) | Original and main development candidates: historical mean and SD, individual folds and 2025 scores |
| [svm_inputs.png](svm_inputs.png) | Metadata, bill text and combined inputs under matched SVM settings |
| [historical_family_comparison.csv](historical_family_comparison.csv) | Candidate with the highest historical mean macro F1 in each family, with 2025 scores |

The historical table can include topic-augmented candidates, so its rows may
differ from the candidates in the figure. It does not identify the final model.

## Final 2026 evaluation

[Notebook 07](../notebooks/07_final_evaluation.ipynb) trains the selected
classifier on 2019–2025 bills and evaluates it on 2026 bills. These are
retrospective classifications of recorded outcomes, not forecasts made when
bills were introduced. The majority reference always predicts the most common
training outcome. The 2026 test was not used to choose the model settings.

| File | Content |
| --- | --- |
| [final_scores.csv](final_scores.csv) | Accuracy, balanced accuracy, macro F1 and record counts for the selected model and training-majority reference |
| [final_classification_report.csv](final_classification_report.csv) | Precision, recall, F1 and support by outcome |
| [final_confusion_matrix.png](final_confusion_matrix.png) | Recorded versus predicted 2026 outcomes |

## Supplementary source checks

[source_sensitivity_scores.csv](source_sensitivity_scores.csv) contains the
label-repair and text-input comparisons from [notebook 08](../notebooks/08_source_sensitivity.ipynb).
These exploratory pre-2026 comparisons were run after examining the final test;
they do not replace the 2026 results.

## Refresh the figures and tables

Follow the root [setup instructions](../README.md#setup-and-running-the-project)
and run notebooks 03, 06, 07 and 08. The [export script](../src/export_report_assets.py)
maps the original outputs to these files. Run it from the repository root:

```shell
python src/export_report_assets.py
```
