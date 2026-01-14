// UI動線で呼び出される関数が定義されているか検証するスクリプト
// 使用方法: node check-ui-functions.js

var fs=require('fs');
var path=require('path');

var htmlFile='index.html';
var jsDir='js';
var excludeDirs=['json_js','test','third','01_build','02_images_svg','03_images','99_doc','font'];
var jsKeywords=['if','else','for','while','do','switch','case','break','continue','return','try','catch','finally','throw','new','delete','typeof','instanceof','void','this','true','false','null','undefined','var','let','const','function','class','extends','super','import','export','default','yield','await','async','static','get','set','of','in','with','debugger'];

function extractFunctionCalls(html){
var regex=/on(?:click|change|input|keyup|keydown|focus|blur|mouseover|mouseout|mousedown|mouseup|submit|load)="([^"]+)"/gi;
var calls=new Set();
var match;
while((match=regex.exec(html))!==null){
var code=match[1];
var funcMatch=code.match(/^([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(/);
if(funcMatch){
calls.add(funcMatch[1]);
}
}
return calls;
}

function getAllJsFiles(dir,files=[]){
var items=fs.readdirSync(dir);
for(var item of items){
var fullPath=path.join(dir,item);
var relativePath=path.relative('.',fullPath);
if(excludeDirs.some(ex=>relativePath.includes(ex))){
continue;
}
var stat=fs.statSync(fullPath);
if(stat.isDirectory()){
getAllJsFiles(fullPath,files);
}else if(item.endsWith('.js')){
files.push(fullPath);
}
}
return files;
}

function extractDefinedFunctions(jsFiles){
var defined=new Map();
var patterns=[
/function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(/g,
/(?:var|let|const)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*function/g,
/(?:var|let|const)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*\([^)]*\)\s*=>/g,
/window\.([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*function/g
];
for(var file of jsFiles){
var content=fs.readFileSync(file,'utf8');
for(var pattern of patterns){
var match;
pattern.lastIndex=0;
while((match=pattern.exec(content))!==null){
if(!defined.has(match[1])){
defined.set(match[1],file);
}
}
}
}
return defined;
}

function extractFunctionsFromHtml(html){
var defined=new Map();
var scriptRegex=/<script[^>]*>([\s\S]*?)<\/script>/gi;
var patterns=[
/function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(/g,
/(?:var|let|const)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*function/g,
/(?:var|let|const)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*\([^)]*\)\s*=>/g
];
var scriptMatch;
while((scriptMatch=scriptRegex.exec(html))!==null){
var scriptContent=scriptMatch[1];
for(var pattern of patterns){
var match;
pattern.lastIndex=0;
while((match=pattern.exec(scriptContent))!==null){
if(!defined.has(match[1])){
defined.set(match[1],'index.html (inline)');
}
}
}
}
return defined;
}

var html=fs.readFileSync(htmlFile,'utf8');
var calledFunctions=extractFunctionCalls(html);
var jsFiles=getAllJsFiles(jsDir);
var definedFunctions=extractDefinedFunctions(jsFiles);
var htmlFunctions=extractFunctionsFromHtml(html);
for(var [name,file] of htmlFunctions){
if(!definedFunctions.has(name)){
definedFunctions.set(name,file);
}
}

console.log('=== UI動線 関数定義チェック ===\n');
console.log('HTMLから抽出した関数呼び出し:',calledFunctions.size,'個');
console.log('JSファイルから抽出した関数定義:',definedFunctions.size,'個\n');

var missing=[];
var found=[];
for(var func of calledFunctions){
if(jsKeywords.includes(func)){
continue;
}
if(definedFunctions.has(func)){
found.push({name:func,file:definedFunctions.get(func)});
}else{
missing.push(func);
}
}

if(missing.length>0){
console.log('【未定義の関数】');
for(var m of missing.sort()){
console.log('  ✗',m);
}
console.log('');
}else{
console.log('✓ すべての関数が定義されています\n');
}

console.log('【定義済み関数】',found.length,'個');
for(var f of found.sort((a,b)=>a.name.localeCompare(b.name))){
console.log('  ✓',f.name,'→',path.relative('.',f.file));
}
