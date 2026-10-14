/*INCLUDE:lib.js*/
const doc = $input.first().json;
const lines = Object.entries(doc.extraction)
  .filter(([, v]) => typeof v !== 'object')
  .map(([k, v]) => `${k}: ${v}`);

await say(doc.chat_id, `Document processed (${doc.doc_type}).\n${lines.join('\n')}`);
return [{ json: doc }];
