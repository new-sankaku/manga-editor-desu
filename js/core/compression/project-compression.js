
async function generateProjectFileBufferList() {
saveState();
const fileBufferList=[];

const promises=[
(async ()=>{
const buffer=await ArrayBufferUtils.toArrayBuffer(JSON.stringify(basePrompt));
lz4Compressor.putDataListByArrayBuffer(fileBufferList,"text2img_basePrompt.json",buffer);
})(),

...stateStack.map(async (json,index)=>{
const buffer=await ArrayBufferUtils.toArrayBuffer(JSON.stringify(json));
const paddedIndex=String(index).padStart(6,'0');
lz4Compressor.putDataListByArrayBuffer(fileBufferList,`state_${paddedIndex}.json`,buffer);
}),

...Array.from(imageMap).map(async ([key,value])=>{
const buffer=await ArrayBufferUtils.toArrayBuffer(value);
lz4Compressor.putDataListByArrayBuffer(fileBufferList,`${key}.img`,buffer);
}),

(async ()=>{
const canvasInfo={width: canvas.width,height: canvas.height};
const buffer=await ArrayBufferUtils.toArrayBuffer(JSON.stringify(canvasInfo));
lz4Compressor.putDataListByArrayBuffer(fileBufferList,"canvas_info.json",buffer);
})(),

(async ()=>{
removeGrid();
const previewLink=getCropAndDownloadLinkByMultiplier(1,'jpeg');
const buffer=await ArrayBufferUtils.toArrayBuffer(previewLink.href);
lz4Compressor.putDataListByArrayBuffer(fileBufferList,"preview-image.jpeg",buffer);
if (isGridVisible) {
drawGrid();
isGridVisible=true;
}
})()
];

await Promise.all(promises);
return fileBufferList;
}



async function loadLz4BlobProjectFile(lz4Blob,guid=null){
stateStack=[];
imageMap.clear();

let files=await lz4Compressor.unLz4Files(lz4Blob);

let t2iBasePromptBuffer=getDataByName(files,"text2img_basePrompt.json");
let canvasInfoBuffer=getDataByName(files,"canvas_info.json");

let t2iBasePromptStr=ArrayBufferUtils.fromArrayBufferToString(t2iBasePromptBuffer);
let canvasInfoStr=ArrayBufferUtils.fromArrayBufferToString(canvasInfoBuffer);

if (t2iBasePromptStr) {
Object.assign(basePrompt,JSON.parse(t2iBasePromptStr));
}

var canvasInfo=canvasInfoStr ? JSON.parse(canvasInfoStr) : {width: 750,height: 850};

var sortedFiles=files.sort((a,b)=>{
const numA=a.name.match(/(\d+)/) ? parseInt(a.name.match(/(\d+)/)[0]) :-1;
const numB=b.name.match(/(\d+)/) ? parseInt(b.name.match(/(\d+)/)[0]) :-1;
if (numA===numB) {
return a.name.localeCompare(b.name);
}
return numA-numB;
});

await Promise.all(sortedFiles.map(async (file)=>{
try {
if (file.name.endsWith(".img")) {
let imgDataUrlStr=ArrayBufferUtils.fromArrayBufferToString(file.data);

let hash=file.name.split('.')[0];
imageMap.set(hash,imgDataUrlStr);
}
} catch (error) {
console.error("Failed to load file:",file.name,error);
}
}));

const jsonLoadPromises=sortedFiles.map(async (file)=>{
try {
if (file.name.endsWith(".json")&&
file.name!=="text2img_basePrompt.json"&&
file.name!=="canvas_info.json") {
let jsonStr=ArrayBufferUtils.fromArrayBufferToString(file.data);
return JSON.parse(jsonStr);
}
} catch (error) {
console.error("Failed to load file:",file.name,error);
}
});

const jsonResults=await Promise.all(jsonLoadPromises);
stateStack=jsonResults.filter(data=>data!==undefined);

currentStateIndex=stateStack.length-1;
resizeCanvasByNum(canvasInfo.width,canvasInfo.height);
lastRedo(guid);

if(guid){
setCanvasGUID(guid);
}
}

async function btmSaveProjectFile(guid=null) {
try {
guid=guid||getCanvasGUID();
const previewLink=getCropAndDownloadLinkByMultiplier(1,"jpeg");
const lz4Blob=await generateBlobProjectFile();
btmAddImage(previewLink,lz4Blob,guid);
return;
} catch (error) {
throw error;
}
}

async function generateBlobProjectFile(guid=null) {
try {
guid=guid||getCanvasGUID();
const fileBufferList=await generateProjectFileBufferList();
const lz4Blob=await lz4Compressor.buffersToLz4Blob(fileBufferList);
return lz4Blob;
} catch (error) {
throw error;
}
}




