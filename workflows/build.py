"""Builds the importable n8n workflow JSON files from workflows/code, schemas and prompts."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "workflows" / "code"
DOC_TYPES = ["invoice", "ktp", "spk"]
SHEETS_CREDENTIAL = {"googleApi": {"id": "", "name": "Google Service Account"}}
ERROR_WORKFLOW = "docintel07"


def read_schema(doc_type):
    schema = json.loads((ROOT / "schemas" / f"{doc_type}.schema.json").read_text(encoding="utf-8"))
    schema.pop("$schema", None)
    schema.pop("title", None)
    return schema


def expand(source):
    prompts = {t: (ROOT / "prompts" / f"extract_{t}.md").read_text(encoding="utf-8").strip() for t in DOC_TYPES}
    catalog = json.loads((ROOT / "schemas" / "vehicle_catalog.json").read_text(encoding="utf-8"))
    source = source.replace("/*INCLUDE:lib.js*/", (CODE / "lib.js").read_text(encoding="utf-8"))
    source = source.replace("/*SCHEMAS*/null", json.dumps({t: read_schema(t) for t in DOC_TYPES}))
    source = source.replace("/*CATALOG*/null", json.dumps(catalog))
    source = source.replace("/*PROMPTS*/null", json.dumps(prompts))

    def prompt(match):
        text = (ROOT / "prompts" / f"{match.group(1)}.md").read_text(encoding="utf-8").strip()
        return json.dumps(text)

    return re.sub(r"/\*PROMPT:(\w+)\*/''", prompt, source)


class Flow:
    def __init__(self, wf_id, name, error_handler=True):
        self.wf_id, self.name = wf_id, name
        self.nodes, self.links = [], {}
        self.settings = {"executionOrder": "v1"}
        if error_handler:
            self.settings["errorWorkflow"] = ERROR_WORKFLOW

    def add(self, name, node_type, version, params, col, row=0, **extra):
        node = {"parameters": params, "name": name, "type": node_type, "typeVersion": version,
                "position": [260 * col, 220 * row]}
        node.update(extra)
        self.nodes.append(node)
        return name

    def code(self, name, filename, col, row=0):
        source = expand((CODE / filename).read_text(encoding="utf-8"))
        return self.add(name, "n8n-nodes-base.code", 2, {"jsCode": source}, col, row)

    def sheet(self, name, tab, mapping, col, row=0, **extra):
        params = {
            "authentication": "serviceAccount",
            "operation": "appendOrUpdate",
            "documentId": {"__rl": True, "value": "={{ $env.SHEET_ID }}", "mode": "id"},
            "sheetName": {"__rl": True, "value": tab, "mode": "name"},
            "columns": {"mappingMode": "defineBelow", "value": mapping,
                        "matchingColumns": ["id"], "schema": []},
            "options": {},
        }
        return self.add(name, "n8n-nodes-base.googleSheets", 4.5, params, col, row,
                        credentials=SHEETS_CREDENTIAL, **extra)

    def sheet_read(self, name, tab, col, row=0, **extra):
        params = {
            "authentication": "serviceAccount",
            "documentId": {"__rl": True, "value": "={{ $env.SHEET_ID }}", "mode": "id"},
            "sheetName": {"__rl": True, "value": tab, "mode": "name"},
            "options": {},
        }
        return self.add(name, "n8n-nodes-base.googleSheets", 4.5, params, col, row,
                        credentials=SHEETS_CREDENTIAL, **extra)

    def run_workflow(self, name, wf_id, col, row=0):
        return self.add(name, "n8n-nodes-base.executeWorkflow", 1.1,
                        {"source": "database", "workflowId": wf_id, "options": {}}, col, row)

    def switch(self, name, expression, outputs, col, row=0):
        params = {"mode": "expression", "numberOutputs": outputs, "output": expression}
        return self.add(name, "n8n-nodes-base.switch", 3, params, col, row)

    def link(self, source, target, output=0):
        outputs = self.links.setdefault(source, [])
        while len(outputs) <= output:
            outputs.append([])
        outputs[output].append({"node": target, "type": "main", "index": 0})

    def chain(self, *names):
        for a, b in zip(names, names[1:]):
            self.link(a, b)

    def to_json(self):
        connections = {src: {"main": outs} for src, outs in self.links.items()}
        return {"id": self.wf_id, "name": self.name, "nodes": self.nodes,
                "connections": connections, "settings": self.settings, "active": False}


def if_node(flow, name, left, operator, right, col, row=0):
    cond = {"id": name.lower().replace(" ", "-"), "leftValue": left, "rightValue": right, "operator": operator}
    params = {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                             "conditions": [cond], "combinator": "and"}, "options": {}}
    return flow.add(name, "n8n-nodes-base.if", 2.2, params, col, row)


def intake():
    f = Flow("docintel01", "01 Intake")
    hook = f.add("Telegram webhook", "n8n-nodes-base.webhook", 2,
                 {"httpMethod": "POST", "path": "telegram", "responseMode": "onReceived", "options": {}},
                 0, webhookId="docintel-telegram")
    parse = f.code("Parse update", "parse_update.js", 1)
    route = f.switch("Route update", "={{ ({file: 0, callback: 1}[$json.kind] ?? 2) }}", 3, 2)
    f.chain(hook, parse, route)

    store = f.code("Check and store", "intake_check.js", 3, 0)
    log = f.sheet("Log received", "documents", {
        "id": "={{ $json.id }}", "source": "={{ $json.source }}", "doc_type": "",
        "status": "={{ $json.status }}", "confidence": "", "created_at": "={{ $json.created_at }}"}, 4)
    restore = f.code("Restore intake", "restore_intake.js", 5)
    gate = f.code("Cost gate", "cost_gate.js", 6)
    pre = f.run_workflow("Preprocess", "docintel02", 7)
    classify = f.run_workflow("Classify", "docintel03", 8)
    extract = f.run_workflow("Extract", "docintel04", 9)
    validate = f.run_workflow("Validate", "docintel05", 10)
    spend = f.code("Record spend", "record_spend.js", 11)
    notify = f.run_workflow("Route and notify", "docintel06", 12)
    f.link(route, store, 0)
    f.chain(store, log, restore, gate, pre, classify, extract, validate, spend, notify)

    cb = f.code("Parse callback", "callback_parse.js", 3, 2)
    decision = f.sheet("Update decision", "documents", {
        "id": "={{ $json.id }}", "status": "={{ $json.status }}"}, 4, 2)
    confirm = f.code("Confirm callback", "callback_confirm.js", 5, 2)
    f.link(route, cb, 1)
    f.chain(cb, decision, confirm)

    helper = f.code("Help reply", "help_reply.js", 3, 4)
    f.link(route, helper, 2)
    return f


def preprocess():
    f = Flow("docintel02", "02 Preprocess")
    start = f.add("Start", "n8n-nodes-base.executeWorkflowTrigger", 1, {}, 0)
    is_image = if_node(f, "Is image", "={{ $json.mime }}",
                       {"type": "string", "operation": "notEquals"}, "application/pdf", 1)
    read = f.add("Read file", "n8n-nodes-base.readWriteFile", 1,
                 {"operation": "read", "fileSelector": "={{ $json.file_path }}",
                  "options": {"dataPropertyName": "data"}}, 2, 0)
    resize = f.add("Resize image", "n8n-nodes-base.editImage", 1,
                   {"operation": "resize", "dataPropertyName": "data", "width": 1600, "height": 1600,
                    "resizeOption": "onlyIfLarger", "options": {}}, 3, 0)
    write = f.add("Write file", "n8n-nodes-base.readWriteFile", 1,
                  {"operation": "write", "fileName": "={{ $('Start').first().json.file_path }}",
                   "dataPropertyName": "data", "options": {}}, 4, 0)
    restore = f.code("Restore", "restore_trigger.js", 5, 0)
    pages = f.code("Count PDF pages", "pdf_pages.js", 2, 1)
    f.chain(start, is_image)
    f.link(is_image, read, 0)
    f.chain(read, resize, write, restore)
    f.link(is_image, pages, 1)
    return f


def single_step(wf_id, name, node_name, filename):
    f = Flow(wf_id, name)
    start = f.add("Start", "n8n-nodes-base.executeWorkflowTrigger", 1, {}, 0)
    step = f.code(node_name, filename, 1)
    f.chain(start, step)
    return f


def route_notify():
    f = Flow("docintel06", "06 Route and notify")
    start = f.add("Start", "n8n-nodes-base.executeWorkflowTrigger", 1, {}, 0)
    decide = f.code("Decide", "route_decide.js", 1)
    f.chain(start, decide)

    route = f.switch("Route status", "={{ ({valid: 0, needs_review: 1}[$json.status] ?? 2) }}", 3, 2)
    ok = f.code("Notify valid", "notify_valid.js", 3, 0)
    review = f.code("Notify review", "notify_review.js", 3, 1)
    failed = f.code("Notify failed", "notify_failed.js", 3, 2)
    cleanup = f.code("Cleanup", "cleanup.js", 4, 1)
    f.link(decide, route)
    f.link(route, ok, 0)
    f.link(route, review, 1)
    f.link(route, failed, 2)
    for node in (ok, review, failed):
        f.link(node, cleanup)

    has_extraction = if_node(f, "Has extraction", "={{ !!$json.extraction }}",
                             {"type": "boolean", "operation": "true", "singleValue": True}, "", 2, 4)
    write_x = f.sheet("Write extraction", "extractions", {
        "id": "={{ $json.extraction_row.id }}", "document_id": "={{ $json.extraction_row.document_id }}",
        "data": "={{ $json.extraction_row.data }}", "warnings": "={{ $json.extraction_row.warnings }}",
        "errors": "={{ $json.extraction_row.errors }}", "model": "={{ $json.extraction_row.model }}"}, 3, 4)
    restore = f.code("Restore decide", "restore_decide.js", 4, 4)
    write_doc = f.sheet("Write document", "documents", {
        "id": "={{ $json.document_row.id }}", "source": "={{ $json.document_row.source }}",
        "doc_type": "={{ $json.document_row.doc_type }}", "status": "={{ $json.document_row.status }}",
        "confidence": "={{ $json.document_row.confidence }}",
        "created_at": "={{ $json.document_row.created_at }}"}, 5, 4)
    rows = f.code("Log rows", "log_rows.js", 6, 4)
    write_logs = f.sheet("Write run logs", "run_logs", {
        "id": "={{ $json.id }}", "document_id": "={{ $json.document_id }}", "step": "={{ $json.step }}",
        "tokens_in": "={{ $json.tokens_in }}", "tokens_out": "={{ $json.tokens_out }}",
        "cost_usd": "={{ $json.cost_usd }}", "latency_ms": "={{ $json.latency_ms }}"}, 7, 4)
    f.link(decide, has_extraction)
    f.link(has_extraction, write_x, 0)
    f.link(has_extraction, restore, 1)
    f.chain(write_x, restore, write_doc, rows, write_logs)
    return f


def error_handler():
    f = Flow("docintel07", "07 Error handler", error_handler=False)
    trigger = f.add("Error trigger", "n8n-nodes-base.errorTrigger", 1, {}, 0)
    notify = f.code("Notify admin", "error_notify.js", 1)
    log = f.sheet("Log error", "run_logs", {
        "id": "={{ $json.id }}", "document_id": "", "step": "={{ $json.step }}",
        "tokens_in": 0, "tokens_out": 0, "cost_usd": 0, "latency_ms": 0}, 2)
    f.chain(trigger, notify, log)
    return f


def weekly_report():
    f = Flow("docintel08", "08 Weekly report")
    trigger = f.add("Weekly", "n8n-nodes-base.scheduleTrigger", 1.2,
                    {"rule": {"interval": [{"field": "weeks", "triggerAtDay": [1], "triggerAtHour": 8}]}}, 0)
    docs = f.sheet_read("Read documents", "documents", 1)
    logs = f.sheet_read("Read run logs", "run_logs", 2, executeOnce=True)
    report = f.code("Report", "report.js", 3)
    f.chain(trigger, docs, logs, report)
    return f


def main():
    flows = {
        "01-intake": intake(),
        "02-preprocess": preprocess(),
        "03-classify": single_step("docintel03", "03 Classify", "Classify", "classify.js"),
        "04-extract": single_step("docintel04", "04 Extract", "Extract", "extract.js"),
        "05-validate": single_step("docintel05", "05 Validate", "Validate", "validate.js"),
        "06-route-notify": route_notify(),
        "07-error-handler": error_handler(),
        "08-weekly-report": weekly_report(),
    }
    for filename, flow in flows.items():
        path = ROOT / "workflows" / f"{filename}.json"
        path.write_text(json.dumps(flow.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(flows)} workflows")


if __name__ == "__main__":
    main()
