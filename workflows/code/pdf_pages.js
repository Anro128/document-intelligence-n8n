const fs = require('fs');
const MAX_PAGES = 10;

const doc = $input.first().json;
const raw = fs.readFileSync(doc.file_path).toString('latin1');
doc.pages = (raw.match(/\/Type\s*\/Page(?![s\w])/g) || []).length;

if (doc.pages > MAX_PAGES) {
  doc.status = 'failed';
  doc.reason = `PDF has ${doc.pages} pages, the limit is ${MAX_PAGES}`;
}
return [{ json: doc }];
