# Report assets

Selected figures and tables from [topic analysis](../notebooks/03_topic_analysis.ipynb)
and [classifier evaluation](../notebooks/06_model_evaluation.ipynb), ready to download
for the report. Classifier results cover historical folds and 2025 development;
they do not include 2026 test scores.

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

## Regenerate the source exports

After following the root [setup instructions](../README.md#setup-and-running-the-project),
run these notebooks from the repository root:

```shell
python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.kernel_name=state-ai-policy --ExecutePreprocessor.timeout=1800 notebooks/03_topic_analysis.ipynb notebooks/06_model_evaluation.ipynb
```

Notebook 03 writes to `outputs/topic_analysis/`; notebook 06 writes to
`data/processed/model_evaluation/`. The figures above are unchanged copies of
those exports. The historical-family table is an unchanged CSV copy; the topic
table keeps the three stated runs and the seven columns shown in its header.
The notebooks contain the full comparisons, sensitivity checks and definitions.
To refresh these copies, replace them with the regenerated files listed above.
