// 選択プロジェクトフォルダ配下の pages/pXXX_page.json をページとして取り込むローダ。
// 仕様: llm_doc/format.md
// 既存ページはすべて破棄し新規プロジェクトとして再構築する。

const PROJECT_LOADER_FILES_API='/api/files';
const PROJECT_LOADER_FILE_API='/api/file';
const PROJECT_LOADER_PAGES_SUBDIR='pages';
const PROJECT_LOADER_PATTERN='^p\\d+_page\\.json$';

window.ProjectLoader={
loadFromFolder:loadProjectPagesFromFolder
};

async function loadProjectPagesFromFolder(folderPath,folderDisplayPath){
const pagesPath=folderPath?`${folderPath}/${PROJECT_LOADER_PAGES_SUBDIR}`:PROJECT_LOADER_PAGES_SUBDIR;
const url=`${PROJECT_LOADER_FILES_API}?path=${encodeURIComponent(pagesPath)}&pattern=${encodeURIComponent(PROJECT_LOADER_PATTERN)}`;

let listJson;
try{
const res=await fetch(url);
if(res.status===404){
createToastError(plText('projectLoaderError'),[plText('projectLoaderNoPagesDir')]);
return;
}
if(!res.ok) throw new Error('list http '+res.status);
listJson=await res.json();
}catch(err){
folderPickerLogger.error('list files failed',err);
createToastError(plText('projectLoaderError'),[err.message||'']);
return;
}

const sorted=(listJson.entries||[])
.map(entry=>{
const m=entry.name.match(/^p(\d+)_page\.json$/);
return m?{...entry,num:parseInt(m[1],10)}:null;
})
.filter(Boolean)
.sort((a,b)=>a.num-b.num);

if(sorted.length===0){
createToastError(plText('projectLoaderError'),[plText('projectLoaderNoPages')]);
return;
}

resetProjectBtm();

let loaded=0;
for(const file of sorted){
try{
const res=await fetch(`${PROJECT_LOADER_FILE_API}?path=${encodeURIComponent(file.path)}`);
if(!res.ok) throw new Error('file http '+res.status);
const pageJson=await res.json();
await addJsonAsPage(pageJson,pagesPath);
loaded++;
}catch(err){
folderPickerLogger.error('page load failed',err,file);
}
}

if(loaded===0){
createToastError(plText('projectLoaderError'),[]);
return;
}
createToast(plText('projectLoaderLoaded'),[`${loaded} / ${sorted.length}`,folderDisplayPath||folderPath]);
}

function resetProjectBtm(){
btmProjectsMap.clear();
const container=$("btm-image-container");
if(container) container.innerHTML='';
}

async function addJsonAsPage(pageJson,pagesBasePath){
const newGuid=pageJson.canvasGuid||generateGUID();
setCanvasGUID(newGuid);
canvas.clear();

if(pageJson.pageSize&&pageJson.pageSize.width&&pageJson.pageSize.height){
canvas.setWidth(pageJson.pageSize.width);
canvas.setHeight(pageJson.pageSize.height);
}

const layers=Array.isArray(pageJson.layers)?pageJson.layers:[];
for(const layerSpec of layers){
const obj=await enlivenLayer(layerSpec,pagesBasePath);
if(obj) canvas.add(obj);
}

canvas.renderAll();
await btmSaveProjectFile(newGuid,false);
}

async function enlivenLayer(spec,pagesBasePath){
if(!spec||!spec.type){
folderPickerLogger.warn('layer spec missing type',spec);
return null;
}

let obj=null;
switch(spec.type){
case 'image':
obj=await createImageLayer(spec,pagesBasePath);
break;
case 'rect':
obj=createRectLayer(spec);
break;
case 'polygon':
obj=createPolygonLayer(spec);
break;
case 'path':
obj=createPathLayer(spec);
break;
case 'textbox':
case 'text':
case 'i-text':
obj=createTextboxLayer(spec);
break;
case 'vertical-textbox':
obj=createVerticalTextboxLayer(spec);
break;
case 'group':
obj=await createGroupLayer(spec,pagesBasePath);
break;
default:
folderPickerLogger.warn('unsupported layer type',spec.type,spec);
return null;
}

if(obj) applyMetaProps(obj,spec);
return obj;
}

