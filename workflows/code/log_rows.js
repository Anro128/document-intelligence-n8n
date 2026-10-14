const doc = $('Decide').first().json;
return doc.log_rows.map((row) => ({ json: row }));
