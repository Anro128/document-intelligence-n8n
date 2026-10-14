const query = $input.first().json.body.callback_query;
const [decision, id] = String(query.data || '').split(':');
const valid = ['approve', 'reject'].includes(decision) && id;
if (!valid) return [];

return [{
  json: {
    id,
    decision,
    status: decision === 'approve' ? 'approved' : 'rejected',
    chat_id: query.message.chat.id,
    message_id: query.message.message_id,
    callback_id: query.id,
  },
}];
