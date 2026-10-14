const doc = $input.first().json;
const json = (value) => JSON.stringify(value === undefined ? null : value);
const validation = doc.validation || { warnings: [], errors: [] };

doc.document_row = {
  id: doc.id,
  source: doc.source,
  doc_type: doc.doc_type || '',
  status: doc.status,
  confidence: doc.confidence === undefined ? '' : doc.confidence,
  created_at: doc.created_at,
};
doc.extraction_row = {
  id: `${doc.id}-x`,
  document_id: doc.id,
  data: json(doc.extraction),
  warnings: json(validation.warnings),
  errors: json(validation.errors),
  model: doc.model || '',
};
doc.log_rows = (doc.usage || []).map((u, i) => ({
  id: `${doc.id}-${i}`,
  document_id: doc.id,
  step: u.step,
  tokens_in: u.tokens_in,
  tokens_out: u.tokens_out,
  cost_usd: u.cost_usd,
  latency_ms: u.latency_ms,
}));
return [{ json: doc }];
