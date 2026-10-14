"""Benchmarks extraction and validation on the synthetic dataset and writes eval/results.md."""
import argparse
import base64
import io
import json
import math
import os
import statistics
import subprocess
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "eval" / "raw"
DOC_TYPES = ["invoice", "ktp", "spk"]
DEFAULT_PRICING = {"claude-sonnet-5-5": [3, 15], "gpt-4o-mini": [0.15, 0.6]}
PRICING = {**DEFAULT_PRICING, **json.loads(os.environ.get("MODEL_PRICING", "{}"))}
CLASSIFY_SCHEMA = {
    "type": "object",
    "required": ["type", "confidence"],
    "properties": {
        "type": {"type": "string", "enum": ["invoice", "ktp", "spk", "other"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_schema(doc_type):
    schema = read_json(ROOT / "schemas" / f"{doc_type}.schema.json")
    schema.pop("$schema", None)
    schema.pop("title", None)
    return schema


def load_dataset(limit):
    records = [read_json(p) for p in sorted((ROOT / "data" / "ground_truth").glob("*.json"))]
    if not limit:
        return records
    return [r for t in DOC_TYPES for r in [x for x in records if x["doc_type"] == t][:limit]]


def encode_image(doc_id, max_width):
    img = Image.open(ROOT / "data" / "synthetic" / f"{doc_id}.jpg").convert("RGB")
    if img.width > max_width:
        img = img.resize((max_width, round(img.height * max_width / img.width)), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode()


def call_claude(model, system, b64, schema, max_tokens):
    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
        json={
            "model": model, "max_tokens": max_tokens, "system": system,
            "tools": [{"name": "record", "description": "Record the result", "input_schema": schema}],
            "tool_choice": {"type": "tool", "name": "record"},
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": "Process this document."},
            ]}],
        },
        timeout=90,
    )
    res.raise_for_status()
    body = res.json()
    block = next(c for c in body["content"] if c["type"] == "tool_use")
    return block["input"], body["usage"]["input_tokens"], body["usage"]["output_tokens"]


def call_openai(model, system, b64, schema, max_tokens):
    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={
            "model": model, "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": "Process this document."},
                ]},
            ],
            "response_format": {"type": "json_schema", "json_schema": {"name": "record", "schema": schema}},
        },
        timeout=90,
    )
    res.raise_for_status()
    body = res.json()
    return json.loads(body["choices"][0]["message"]["content"]), body["usage"]["prompt_tokens"], body["usage"]["completion_tokens"]


def call_model(model, system, b64, schema, max_tokens):
    """One retry on failure, no fallback model so each model is measured on its own."""
    call = call_claude if model.startswith("claude") else call_openai
    last = None
    for _ in range(2):
        started = time.time()
        try:
            data, tin, tout = call(model, system, b64, schema, max_tokens)
            cost = (tin * PRICING.get(model, [0, 0])[0] + tout * PRICING.get(model, [0, 0])[1]) / 1e6
            return data, cost, (time.time() - started) * 1000, None
        except Exception as exc:
            last = str(exc)
    return None, 0.0, 0.0, last


def flatten(value, prefix=""):
    if isinstance(value, dict):
        out = {}
        for key, sub in value.items():
            out.update(flatten(sub, f"{prefix}.{key}" if prefix else key))
        return out
    if isinstance(value, list):
        out = {}
        for i, sub in enumerate(value):
            out.update(flatten(sub, f"{prefix}[{i}]"))
        return out
    return {prefix: value}


def normalize(value):
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return value


def score_fields(truth, predicted):
    expected = flatten(truth)
    got = flatten(predicted) if isinstance(predicted, (dict, list)) else {}
    correct = sum(1 for k, v in expected.items() if k in got and normalize(got[k]) == normalize(v))
    return correct, len(expected)


def run_validation(items):
    if not items:
        return {}
    proc = subprocess.run(
        ["node", str(ROOT / "workflows" / "code" / "validate_cli.js")],
        input=json.dumps(items), capture_output=True, text=True, check=True,
    )
    return {r["id"]: r for r in json.loads(proc.stdout)}


def validation_stats(flagged_by_id, truth_by_id):
    tp = sum(1 for i, f in flagged_by_id.items() if f and truth_by_id[i]["injected_error"])
    fp = sum(1 for i, f in flagged_by_id.items() if f and not truth_by_id[i]["injected_error"])
    fn = sum(1 for i, f in flagged_by_id.items() if not f and truth_by_id[i]["injected_error"])
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall}


def rules_only_report():
    records = load_dataset(0)
    results = run_validation([{"id": r["id"], "doc_type": r["doc_type"], "fields": r["fields"]} for r in records])
    truth = {r["id"]: r for r in records}
    flagged = {i: bool(v["errors"] or v["warnings"]) for i, v in results.items()}
    per_error = {}
    for r in records:
        if r["injected_error"]:
            hit = per_error.setdefault(r["injected_error"], [0, 0])
            hit[1] += 1
            hit[0] += 1 if flagged[r["id"]] else 0
    return validation_stats(flagged, truth), per_error, len(records)


def percentile(values, q):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)] if ordered else 0


