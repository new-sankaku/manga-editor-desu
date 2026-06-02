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

// ページサイズはresizeCanvasByNumで設定する。raw setWidth/setHeightだと
// aspectRatioが更新されず、後続のadjustCanvasSizeが旧アスペクト(A4等)で
// 合わせてコマを非一様に歪ませるため。
if(pageJson.pageSize&&pageJson.pageSize.width&&pageJson.pageSize.height){
resizeCanvasByNum(pageJson.pageSize.width,pageJson.pageSize.height);
}

// ビルド中の画像ロードawait中にリサイズが割り込んでスケールが累積するのを防ぐ。
window._projectLoaderBuilding=true;
try{
const layers=Array.isArray(pageJson.layers)?pageJson.layers:[];
for(const layerSpec of layers){
await addLayerWithChildren(layerSpec,pagesBasePath);
}
// 全オブジェクトの基準状態をページサイズ(scale=1)で揃えてから保存する。
canvas.getObjects().forEach(obj=>saveInitialState(obj));
}finally{
window._projectLoaderBuilding=false;
}

canvas.renderAll();
await btmSaveProjectFile(newGuid,false);
}

async function addLayerWithChildren(spec,pagesBasePath){
const obj=await enlivenLayer(spec,pagesBasePath);
if(obj) canvas.add(obj);
if(spec.type!=='group'&&Array.isArray(spec.children)){
for(const childSpec of spec.children){
await addLayerWithChildren(childSpec,pagesBasePath);
}
}
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
const shift=strokeShift(spec);
return new fabric.Rect({
left:numOr(spec.left,0)-shift,
top:numOr(spec.top,0)-shift,
width:numOr(spec.width,100),
height:numOr(spec.height,100),
fill:spec.fill||'transparent',
stroke:spec.stroke,
strokeWidth:numOr(spec.strokeWidth,0)
});
}

function createPolygonLayer(spec){
const points=Array.isArray(spec.points)?spec.points:[];
const shift=strokeShift(spec);
return new fabric.Polygon(points,{
left:numOr(spec.left,0)-shift,
top:numOr(spec.top,0)-shift,
fill:spec.fill||'transparent',
stroke:spec.stroke,
strokeWidth:numOr(spec.strokeWidth,0)
});
}

function createPathLayer(spec){
const shift=strokeShift(spec);
return new fabric.Path(spec.d||'M 0 0',{
left:numOr(spec.left,0)-shift,
top:numOr(spec.top,0)-shift,
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
const shift=groupStrokeShift(spec);
const group=new fabric.Group(children,{
left:numOr(spec.left,0)-shift,
top:numOr(spec.top,0)-shift
});
// speechBubbleSVG等はreSetSpeechBubbleTextがobj.guidsを参照するため、
// specにguidsが無くても子のguidから補完する(未設定だと読込時に例外)。
if(!Array.isArray(spec.guids)){
const childGuids=childSpecs.map(child=>child.guid).filter(Boolean);
if(childGuids.length) group.guids=childGuids;
}
return group;
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

// fabricのleft/topはstroke外側を指すため、SVG/外部座標(幾何形状の角)に合わせて
// strokeWidth/2だけ左上に補正する。これをしないと枠線分(strokeWidth/2)右下にズレる。
function strokeShift(spec){
return numOr(spec.strokeWidth,0)/2;
}

// グループ(吹き出し等)はfabricが子のbboxで再配置するため、bbox端を成す子のstroke分だけ
// グループ自体を補正する。子要素中の最大strokeWidthを端の枠線とみなす。
function groupStrokeShift(spec){
const children=Array.isArray(spec.children)?spec.children:[];
let max=0;
for(const child of children){
const sw=numOr(child.strokeWidth,0);
if(sw>max) max=sw;
}
return max/2;
}

function plText(key){
if(typeof i18next!=='undefined'&&i18next.isInitialized){
return i18next.t(key);
}
return key;
}
