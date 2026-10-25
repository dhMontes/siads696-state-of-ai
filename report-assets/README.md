# Report assets

Selected figures and tables from [topic analysis](../notebooks/03_topic_analysis.ipynb)
and [classifier evaluation](../notebooks/06_model_evaluation.ipynb), ready to download
for the report. The classifier comparisons cover historical folds and 2025
development. The separate [final evaluation](../notebooks/07_final_evaluation.ipynb)
assets report the selected classifier's results on 2026 bills.

## Figures

| File | Content | Source export |
| --- | --- | --- |
| [classifier_families.png](classifier_families.png) | Original and main development candidates: historical mean and SD, individual folds and 2025 development | `family_comparison.png` in notebook 06 |
| [svm_inputs.png](svm_inputs.png) | Metadata, bill text and combined inputs under matched SVM settings | `matched_svm_inputs.png` in notebook 06 |
| [nmf_leading_words.png](nmf_leading_words.png) | Leading terms for the eight reviewed NMF topics | `refined_leading_words.png` in notebook 03 |
| [nmf_state_topic_weights.png](nmf_state_topic_weights.png) | Mean NMF topic weights for all states in the data | `refined_state_mean_topic_shares.png` in notebook 03 |
| [lda_leading_words.png](lda_leading_words.png) | Leading terms for eight LDA topics | `lda_leading_words.png` in notebook 03 |
| [lda_state_topic_weights.png](lda_state_topic_weights.png) | Mean LDA topic weights for the 15 states with the most records | `lda_state_mean_topic_weights.png` in notebook 03 |

The state percentages are mean normalized topic weights among records with
nonzero text features, not percentages of bills assigned to a topic. These
descriptive topic models use the full corpus; their weights are not supervised
classifier inputs.

## Tables

- [historical_family_comparison.csv](historical_family_comparison.csv) copies
  notebook 06's `best_historical_candidate_per_family.csv`. It lists the candidate
  with the highest historical mean macro F1 in each family, alongside 2025
  development scores. It does not record the team's final model choice.
  Selection includes topic-augmented candidates, so its rows can differ from
  the six main candidates in the classifier-family figure.
- [topic_method_comparison.csv](topic_method_comparison.csv) keeps the baseline
  NMF, refined NMF and baseline LDA runs with eight topics and seed 42 from
  notebook 03's `model_comparison.csv`. It retains the source run IDs, vocabulary
  variants, NPMI coherence, term diversity and mean topic overlap. Higher coherence
  and diversity and lower overlap are preferable under these measures. The
  eight-topic rows compare the methods at the same size. Notebook 03, section 4,
  explains the count choices and the stronger metrics at some other counts;
  this table does not present a separately optimized model for each method.

## Final 2026 evaluation

These exports come from [notebook 07](../notebooks/07_final_evaluation.ipynb),
which trains the selected classifier on 2019–2025 bills and evaluates it on
2026 bills. The notebook records the selected inputs, settings and fixed split.
These are retrospective classifications of published outcome labels, not
predictions made when bills were introduced.

| File | Content | Source export |
| --- | --- | --- |
| [final_scores.csv](final_scores.csv) | Accuracy, balanced accuracy and macro F1 for the selected model and the training-majority reference, with train and test record counts | `scores.csv` in notebook 07 |
| [final_classification_report.csv](final_classification_report.csv) | Precision, recall, F1 and support for Failed, Passed and Pending outcomes | `classification_report.csv` in notebook 07 |
| [final_confusion_matrix.png](final_confusion_matrix.png) | Recorded versus predicted 2026 outcomes for the selected classifier | `confusion_matrix.png` in notebook 07 |

The majority reference always predicts the most common training outcome and
uses the same test records as the selected model. The final test scores do not
replace the historical and development comparisons above. They measure the
selected configuration on the reserved year and are not used to choose new settings.

## Refresh the figures and tables

After following the root [setup instructions](../README.md#setup-and-running-the-project),
run these notebooks from the repository root:

```shell
python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.kernel_name=state-ai-policy --ExecutePreprocessor.timeout=1800 notebooks/03_topic_analysis.ipynb notebooks/06_model_evaluation.ipynb
python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.kernel_name=state-ai-policy --ExecutePreprocessor.timeout=1800 notebooks/07_final_evaluation.ipynb
python src/export_report_assets.py
```

Notebook 03 writes to `outputs/topic_analysis/`; notebook 06 writes to
`outputs/model_evaluation/`; notebook 07 writes to `outputs/final_evaluation/`.
The figures above are unchanged copies of those exports. The historical-family
and final-evaluation tables are unchanged CSV copies; the topic
table keeps the three stated runs and the seven columns shown in its header.
The notebooks contain the full comparisons, sensitivity checks and definitions.
The export script copies the selected figures, historical table and final tables,
then filters the topic comparison to the three runs and seven columns described above.

Sources: [notebook 03](../notebooks/03_topic_analysis.ipynb),
[notebook 06](../notebooks/06_model_evaluation.ipynb) and
[notebook 07](../notebooks/07_final_evaluation.ipynb).
