# Related-work evidence

Three published studies support the project's text, metadata and topic comparisons. The upstream corpus project is documented separately below. These are research notes, not a completed literature-review section or evidence of model performance on our data.

Checked October 19, 2026. Coverage is partial and stated for each source.

## Published studies

| Study | Question and data | Method and evaluation | Relevance to this project | Limits and inspected coverage |
| --- | --- | --- | --- | --- |
| Yano, T., Smith, N. A., & Wilkerson, J. D. (2012). [Textual Predictors of Bill Survival in Congressional Committees](https://aclanthology.org/N12-1097/). NAACL-HLT, 793–802. [Paper](https://aclanthology.org/N12-1097.pdf). | Does a bill leave committee? 51,762 U.S. House bills from the 103rd–111th Congresses; original introduced text. | Sparse logistic regression compares political/committee metadata with added textual features. Earlier Congresses train models tested on a later Congress; additional chronological splits check the pattern. | Supports comparing metadata with text on the same legislative task. Our target is recorded state-bill outcomes, rather than federal committee survival. Its original-text restriction illustrates why the input version matters. | Committee survival is not enactment. Its sample and error rates cannot serve as our expected results. Inspected abstract, §3, §§4.1–4.3, §5.3, Table 3 and §5.5; not the complete paper or released corpus. |
| Nay, J. J. (2017). [Predicting and understanding law-making with word vectors and an ensemble model](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0176999). PLOS ONE, 12(5), e0176999. | Forecasting enactment among nearly 70,000 U.S. congressional bills from 2001–2015; 2,513 were enacted. | Word-vector language scores combine with contextual features through stacked tree and logistic models. Training uses prior Congresses. The study compares introduction-time inputs with newer inputs, and text, context and combined versions. | Closest outcome-model comparison here: text plus metadata and explicit input-timing comparisons. Our smaller, state-AI corpus uses a different population and a recorded-outcome framing unless historical inputs are verified. | This study does not justify introducing an ensemble into our project. Its published performance does not transfer to our data. Inspected abstract and §§2.1–2.2 plus the input-condition/model comparisons at the start of §3; appendices and full results were not reviewed. |
| Quinn, K. M., Monroe, B. L., Colaresi, M., Crespin, M. H., & Radev, D. R. (2010). [How to Analyze Political Attention with Minimal Assumptions and Costs](https://doi.org/10.1111/j.1540-5907.2009.00427.x). American Journal of Political Science, 54(1), 209–228. [Author's Berkeley copy](https://www.law.berkeley.edu/files/TopicModelAJPS%282%29.pdf). | Learning topics and attention patterns from more than 118,000 U.S. Senate speeches, 1997–2004. | A dynamic topic model infers word profiles and speech categories, rather than starting from predefined substantive labels. The paper describes checking semantic meaning and correspondence with legislative activity and outside events. | Supports discovering themes and interpreting them in substantive context. Our proposed NMF/LDA comparisons concern state bill text and state-level distributions, rather than Senate speech attention over time. | Its model assumes a single latent topic per speech; it is not the same as standard LDA or NMF. It does not establish validity for our bill topics. Inspected publisher abstract and paper pp. 209–213, including the methods comparison and model opening; later empirical checks and appendices were not reviewed. |

## Upstream corpus and closest project comparison

Bhargava, H. K., & Soliman, M. (2026), [U.S. State AI Legislation Corpus, v4](https://zenodo.org/records/20781731), supplies the 2,571-record starting file. Its Bill Analyst system assigns scores under seven predefined policy dimensions. Our proposed topic models instead learn themes from text, alongside separately evaluated outcome classifiers. This difference is a design comparison, not proven novelty or superiority.

The deposit calls *The Structure of U.S. State AI Policy: Evidence from a Multi-Dimensional Bill Classification* **in preparation**. No manuscript was inspected; do not cite it as a reviewed published article. The [construction documentation](https://github.com/marksoliman3/Bill_Analyst_Agent/blob/main/Database_Creation_doc.md) was inspected for acquisition, cleaning, generated fields, taxonomy and validation descriptions. Its historical status totals are not reused as current corpus counts.

## Decisions these sources help document

| Project decision | Supporting comparison | Boundary |
| --- | --- | --- |
| Compare metadata, text and combined inputs | Yano et al.; Nay | Keep bills and evaluation splits comparable; empirical gains must come from our own results. |
| Separate text versions from outcome observation dates | Yano et al.; Nay | Newer text is not verified introduction-time evidence. A later outcome observation does not fix an input-timing gap. |
| Interpret learned topics using actual bills | Quinn et al.; upstream Bill Analyst comparison | Topic names need substantive review. Learned themes need not reproduce the supplied seven categories. |

Next: use these source notes when writing the related-work section after reviewing the team's actual method and evaluation choices.

Sources: the linked primary papers, publisher records, Zenodo v4 deposit and Bill Analyst construction documentation.
