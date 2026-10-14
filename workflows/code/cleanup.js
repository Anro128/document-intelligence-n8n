const fs = require('fs');
const doc = $input.first().json;
if (doc.file_path && fs.existsSync(doc.file_path)) fs.unlinkSync(doc.file_path);
return [{ json: { id: doc.id, status: doc.status } }];
