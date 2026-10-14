const body = $input.first().json.body || {};
let kind = 'other';
if (body.callback_query) kind = 'callback';
else if (body.message && (body.message.document || body.message.photo)) kind = 'file';
return [{ json: { kind, body } }];