function applyMetaProps(obj,spec){
if(spec.angle!==undefined) obj.angle=spec.angle;
if(spec.opacity!==undefined) obj.opacity=spec.opacity;
if(spec.visible!==undefined) obj.visible=spec.visible;
if(spec.selectable!==undefined) obj.selectable=spec.selectable;
if(spec.guid) obj.guid=spec.guid;
if(Array.isArray(spec.guids)) obj.guids=spec.guids.slice();
if(spec.relatedPoly) obj.relatedPoly=spec.relatedPoly;
if(spec.isPanel) obj.isPanel=true;
if(spec.customType) obj.customType=spec.customType;
if(spec.name) obj.name=spec.name;
}

function createImageLayer(spec,pagesBasePath){
return new Promise((resolve,reject)=>{
const src=resolveSrc(spec.src,pagesBasePath);
if(!src){
reject(new Error('image src missing'));
return;
}
fabric.Image.fromURL(src,(img)=>{
if(!img){
reject(new Error('image load failed: '+spec.src));
return;
}
img.set({
left:numOr(spec.left,0),
top:numOr(spec.top,0)
});
if(spec.scaleX!==undefined) img.scaleX=spec.scaleX;
if(spec.scaleY!==undefined) img.scaleY=spec.scaleY;
if(spec.width&&img.width) img.scaleX=spec.width/img.width;
if(spec.height&&img.height) img.scaleY=spec.height/img.height;
resolve(img);
},{crossOrigin:'anonymous'});
});
}

function createRectLayer(spec){
return new fabric.Rect({
left:numOr(spec.left,0),
top:numOr(spec.top,0),
width:numOr(spec.width,100),
height:numOr(spec.height,100),
fill:spec.fill||'transparent',
stroke:spec.stroke,
strokeWidth:numOr(spec.strokeWidth,0)
});
}

function createPolygonLayer(spec){
const points=Array.isArray(spec.points)?spec.points:[];
return new fabric.Polygon(points,{
left:numOr(spec.left,0),
top:numOr(spec.top,0),
fill:spec.fill||'transparent',
stroke:spec.stroke,
strokeWidth:numOr(spec.strokeWidth,0)
});
}

function createPathLayer(spec){
return new fabric.Path(spec.d||'M 0 0',{
left:numOr(spec.left,0),
top:numOr(spec.top,0),
fill:spec.fill||'transparent',
stroke:spec.stroke,
strokeWidth:numOr(spec.strokeWidth,0)
});
}

function createTextboxLayer(spec){
const opts={
left:numOr(spec.left,0),
top:numOr(spec.top,0),
fontSize:numOr(spec.fontSize,16)
};
if(spec.width!==undefined) opts.width=spec.width;
if(spec.fontFamily) opts.fontFamily=spec.fontFamily;
if(spec.fill) opts.fill=spec.fill;
if(spec.textAlign) opts.textAlign=spec.textAlign;
if(spec.lineHeight!==undefined) opts.lineHeight=spec.lineHeight;
return new fabric.Textbox(spec.text||'',opts);
}

function createVerticalTextboxLayer(spec){
if(typeof fabric.VerticalTextbox==='function'){
const opts={
left:numOr(spec.left,0),
top:numOr(spec.top,0),
fontSize:numOr(spec.fontSize,16)
};
if(spec.width!==undefined) opts.width=spec.width;
if(spec.fontFamily) opts.fontFamily=spec.fontFamily;
if(spec.fill) opts.fill=spec.fill;
return new fabric.VerticalTextbox(spec.text||'',opts);
}
folderPickerLogger.warn('fabric.VerticalTextbox not available; vertical-textbox is unsupported',spec);
return null;
}

async function createGroupLayer(spec,pagesBasePath){
const children=[];
const childSpecs=Array.isArray(spec.children)?spec.children:[];
for(const childSpec of childSpecs){
const childObj=await enlivenLayer(childSpec,pagesBasePath);
if(childObj) children.push(childObj);
}
return new fabric.Group(children,{
left:numOr(spec.left,0),
top:numOr(spec.top,0)
});
}

function resolveSrc(src,pagesBasePath){
if(!src) return null;
if(src.startsWith('data:')||src.startsWith('http://')||src.startsWith('https://')){
return src;
}
const clean=src.replace(/^\.\//,'');
const fullPath=pagesBasePath?`${pagesBasePath}/${clean}`:clean;
return `${PROJECT_LOADER_FILE_API}?path=${encodeURIComponent(fullPath)}`;
}

function numOr(v,fallback){
return (v===undefined||v===null||isNaN(v))?fallback:v;
}

function plText(key){
if(typeof i18next!=='undefined'&&i18next.isInitialized){
return i18next.t(key);
}
return key;
}
