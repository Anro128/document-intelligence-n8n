/*INCLUDE:lib.js*/
const doc = $input.first().json;
const store = $getWorkflowStaticData('global');
const today = new Date().toISOString().slice(0, 10);
const spent = store.spend && store.spend.day === today ? store.spend.usd : 0;

if (spent >= Number($env.DAILY_COST_CAP_USD || 2)) {
  await say(doc.chat_id, 'Daily processing limit reached. Try again tomorrow.');
  return [];
}
return [{ json: doc }];
