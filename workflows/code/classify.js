/*INCLUDE:lib.js*/
const fs = require('fs');
const CLASSIFY_PROMPT = /*PROMPT:classify*/'';
const SCHEMA = {
  type: 'object',
  required: ['type', 'confidence'],
  properties: {
    type: { type: 'string', enum: ['invoice', 'ktp', 'spk', 'other'] },
    confidence: { type: 'number', minimum: 0, maximum: 1 },
  },
};

const doc = $input.first().json;
if (doc.status !== 'received') return [{ json: doc }];

const b64 = fs.readFileSync(doc.file_path).toString('base64');
const out = await runLLM('classify', CLASSIFY_PROMPT, doc.mime, b64, SCHEMA, 200);
doc.usage = (doc.usage || []).concat(out.usage);

if (out.error) {
  doc.status = 'failed';
  doc.reason = `Classification failed: ${out.error}`;
  return [{ json: doc }];
}

doc.doc_type = out.data.type;
doc.confidence = out.data.confidence;
const minimum = Number($env.CLASSIFY_MIN_CONFIDENCE || 0.7);

if (doc.doc_type === 'other') {
  doc.status = 'failed';
  doc.reason = 'Unsupported document type';
} else if (doc.confidence < minimum) {
  doc.status = 'needs_review';
  doc.reason = `Low classification confidence (${doc.confidence})`;
}
return [{ json: doc }];
