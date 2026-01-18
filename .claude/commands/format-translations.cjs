const fs = require('fs');
const path = require('path');

const dir = './js/ui/third/base-translation';
const files = fs.readdirSync(dir).filter(f => f.startsWith('base-') && f.endsWith('.js'));

files.forEach(file => {
const filePath = path.join(dir, file);
let content = fs.readFileSync(filePath, 'utf8');

const match = content.match(/^const (\w+)\s*=\s*(\{[\s\S]*\});?\s*$/);
if (!match) {
console.log('Skip:', file, '(pattern not matched)');
return;
}

const varName = match[1];
let objStr = match[2];

objStr = objStr.replace(/([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:/g, '$1"$2":');
objStr = objStr.replace(/,\s*\}/g, '}');

try {
const obj = JSON.parse(objStr);
const formatted = JSON.stringify(obj, null, 0)
.replace(/^\{/, '{\n')
.replace(/\}$/, '\n}')
.replace(/","/g, '",\n"');

const newContent = `const ${varName} = ${formatted};`;
fs.writeFileSync(filePath, newContent, 'utf8');
const lines = newContent.split('\n').length;
console.log('Formatted:', file, '(' + lines + ' lines)');
} catch (e) {
console.log('Error:', file, e.message);
}
});

console.log('Done!');
