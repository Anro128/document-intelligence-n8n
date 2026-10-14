/*INCLUDE:lib.js*/
const cb = $('Parse callback').first().json;
await telegram('answerCallbackQuery', { callback_query_id: cb.callback_id, text: `Marked as ${cb.status}` });
await telegram('editMessageReplyMarkup', {
  chat_id: cb.chat_id,
  message_id: cb.message_id,
  reply_markup: { inline_keyboard: [] },
});
await say(cb.chat_id, `Document ${cb.id.slice(0, 8)} ${cb.status}.`);
return [{ json: cb }];
