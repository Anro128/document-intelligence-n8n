const doc = $input.first().json;
const store = $getWorkflowStaticData('global');
const today = new Date().toISOString().slice(0, 10);
const added = (doc.usage || []).reduce((sum, u) => sum + u.cost_usd, 0);

const base = store.spend && store.spend.day === today ? store.spend.usd : 0;
store.spend = { day: today, usd: base + added };
return [{ json: doc }];
