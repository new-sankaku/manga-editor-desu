// プロジェクトで使用しているフォント情報の保存・復元
// フォント本体はIndexedDB(fm-fontStorage)にありプロジェクトには含まれないため、
// name/type/url を保存して読み込み側で復元または不足を明示する

var projectFontData=new Map();
var missingProjectFonts=[];

function collectUsedFontNames(){
const used=new Set();
canvas.getObjects().forEach(function(obj){
if(obj.fontFamily){
used.add(obj.fontFamily);
}
if(obj.styles){
Object.keys(obj.styles).forEach(function(line){
const lineStyles=obj.styles[line];
if(!lineStyles){
return;
}
Object.keys(lineStyles).forEach(function(charIndex){
const style=lineStyles[charIndex];
if(style&&style.fontFamily){
used.add(style.fontFamily);
}
});
});
}
});
return used;
}

function getUserFontEntry(fontName){
if(typeof fmFontData==='undefined'||!fmFontData["UserFont"]){
return null;
}
const fonts=fmFontData["UserFont"].fonts||[];
for(let i=0;i<fonts.length;i++){
if(fonts[i].name===fontName){
return fonts[i];
}
}
return null;
}

// 保存時: ローカルに登録済みの情報を優先し、無ければ読み込み時に受け取った情報を引き継ぐ。
// 引き継がないと、フォント未登録の環境で開いて保存し直したときに情報が失われる。
function buildProjectFontData(){
const used=collectUsedFontNames();
const list=[];
used.forEach(function(fontName){
const entry=getUserFontEntry(fontName);
if(entry){
list.push({name:entry.name,type:entry.type,url:entry.url||null});
return;
}
const carried=projectFontData.get(fontName);
if(carried){
list.push({name:carried.name,type:carried.type,url:carried.url||null});
}
});
return list;
}

function setProjectFontData(fontList){
projectFontData=new Map();
if(!fontList||!fontList.length){
return;
}
fontList.forEach(function(font){
if(font&&font.name){
projectFontData.set(font.name,font);
}
});
}

async function restoreProjectFonts(fontList){
setProjectFontData(fontList);
missingProjectFonts=[];
if(!fontList||!fontList.length){
return;
}
for(const font of fontList){
if(!font||!font.name){
continue;
}
if(fontManager.existsFont(font.name)){
continue;
}
if(font.type==='web'&&font.url){
try{
await fontManager.registerWebFont(font.url);
fontLogger.info("Restored web font from project: "+font.name);
continue;
}catch(error){
fontLogger.error("Failed to restore web font: "+font.name,error);
}
}
missingProjectFonts.push(font);
}
notifyMissingProjectFonts();
}

function notifyMissingProjectFonts(){
if(!missingProjectFonts.length){
return;
}
const names=missingProjectFonts.map(function(font){return font.name;}).join(", ");
createToastError(getText("fontMissingTitle"),getText("fontMissingMessage")+" "+names);
fontLogger.warn("Missing project fonts: "+names);
}

// フォントが後から登録されたとき、そのフォントを使うテキストを再計算して描画し直す
function applyRecoveredFont(fontName){
if(!missingProjectFonts.length){
return;
}
const index=missingProjectFonts.findIndex(function(font){return font.name===fontName;});
if(index<0){
return;
}
missingProjectFonts.splice(index,1);
withoutHistory(function(){
canvas.getObjects().forEach(function(obj){
if(!usesFontFamily(obj,fontName)){
return;
}
obj.dirty=true;
if(typeof obj.initDimensions==='function'){
obj.initDimensions();
}
obj.setCoords();
});
});
canvas.requestRenderAll();
updateLayerPanel();
createToast(getText("fontRestoredTitle"),fontName);
}

function usesFontFamily(obj,fontName){
if(obj.fontFamily===fontName){
return true;
}
if(!obj.styles){
return false;
}
return Object.keys(obj.styles).some(function(line){
const lineStyles=obj.styles[line];
if(!lineStyles){
return false;
}
return Object.keys(lineStyles).some(function(charIndex){
const style=lineStyles[charIndex];
return style&&style.fontFamily===fontName;
});
});
}
