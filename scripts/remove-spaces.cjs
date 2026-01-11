/**
 * JSファイルからインデントと不要なスペースを削除するスクリプト
 * 使用方法: npm run format
 *
 * 削除対象:
 * - 行頭のインデント（スペース/タブ）
 * - 行末の空白
 * - 演算子周りのスペース（=, +, -, *, /, <, >, !, &, |, ^）
 * - カンマ後のスペース
 * - セミコロン後のスペース
 * - 括弧内側のスペース
 *
 * 保持対象:
 * - 文字列リテラル内のスペース
 * - コメント内のスペース
 * - 改行
 */
const fs = require('fs');
const path = require('path');
const excludeDirs = ['json_js', 'test', 'third', '01_build', '02_images_svg', '03_images', '99_doc', 'font', 'node_modules', '.git'];
function removeSpaces(code) {
let preserved = [];
let index = 0;
let result = code.replace(/(\/\/[^\n]*|\/\*[\s\S]*?\*\/|`(?:[^`\\]|\\.)*`|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, (match) => {
preserved.push(match);
return `__PRESERVED_${index++}__`;
});
result = result.replace(/^[ \t]+/gm, '');
result = result.replace(/[ \t]+$/gm, '');
result = result.replace(/([=!<>+\-*/%&|^])[ \t]+(?=\S)/g, '$1');
result = result.replace(/(?<=\S)[ \t]+([=!<>+\-*/%&|^])/g, '$1');
result = result.replace(/,[ \t]+/g, ',');
result = result.replace(/;[ \t]+/g, ';');
result = result.replace(/\([ \t]+/g, '(');
result = result.replace(/[ \t]+\)/g, ')');
result = result.replace(/\[[ \t]+/g, '[');
result = result.replace(/[ \t]+\]/g, ']');
result = result.replace(/\{[ \t]+/g, '{');
result = result.replace(/[ \t]+\}/g, '}');
for (let i = 0; i < preserved.length; i++) {
result = result.replace(`__PRESERVED_${i}__`, preserved[i]);
}
return result;
}
function processFile(filePath) {
try {
const code = fs.readFileSync(filePath, 'utf8');
const processed = removeSpaces(code);
if (code !== processed) {
fs.writeFileSync(filePath, processed, 'utf8');
console.log(`Processed: ${filePath}`);
return true;
}
return false;
} catch (err) {
console.error(`Error processing ${filePath}: ${err.message}`);
return false;
}
}
function walkDir(dir) {
let count = 0;
const files = fs.readdirSync(dir);
for (const file of files) {
const fullPath = path.join(dir, file);
const stat = fs.statSync(fullPath);
if (stat.isDirectory()) {
if (!excludeDirs.includes(file)) {
count += walkDir(fullPath);
}
} else if (file.endsWith('.js') && !file.endsWith('.min.js')) {
if (processFile(fullPath)) {
count++;
}
}
}
return count;
}
const targetDir = path.join(__dirname, '..', 'js');
console.log(`Processing JS files in: ${targetDir}`);
console.log(`Excluding directories: ${excludeDirs.join(', ')}`);
console.log('');
const count = walkDir(targetDir);
console.log('');
console.log(`Done! ${count} files modified.`);
