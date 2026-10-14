const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..', '..');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

const nodeCode = (file, name) => {
  const wf = JSON.parse(fs.readFileSync(path.join(root, 'workflows', file), 'utf8'));
  return wf.nodes.find((n) => n.name === name).parameters.jsCode;
};

async function run(code, { doc, env = {}, http }) {
  const fn = new AsyncFunction('$input', '$env', '$getWorkflowStaticData', '$', 'require', code);
  const ctx = { helpers: { httpRequest: http } };
  const envFull = {
    PRIMARY_MODEL: 'claude-test',
    FALLBACK_MODEL: 'gpt-test',
    MODEL_PRICING: '{"claude-test":[3,15],"gpt-test":[1,2]}',
    CLASSIFY_MIN_CONFIDENCE: '0.7',
    TELEGRAM_BOT_TOKEN: 't',
    ...env,
  };
  const out = await fn.call(ctx, { first: () => ({ json: doc }) }, envFull, () => ({}), () => ({}), require);
  return out[0].json;
}

const claudeReply = (input) => ({ content: [{ type: 'tool_use', input }], usage: { input_tokens: 1000, output_tokens: 100 } });
const sample = (name) => path.join(root, 'data', 'synthetic', name);
const truth = (name) => JSON.parse(fs.readFileSync(path.join(root, 'data', 'ground_truth', name), 'utf8'));
const baseDoc = (file) => ({ id: 'x', status: 'received', mime: 'image/jpeg', file_path: sample(file), usage: [] });

(async () => {
  const classify = nodeCode('03-classify.json', 'Classify');
  const extract = nodeCode('04-extract.json', 'Extract');
  const validate = nodeCode('05-validate.json', 'Validate');

  let doc = await run(classify, {
    doc: baseDoc('ktp_001.jpg'),
    http: async () => claudeReply({ type: 'ktp', confidence: 0.95 }),
  });
  assert.strictEqual(doc.doc_type, 'ktp');
  assert.strictEqual(doc.status, 'received');
  assert.strictEqual(doc.usage[0].cost_usd, 0.0045);

  doc = await run(classify, {
    doc: baseDoc('ktp_001.jpg'),
    http: async () => claudeReply({ type: 'ktp', confidence: 0.4 }),
  });
  assert.strictEqual(doc.status, 'needs_review');

  let calls = [];
  doc = await run(classify, {
    doc: baseDoc('ktp_001.jpg'),
    http: async (opts) => {
      calls.push(opts.url);
      if (opts.url.includes('anthropic')) throw new Error('overloaded');
      return { choices: [{ message: { content: '{"type":"spk","confidence":0.9}' } }], usage: { prompt_tokens: 10, completion_tokens: 5 } };
    },
  });
  assert.strictEqual(calls.filter((u) => u.includes('anthropic')).length, 2);
  assert.strictEqual(doc.doc_type, 'spk');
  assert.strictEqual(doc.usage.length, 3);

  doc = await run(classify, {
    doc: baseDoc('ktp_001.jpg'),
    http: async () => { throw new Error('down'); },
  });
  assert.strictEqual(doc.status, 'failed');

  let seen;
  doc = await run(classify, {
    doc: baseDoc('ktp_001.jpg'),
    env: { PRIMARY_MODEL: 'deepseek-test', FALLBACK_MODEL: '', DEEPSEEK_API_KEY: 'k' },
    http: async (opts) => {
      seen = opts;
      return { choices: [{ message: { content: '{"type":"invoice","confidence":0.8}' } }], usage: { prompt_tokens: 300, completion_tokens: 20 } };
    },
  });
  assert.strictEqual(seen.url, 'https://api.deepseek.com/chat/completions');
  assert.deepStrictEqual(seen.body.response_format, { type: 'json_object' });
  assert.ok(seen.body.messages[0].content.includes('JSON schema'));
  assert.strictEqual(doc.doc_type, 'invoice');

  doc = await run(classify, {
    doc: { ...baseDoc('ktp_001.jpg'), mime: 'application/pdf' },
    env: { PRIMARY_MODEL: 'deepseek-test', FALLBACK_MODEL: '' },
    http: async () => ({}),
  });
  assert.strictEqual(doc.status, 'failed');
  assert.ok(doc.reason.includes('PDF'));

  const good = truth('invoice_001.json');
  doc = await run(extract, {
    doc: { ...baseDoc('invoice_001.jpg'), doc_type: 'invoice' },
    http: async () => claudeReply(good.fields),
  });
  assert.strictEqual(doc.status, 'extracted');
  doc = await run(validate, { doc, http: async () => ({}) });
  assert.strictEqual(doc.status, 'valid');

  const broken = { ...good.fields, total: good.fields.total + 5000 };
  doc = await run(validate, { doc: { status: 'extracted', doc_type: 'invoice', extraction: broken }, http: async () => ({}) });
  assert.strictEqual(doc.status, 'needs_review');

  const noNik = { ...truth('ktp_001.json').fields, nik: '123' };
  doc = await run(validate, { doc: { status: 'extracted', doc_type: 'ktp', extraction: noNik }, http: async () => ({}) });
  assert.strictEqual(doc.status, 'failed');

  console.log('stage tests passed');
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
