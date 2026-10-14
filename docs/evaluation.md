# Evaluation

## Dataset

`eval/generate_docs.py` produces 90 synthetic documents (30 invoices, 30 KTP, 30 SPK) with ground-truth JSON in `data/ground_truth/`.
Layouts, fonts, rotation, blur and noise vary per document. About 20% of documents carry an injected error, recorded in the `injected_error` field of the ground truth:

| Error | Type | Expected outcome |
|---|---|---|
| `total_mismatch` | invoice | warning, needs review |
| `nik_birth_mismatch` | KTP | warning, needs review |
| `nik_length` | KTP | error, failed |
| `price_out_of_range` | SPK | warning, needs review |

All data is synthetic and every image carries a "SYNTHETIC DEMO DOCUMENT" label.

## Metrics

| Metric | Definition |
|---|---|
| Field-level accuracy | Correct leaf fields / total ground-truth leaf fields. Strings compare case-insensitively with collapsed whitespace; numbers compare numerically |
| Document exact match | Documents where every field is correct |
| Classification accuracy | Correct predicted type / documents |
| Validation precision / recall | A document is flagged when validation returns any warning or error. Recall is injected-error documents flagged / injected-error documents |
| Latency | Median and p95 of classify + extract time per document |
| Cost | USD per document from token usage and `MODEL_PRICING` |

## Running

```bash
pip install -r eval/requirements.txt
python eval/generate_docs.py

# rules only, no API key needed
python eval/run_eval.py --report

# LLM experiments, results land in eval/raw/ and eval/results.md
export DEEPSEEK_API_KEY=...
python eval/run_eval.py --experiment prompt-v1 --model deepseek-v4-flash-vision-exp --prompts v1
python eval/run_eval.py --experiment prompt-v2 --model deepseek-v4-flash-vision-exp --prompts v2

export ANTHROPIC_API_KEY=...
python eval/run_eval.py --experiment claude --model claude-sonnet-5-5 --prompts v2

python eval/run_eval.py --experiment width-800 --model deepseek-v4-flash-vision-exp --prompts v2 --max-width 800
```

Use `--limit 5` for a cheap smoke run (5 documents per type).

## Experiments

1. Prompt v1 (`prompts/`) against v2 (`prompts/v2/`, adds worked examples).
2. Primary model against fallback model.
3. Image width 1600 against smaller widths, trading accuracy for cost.

Validation rules are also tested without any model:

```bash
node workflows/code/stages.test.js
```
