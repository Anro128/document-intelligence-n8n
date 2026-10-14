const fs = require('fs');
const path = require('path');
const { validate } = require('./validate.js');

const root = path.resolve(__dirname, '..', '..');
const read = (p) => JSON.parse(fs.readFileSync(path.join(root, p), 'utf8'));

const schemas = {
  invoice: read('schemas/invoice.schema.json'),
  ktp: read('schemas/ktp.schema.json'),
  spk: read('schemas/spk.schema.json'),
};
const catalog = read('schemas/vehicle_catalog.json');

// Reads [{id, doc_type, fields}] from stdin and prints [{id, valid, warnings, errors}]
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const today = new Date().toISOString().slice(0, 10);
const results = input.map((item) => ({
  id: item.id,
  ...validate(item.doc_type, item.fields, { schemas, catalog, today }),
}));
process.stdout.write(JSON.stringify(results));