def summarize(docs):
    done = [d for d in docs if d["fields_total"]]
    fields_correct = sum(d["fields_correct"] for d in done)
    fields_total = sum(d["fields_total"] for d in done)
    latencies = [d["latency_ms"] for d in docs if d["latency_ms"]]
    return {
        "documents": len(docs),
        "classification_accuracy": sum(d["predicted_type"] == d["doc_type"] for d in docs) / len(docs),
        "field_accuracy": fields_correct / fields_total if fields_total else 0,
        "exact_match": sum(d["exact"] for d in docs) / len(docs),
        "latency_median_ms": statistics.median(latencies) if latencies else 0,
        "latency_p95_ms": percentile(latencies, 0.95),
        "cost_per_doc_usd": sum(d["cost_usd"] for d in docs) / len(docs),
        "failures": sum(1 for d in docs if d["error"]),
    }


def run_experiment(args):
    records = load_dataset(args.limit)
    prompt_dir = ROOT / "prompts" / ("v2" if args.prompts == "v2" else "")
    classify_prompt = (ROOT / "prompts" / "classify.md").read_text(encoding="utf-8")
    prompts = {t: (prompt_dir / f"extract_{t}.md").read_text(encoding="utf-8") for t in DOC_TYPES}
    schemas = {t: load_schema(t) for t in DOC_TYPES}

    docs, predictions = [], []
    for record in records:
        b64 = encode_image(record["id"], args.max_width)
        cls, cost1, lat1, err1 = call_model(args.model, classify_prompt, b64, CLASSIFY_SCHEMA, 200)
        predicted_type = cls["type"] if cls else None
        fields, cost2, lat2, err2 = (None, 0.0, 0.0, err1)
        if predicted_type in DOC_TYPES:
            fields, cost2, lat2, err2 = call_model(args.model, prompts[predicted_type], b64, schemas[predicted_type], 2048)
        correct, total = score_fields(record["fields"], fields)
        docs.append({
            "id": record["id"], "doc_type": record["doc_type"], "predicted_type": predicted_type,
            "fields_correct": correct, "fields_total": total, "exact": correct == total and fields is not None,
            "injected_error": record["injected_error"], "cost_usd": cost1 + cost2,
            "latency_ms": lat1 + lat2, "error": err2,
        })
        if fields is not None:
            predictions.append({"id": record["id"], "doc_type": predicted_type, "fields": fields})
        print(f"{record['id']}: {correct}/{total} fields")

    results = run_validation(predictions)
    truth = {r["id"]: r for r in records}
    flagged = {i: bool(v["errors"] or v["warnings"]) for i, v in results.items()}
    summary = summarize(docs)
    summary["validation"] = validation_stats(flagged, {i: truth[i] for i in flagged})

    RAW.mkdir(parents=True, exist_ok=True)
    payload = {"experiment": args.experiment, "model": args.model, "prompts": args.prompts,
               "max_width": args.max_width, "summary": summary, "docs": docs}
    (RAW / f"{args.experiment}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def pct(value):
    return "n/a" if value is None else f"{100 * value:.1f}%"


def write_report():
    stats, per_error, total = rules_only_report()
    lines = [
        "# Evaluation results", "",
        "## Validation rules on ground-truth fields", "",
        f"Dataset: {total} synthetic documents, injected errors flagged by schema and business rules.", "",
        "| Metric | Value |", "|---|---|",
        f"| Precision | {pct(stats['precision'])} |",
        f"| Recall | {pct(stats['recall'])} |",
        f"| True positives / false positives / false negatives | {stats['tp']} / {stats['fp']} / {stats['fn']} |", "",
        "| Injected error | Detected |", "|---|---|",
    ]
    lines += [f"| {name} | {hit}/{n} |" for name, (hit, n) in sorted(per_error.items())]
    lines += ["", "## LLM experiments", ""]

    runs = [read_json(p) for p in sorted(RAW.glob("*.json"))] if RAW.exists() else []
    if not runs:
        lines.append("No experiment has been run yet. Run `python eval/run_eval.py --experiment <name> --model <model>`.")
    else:
        lines += [
            "| Experiment | Model | Prompts | Width | Docs | Class. acc | Field acc | Exact match | "
            "Val. recall | Median ms | p95 ms | $/doc |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for run in runs:
            s = run["summary"]
            lines.append(
                f"| {run['experiment']} | {run['model']} | {run['prompts']} | {run['max_width']} | {s['documents']} | "
                f"{pct(s['classification_accuracy'])} | {pct(s['field_accuracy'])} | {pct(s['exact_match'])} | "
                f"{pct(s['validation']['recall'])} | {s['latency_median_ms']:.0f} | {s['latency_p95_ms']:.0f} | "
                f"{s['cost_per_doc_usd']:.4f} |"
            )
    (ROOT / "eval" / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote eval/results.md")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", help="name of the run, used as the raw result filename")
    parser.add_argument("--model", default=os.environ.get("PRIMARY_MODEL", "claude-sonnet-5-5"))
    parser.add_argument("--prompts", choices=["v1", "v2"], default="v1")
    parser.add_argument("--max-width", type=int, default=1600)
    parser.add_argument("--limit", type=int, default=0, help="documents per type, 0 for all")
    parser.add_argument("--report", action="store_true", help="rebuild eval/results.md from stored runs")
    args = parser.parse_args()

    if args.report or not args.experiment:
        write_report()
        return
    run_experiment(args)
    write_report()


if __name__ == "__main__":
    main()
