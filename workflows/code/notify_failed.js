/*INCLUDE:lib.js*/
const doc = $input.first().json;
await say(doc.chat_id, `Document could not be processed.\nReason: ${doc.reason || 'unknown error'}`);
return [{ json: doc }];
