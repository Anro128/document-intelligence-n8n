# Evaluation results

## Validation rules on ground-truth fields

Dataset: 90 synthetic documents, injected errors flagged by schema and business rules.

| Metric | Value |
|---|---|
| Precision | 100.0% |
| Recall | 100.0% |
| True positives / false positives / false negatives | 18 / 0 / 0 |

| Injected error | Detected |
|---|---|
| nik_birth_mismatch | 2/2 |
| nik_length | 6/6 |
| price_out_of_range | 5/5 |
| total_mismatch | 5/5 |

## LLM experiments

No experiment has been run yet. Run `python eval/run_eval.py --experiment <name> --model <model>`.