async function multiLoadLz4(bufferFileLz4List) {
for (const file of bufferFileLz4List) {
let projectFileList=await lz4Compressor.unLz4FilesByBuffer(file.data.buffer);
const previewBlobBuffer=projectFileList.find(file=>file.name==="preview-image.jpeg");

const isBase64=new TextDecoder().decode(previewBlobBuffer.data.slice(0,30)).startsWith('data:image/jpeg;base64,');

let previewBlob;
if (isBase64) {
const base64Data=new TextDecoder().decode(previewBlobBuffer.data);
const actualData=atob(base64Data.split(',')[1]);
const uint8Array=new Uint8Array(actualData.length);
for (let i=0;i<actualData.length;i++) {
uint8Array[i]=actualData.charCodeAt(i);
}
previewBlob=new Blob([uint8Array],{type: 'image/jpeg'});
} else {
previewBlob=new Blob([previewBlobBuffer.data],{type: 'image/jpeg'});
}

const previewImageUrl=URL.createObjectURL(previewBlob);

const reader=new FileReader();
reader.onload=function() {
};
reader.readAsText(previewBlob);

const binaryReader=new FileReader();
binaryReader.readAsArrayBuffer(previewBlob);

const jsonBufferFiles=projectFileList.filter(f=>
f.name.startsWith('state_')&&f.name.endsWith('.json')
);
let canvasGuid=null;

for (const jsonBuffer of jsonBufferFiles) {
let jsonStr=ArrayBufferUtils.fromArrayBufferToString(jsonBuffer.data);

try {
const state=JSON.parse(jsonStr);
canvasGuid=findCanvasGuid(state);

if (canvasGuid) {
const lz4Blob=new Blob([file.data]);
btmAddImage({href: previewImageUrl},lz4Blob,canvasGuid);
break;
}
} catch (error) {
console.error("Error parsing JSON:",error);
}
}

if (!canvasGuid) {
let guid=generateGUID();
const blob=new Blob([file.data]);
btmAddImage({href: previewImageUrl},blob,guid);
}
}
}


async function multiLoadZip(zip) {
const zipFiles=Object.keys(zip.files).filter(filename=>filename.endsWith('.zip'));

for (let i=0;i<zipFiles.length;i++) {
const zipContent=await zip.file(zipFiles[i]).async('blob');
const innerZip=await JSZip.loadAsync(zipContent);
const previewImage=innerZip.file('preview-image.jpeg');
if (!previewImage) {
continue;
}

const previewImageBlob=await previewImage.async('blob');
const previewImageUrl=URL.createObjectURL(previewImageBlob);

const stateFiles=Object.keys(innerZip.files).filter(filename=>filename.startsWith('state_')&&filename.endsWith('.json'));

var canvasGuid=null;

for (const stateFile of stateFiles) {
const stateContent=await innerZip.file(stateFile).async('text');
try {
const state=JSON.parse(stateContent);
canvasGuid=findCanvasGuid(state);

if (canvasGuid) {
btmAddImage({href: previewImageUrl},zipContent,canvasGuid);
break;
}
} catch (error) {
console.error("Error parsing JSON:",error);
}
}

if(canvasGuid){
//skip
}else{
let guid=generateGUID();
btmAddImage({href: previewImageUrl},zipContent,guid);
}
}
}




//This is not recommended as it has been changed from Zip management to Lz4 management.
async function processZip(zip) {
const zipFiles=Object.keys(zip.files).filter(filename=>filename.endsWith('.zip'));

for (let i=0;i<zipFiles.length;i++) {
const zipContent=await zip.file(zipFiles[i]).async('blob');
const innerZip=await JSZip.loadAsync(zipContent);
const previewImage=innerZip.file('preview-image.jpeg');
if (!previewImage) {
continue;
}

const previewImageBlob=await previewImage.async('blob');
const previewImageUrl=URL.createObjectURL(previewImageBlob);

const stateFiles=Object.keys(innerZip.files).filter(filename=>filename.startsWith('state_')&&filename.endsWith('.json'));

var canvasGuid=null;

for (const stateFile of stateFiles) {
const stateContent=await innerZip.file(stateFile).async('text');
try {
const state=JSON.parse(stateContent);
canvasGuid=findCanvasGuid(state);

if (canvasGuid) {
let lz4Blob=await lz4Compressor.zipFileListToLz4Blob(innerZip.files);
btmAddImage({href: previewImageUrl},lz4Blob,canvasGuid);
break;
}
} catch (error) {
console.error("Error parsing JSON:",error);
}
}

if(canvasGuid){
//skip
}else{
let guid=generateGUID();
btmAddImage({href: previewImageUrl},zipContent,guid);
}
}
}

//This is not recommended as it has been changed from Zip management to Lz4 management.
async function loadZip(zip,guid=null){
stateStack=[];
imageMap.clear();

var text2imgBasePromptFile=zip.file("text2img_basePrompt.json");
if (text2imgBasePromptFile) {
const content=await text2imgBasePromptFile.async("string");
Object.assign(basePrompt,JSON.parse(content));
}

var canvasInfoFile=zip.file("canvas_info.json");
var canvasInfo=canvasInfoFile
? JSON.parse(await canvasInfoFile.async("string"))
: {width: 750,height: 850};

var sortedFiles=Object.keys(zip.files).sort((a,b)=>{
const numA=a.match(/(\d+)/) ? parseInt(a.match(/(\d+)/)[0]) :-1;
const numB=b.match(/(\d+)/) ? parseInt(b.match(/(\d+)/)[0]) :-1;
if (numA===numB) {
return a.localeCompare(b);
}
return numA-numB;
});

await Promise.all(sortedFiles.map(async (fileName)=>{
try {
const content=await zip.file(fileName).async("string");
if (fileName.endsWith(".img")) {
let hash=fileName.split('.')[0];
imageMap.set(hash,content);
}
} catch (error) {
console.error("Failed to load file:",fileName,error);
}
}));

const jsonLoadPromises=sortedFiles.map(async (fileName)=>{
try {
if (fileName.endsWith(".json")&&
fileName!=="text2img_basePrompt.json"&&
fileName!=="canvas_info.json") {
const content=await zip.file(fileName).async("string");
return JSON.parse(content);
}
} catch (error) {
console.error("Failed to load file:",fileName,error);
}
});

const jsonResults=await Promise.all(jsonLoadPromises);
stateStack=jsonResults.filter(data=>data!==undefined);

currentStateIndex=stateStack.length-1;
resizeCanvasByNum(canvasInfo.width,canvasInfo.height);
lastRedo(guid);

if(guid){
setCanvasGUID(guid);
}
}
