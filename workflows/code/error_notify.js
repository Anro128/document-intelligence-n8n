/*INCLUDE:lib.js*/
const err = $input.first().json;
const execution = err.execution || {};
const workflow = err.workflow || {};
const message = (execution.error && execution.error.message) || 'unknown error';
const node = execution.lastNodeExecuted || 'unknown node';

await say($env.TELEGRAM_ADMIN_CHAT_ID, `Workflow failed: ${workflow.name}\nNode: ${node}\n${message}\n${execution.url || ''}`);

return [{
  json: {
    id: `err-${execution.id || Date.now()}`,
    document_id: '',
    step: `error:${workflow.name}`,
    tokens_in: 0,
    tokens_out: 0,
    cost_usd: 0,
    latency_ms: 0,
  },
}];
