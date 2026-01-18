const fs = require('fs');

const content = fs.readFileSync('js/ui/third/base-translation/base-ja.js', 'utf8');
const match = content.match(/^const (\w+)\s*=\s*(\{[\s\S]*\});?\s*$/);
let objStr = match[2];

objStr = objStr.replace(/([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:/g, '$1"$2":');

try {
JSON.parse(objStr);
console.log('OK');
} catch (e) {
const pos = parseInt(e.message.match(/position (\d+)/)[1]);
console.log('Error at position:', pos);
console.log('Context:', objStr.substring(pos - 50, pos + 50));
console.log('Char at pos:', objStr.charCodeAt(pos), JSON.stringify(objStr[pos]));
}
