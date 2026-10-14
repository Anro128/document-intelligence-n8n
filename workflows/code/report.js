/*INCLUDE:lib.js*/
const since = new Date(Date.now() - 7 * 24 * 3600 * 1000).toISOString();
const docs = $('Read documents').all().map((i) => i.json).filter((d) => String(d.created_at) >= since);
const logs = $('Read run logs').all().map((i) => i.json);
const recentIds = new Set(docs.map((d) => d.id));
const mine = logs.filter((l) => recentIds.has(l.document_id));

const count = (status) => docs.filter((d) => d.status === status).length;
const cost = mine.reduce((s, l) => s + Number(l.cost_usd || 0), 0);
const latencies = mine.map((l) => Number(l.latency_ms || 0)).sort((a, b) => a - b);
const median = latencies.length ? latencies[Math.floor(latencies.length / 2)] : 0;
const pct = (n) => (docs.length ? `${Math.round((100 * n) / docs.length)}%` : '0%');

const text = [
  'Weekly document report',
  `Documents: ${docs.length}`,
  `Valid: ${count('valid') + count('approved')} (${pct(count('valid') + count('approved'))})`,
  `Needs review / rejected: ${count('needs_review') + count('rejected')} (${pct(count('needs_review') + count('rejected'))})`,
  `Failed: ${count('failed')} (${pct(count('failed'))})`,
  `Cost: $${cost.toFixed(4)}`,
  `Median step latency: ${median} ms`,
].join('\n');

await say($env.TELEGRAM_ADMIN_CHAT_ID, text);
return [{ json: { text } }];
