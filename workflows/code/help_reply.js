/*INCLUDE:lib.js*/
const message = $input.first().json.body.message;
if (message && message.chat && message.chat.type === 'private') {
  await say(message.chat.id, 'Send an invoice, KTP or SPK as PDF, JPG or PNG (max 5MB, 10 pages).');
}
return [];
