const http = (options) => this.helpers.httpRequest(options);
const PRICING = JSON.parse($env.MODEL_PRICING || '{}');
const TELEGRAM_API = `https://api.telegram.org/bot${$env.TELEGRAM_BOT_TOKEN}`;

const telegram = (method, body) => http({ method: 'POST', url: `${TELEGRAM_API}/${method}`, body, json: true });
const say = (chatId, text, extra = {}) => telegram('sendMessage', { chat_id: chatId, text, ...extra });

const costOf = (model, tokensIn, tokensOut) => {
  const [priceIn, priceOut] = PRICING[model] || [0, 0];
  return Number(((tokensIn * priceIn + tokensOut * priceOut) / 1e6).toFixed(6));
};

async function callClaude(model, system, mime, b64, schema, maxTokens) {
  const media = mime === 'application/pdf' ? 'document' : 'image';
  const res = await http({
    method: 'POST',
    url: 'https://api.anthropic.com/v1/messages',
    headers: { 'x-api-key': $env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01' },
    body: {
      model,
      max_tokens: maxTokens,
      system,
      tools: [{ name: 'record', description: 'Record the result', input_schema: schema }],
      tool_choice: { type: 'tool', name: 'record' },
      messages: [{
        role: 'user',
        content: [
          { type: media, source: { type: 'base64', media_type: mime, data: b64 } },
          { type: 'text', text: 'Process this document.' },
        ],
      }],
    },
    json: true,
    timeout: 90000,
  });
  const block = (res.content || []).find((c) => c.type === 'tool_use');
  if (!block) throw new Error('model returned no structured output');
  return { data: block.input, tokensIn: res.usage.input_tokens, tokensOut: res.usage.output_tokens };
}

async function callOpenAI(model, system, mime, b64, schema, maxTokens) {
  const dataUrl = `data:${mime};base64,${b64}`;
  const part = mime === 'application/pdf'
    ? { type: 'file', file: { filename: 'document.pdf', file_data: dataUrl } }
    : { type: 'image_url', image_url: { url: dataUrl } };
  const res = await http({
    method: 'POST',
    url: 'https://api.openai.com/v1/chat/completions',
    headers: { Authorization: `Bearer ${$env.OPENAI_API_KEY}` },
    body: {
      model,
      max_tokens: maxTokens,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: [part, { type: 'text', text: 'Process this document.' }] },
      ],
      response_format: { type: 'json_schema', json_schema: { name: 'record', schema } },
    },
    json: true,
    timeout: 90000,
  });
  return {
    data: JSON.parse(res.choices[0].message.content),
    tokensIn: res.usage.prompt_tokens,
    tokensOut: res.usage.completion_tokens,
  };
}

// Tries the primary model twice, then the fallback model once
async function runLLM(step, system, mime, b64, schema, maxTokens) {
  const models = [$env.PRIMARY_MODEL, $env.PRIMARY_MODEL, $env.FALLBACK_MODEL].filter(Boolean);
  const usage = [];
  let lastError = 'no model configured';
  for (const model of models) {
    const started = Date.now();
    try {
      const call = model.startsWith('claude') ? callClaude : callOpenAI;
      const r = await call(model, system, mime, b64, schema, maxTokens);
      usage.push({
        step, model, tokens_in: r.tokensIn, tokens_out: r.tokensOut,
        cost_usd: costOf(model, r.tokensIn, r.tokensOut), latency_ms: Date.now() - started,
      });
      return { data: r.data, model, usage };
    } catch (e) {
      lastError = e.message;
      usage.push({ step, model, tokens_in: 0, tokens_out: 0, cost_usd: 0, latency_ms: Date.now() - started });
    }
  }
  return { error: lastError, usage };
}
