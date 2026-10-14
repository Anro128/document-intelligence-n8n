/*INCLUDE:lib.js*/
const fs = require('fs');
const { randomUUID } = require('crypto');

const MAX_BYTES = 5 * 1024 * 1024;
const MIME_EXT = { 'application/pdf': 'pdf', 'image/jpeg': 'jpg', 'image/png': 'png' };

const message = $input.first().json.body.message;
const chatId = message.chat.id;
const file = message.document
  || (message.photo && { ...message.photo[message.photo.length - 1], mime_type: 'image/jpeg' });

if (!file) {
  await say(chatId, 'Send a PDF, JPG or PNG document to process.');
  return [];
}
const mime = file.mime_type;
if (!MIME_EXT[mime]) {
  await say(chatId, 'Unsupported file type. Send a PDF, JPG or PNG.');
  return [];
}
if (file.file_size > MAX_BYTES) {
  await say(chatId, 'File is larger than 5MB. Send a smaller file.');
  return [];
}

const info = await telegram('getFile', { file_id: file.file_id });
const bytes = await http({
  method: 'GET',
  url: `https://api.telegram.org/file/bot${$env.TELEGRAM_BOT_TOKEN}/${info.result.file_path}`,
  encoding: 'arraybuffer',
  json: false,
});

const id = randomUUID();
const filePath = `/files/${id}.${MIME_EXT[mime]}`;
fs.writeFileSync(filePath, Buffer.from(bytes));
await say(chatId, 'Document received, processing...');

return [{
  json: {
    id,
    source: 'telegram',
    chat_id: chatId,
    mime,
    file_path: filePath,
    status: 'received',
    usage: [],
    created_at: new Date().toISOString(),
  },
}];
