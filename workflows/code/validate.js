const TOLERANCE = 1;

const typeOf = (v) => (v === null ? 'null' : Array.isArray(v) ? 'array' : typeof v);
const near = (a, b) => Math.abs(a - b) <= TOLERANCE;
const child = (path, key) => (path ? `${path}.${key}` : key);

function validDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return false;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return d.getUTCFullYear() === +m[1] && d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[3];
}

function checkSchema(schema, value, path, errors) {
  const t = typeOf(value);
  const label = path || 'document';
  if (schema.type) {
    const ok = schema.type === 'number' ? t === 'number' && Number.isFinite(value) : schema.type === t;
    if (!ok) {
      errors.push(`${label}: expected ${schema.type}, got ${t}`);
      return;
    }
  }
  if (schema.enum && !schema.enum.includes(value)) errors.push(`${label}: must be one of ${schema.enum.join(', ')}`);
  if (t === 'string') {
    if (schema.minLength !== undefined && value.length < schema.minLength) errors.push(`${label}: is empty`);
    if (schema.pattern && !new RegExp(schema.pattern).test(value)) errors.push(`${label}: invalid format`);
  }
  if (t === 'number') {
    if (schema.minimum !== undefined && value < schema.minimum) errors.push(`${label}: below minimum`);
    if (schema.exclusiveMinimum !== undefined && value <= schema.exclusiveMinimum) {
      errors.push(`${label}: must be greater than ${schema.exclusiveMinimum}`);
    }
  }
  if (t === 'array') {
    if (schema.minItems !== undefined && value.length < schema.minItems) errors.push(`${label}: needs at least ${schema.minItems} item(s)`);
    if (schema.items) value.forEach((item, i) => checkSchema(schema.items, item, `${path}[${i}]`, errors));
  }
  if (t === 'object') {
    for (const key of schema.required || []) {
      if (!(key in value)) errors.push(`${child(path, key)}: missing`);
    }
    for (const [key, sub] of Object.entries(schema.properties || {})) {
      if (key in value) checkSchema(sub, value[key], child(path, key), errors);
    }
  }
}

function invoiceRules(d, ctx, out) {
  if (!validDate(d.date)) out.errors.push('date: not a valid calendar date');
  else if (d.date > ctx.today) out.warnings.push('date: is in the future');
  const sum = d.line_items.reduce((s, i) => s + i.amount, 0);
  if (!near(sum, d.subtotal)) out.warnings.push(`subtotal: line items sum to ${sum}, document says ${d.subtotal}`);
  if (!near(d.subtotal + d.tax, d.total)) out.warnings.push(`total: subtotal + tax is ${d.subtotal + d.tax}, document says ${d.total}`);
  d.line_items.forEach((item, n) => {
    if (!near(item.quantity * item.unit_price, item.amount)) out.warnings.push(`line_items[${n}]: quantity x unit_price differs from amount`);
  });
}

function ktpRules(d, ctx, out) {
  if (!validDate(d.birth_date)) {
    out.errors.push('birth_date: not a valid calendar date');
    return;
  }
  if (d.birth_date > ctx.today) out.warnings.push('birth_date: is in the future');
  const day = Number(d.nik.slice(6, 8));
  const month = Number(d.nik.slice(8, 10));
  const year = Number(d.nik.slice(10, 12));
  const [y, m, dd] = d.birth_date.split('-').map(Number);
  const nikGender = day > 40 ? 'female' : 'male';
  if ((day > 40 ? day - 40 : day) !== dd || month !== m || year !== y % 100) {
    out.warnings.push('nik: date segment does not match birth_date');
  }
  if (nikGender !== d.gender) out.warnings.push('nik: gender segment does not match gender');
}

function spkRules(d, ctx, out) {
  const key = Object.keys(ctx.catalog).find((k) => k.toLowerCase() === d.model.toLowerCase());
  if (!key) {
    out.warnings.push(`model: ${d.model} is not in the catalog`);
    return;
  }
  const info = ctx.catalog[key];
  if (!info.variants.some((v) => v.toLowerCase() === d.variant.toLowerCase())) {
    out.warnings.push(`variant: ${d.variant} is not a known ${key} variant`);
  }
  const [low, high] = info.price;
  if (d.price < low || d.price > high) out.warnings.push(`price: ${d.price} is outside the expected ${low}-${high} range for ${key}`);
}

const RULES = { invoice: invoiceRules, ktp: ktpRules, spk: spkRules };

function validate(docType, data, ctx) {
  const out = { valid: false, warnings: [], errors: [] };
  const schema = ctx.schemas[docType];
  if (!schema || !RULES[docType]) {
    out.errors.push(`no validation available for document type ${docType}`);
    return out;
  }
  checkSchema(schema, data, '', out.errors);
  if (out.errors.length === 0) RULES[docType](data, ctx, out);
  out.valid = out.errors.length === 0 && out.warnings.length === 0;
  return out;
}

if (typeof module !== 'undefined' && module.exports) module.exports = { validate };

if (typeof $input !== 'undefined') {
  const SCHEMAS = /*SCHEMAS*/null;
  const CATALOG = /*CATALOG*/null;
  const doc = $input.first().json;
  if (doc.status !== 'extracted') return [{ json: doc }];
  const result = validate(doc.doc_type, doc.extraction, {
    schemas: SCHEMAS,
    catalog: CATALOG,
    today: new Date().toISOString().slice(0, 10),
  });
  doc.validation = result;
  if (result.errors.length) {
    doc.status = 'failed';
    doc.reason = `Validation errors: ${result.errors.join('; ')}`;
  } else if (result.warnings.length) {
    doc.status = 'needs_review';
    doc.reason = `Needs review: ${result.warnings.join('; ')}`;
  } else {
    doc.status = 'valid';
  }
  return [{ json: doc }];
}
