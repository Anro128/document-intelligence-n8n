/*INCLUDE:lib.js*/
const doc = $input.first().json;
const data = doc.extraction ? JSON.stringify(doc.extraction, null, 1).slice(0, 1500) : 'no extraction';
const text = `Needs review (${doc.doc_type || 'unknown'}, id ${doc.id.slice(0, 8)})\n${doc.reason}\n\n${data}`;

await say(doc.chat_id, text, {
  reply_markup: {
    inline_keyboard: [[
      { text: 'Approve', callback_data: `approve:${doc.id}` },
      { text: 'Reject', callback_data: `reject:${doc.id}` },
    ]],
  },
});
return [{ json: doc }];
