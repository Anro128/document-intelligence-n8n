/*INCLUDE:lib.js*/
const fs = require('fs');
const SCHEMAS = /*SCHEMAS*/null;
const PROMPTS = /*PROMPTS*/null;

const doc = $input.first().json;
if (doc.status !== 'received') return [{ json: doc }];

const b64 = fs.readFileSync(doc.file_path).toString('base64');
const out = await runLLM('extract', PROMPTS[doc.doc_type], doc.mime, b64, SCHEMAS[doc.doc_type], 2048);
doc.usage = (doc.usage || []).concat(out.usage);

if (out.error) {
  doc.status = 'failed';
  doc.reason = `Extraction failed: ${out.error}`;
  return [{ json: doc }];
}

doc.extraction = out.data;
doc.model = out.model;
doc.status = 'extracted';
return [{ json: doc }];
