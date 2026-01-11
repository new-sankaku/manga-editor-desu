class FileCompressor {
constructor() {
this.lz4Module=null;
}

async initialize() {
try {
const wasmBuffer=this.base64ToArrayBuffer(wasmBase64);
const initResult=lz4init({wasmBinary: wasmBuffer});
this.lz4Module=await initResult;
} catch (e) {
console.log("initialize error:",JSON.stringify(e));
}
}

async isLz4(input) {
try {
let arrayBuffer;

if (input instanceof Blob) {
arrayBuffer=await input.arrayBuffer();
} else if (input instanceof ArrayBuffer) {
arrayBuffer=input;
} else {
return false;
}

const data=new Uint8Array(arrayBuffer);
if (data.length<4) {
return false;
}

const headerSize=new Uint32Array(data.slice(0,4).buffer)[0];
if (headerSize<=0||headerSize>data.length-4) {
return false;
}

const headerData=data.slice(4,4+headerSize);
try {
const headerText=new TextDecoder().decode(headerData);
const header=JSON.parse(headerText);

if (!Array.isArray(header)) {
return false;
}

for (const file of header) {
if (!file.hasOwnProperty('name')||!file.hasOwnProperty('size')) {
return false;
}
}
return true;
} catch (e) {
return false;
}
} catch (e) {
console.log("isLz4 error:",JSON.stringify(e));
return false;
}
}



base64ToArrayBuffer(base64) {
const binaryString=atob(base64);
const bytes=new Uint8Array(binaryString.length);
for (let i=0;i<binaryString.length;i++) {
bytes[i]=binaryString.charCodeAt(i);
}
return bytes.buffer;
}

async readFileAsArrayBuffer(file) {
return new Promise((resolve,reject)=>{
const reader=new FileReader();
reader.onload=(e)=>resolve(e.target.result);
reader.onerror=reject;
reader.readAsArrayBuffer(file);
});
}

putDataListByArrayBuffer(dataList,name,arrayBuffer) {
if (!arrayBuffer||!(arrayBuffer instanceof ArrayBuffer)) {
return;
}

const uint8Array=new Uint8Array(arrayBuffer);

const item={
name: name,
size: arrayBuffer.byteLength,
data: uint8Array,
};

dataList.push(item);
}

putDataList(dataList,name,size,data) {
dataList.push({
name: name,
size: size,
data: new Uint8Array(data),
});
}

async mergeLz4Blobs(lz4BlobList) {
const fileBufferList=[];
for (const blob of lz4BlobList) {
const buffer=await blob.arrayBuffer();
fileBufferList.push({
name: 'lz4_part_'+fileBufferList.length+".lz4",
size: buffer.byteLength,
data: new Uint8Array(buffer)
});
}

return await this.buffersToLz4Blob(fileBufferList);
}


async buffersToLz4Blob(fileBufferList) {
const header=new TextEncoder().encode(
JSON.stringify(
fileBufferList.map((f)=>({name: f.name,size: f.size}))
)
);
const headerSize=new Uint32Array([header.length]);
const totalSize=fileBufferList.reduce((sum,f)=>sum+f.data.length,0);
const combinedData=new Uint8Array(totalSize);

let offset=0;
for (const file of fileBufferList) {
combinedData.set(file.data,offset);
offset+=file.data.length;
}

const compressed=this.lz4Module.lz4js.compress(combinedData);
const finalData=new Uint8Array(4+header.length+compressed.length);
finalData.set(new Uint8Array(headerSize.buffer),0);
finalData.set(header,4);
finalData.set(compressed,4+header.length);

const lz4Blob=new Blob([finalData]);
return lz4Blob;
}


//This is a compatibility fix for old Zip projects.
async zipFileListToLz4Blob(files) {
const fileBufferList=[];

for (const [filename,fileEntry] of Object.entries(files)) {
if (fileEntry._data&&fileEntry._data.compressedContent) {
const name=fileEntry.name;
const data=fileEntry._data.compressedContent;
const size=data.length;

fileBufferList.push({
name,
data,
size
});
}
}
return await this.buffersToLz4Blob(fileBufferList);
}



async unLz4Files(blob) {
// console.log("unLz4Files, ", blob);
const arrayBuffer=await blob.arrayBuffer();
return await this.unLz4FilesByBuffer(arrayBuffer);
}

async unLz4FilesByBuffer(arrayBuffer) {
const compressedData=new Uint8Array(arrayBuffer);
const headerSize=new Uint32Array(compressedData.slice(0,4).buffer)[0];
const headerData=compressedData.slice(4,4+headerSize);
const header=JSON.parse(new TextDecoder().decode(headerData));

const compressed=compressedData.slice(4+headerSize);
const decompressed=this.lz4Module.lz4js.decompress(compressed);

let offset=0;
const files=[];
for (const fileInfo of header) {
const fileData=decompressed.slice(offset,offset+fileInfo.size);
files.push({
name: fileInfo.name,
data: fileData,
});
offset+=fileInfo.size;
}
return files;
}

async unLz4(decompressFile) {
if (!decompressFile||!this.lz4Module) return;
try {
const buffer=await this.readFileAsArrayBuffer(decompressFile);
const decompressed=await this.unLz4Files(new Uint8Array(buffer));

for (const file of decompressed) {
const blob=new Blob([file.data]);
const url=URL.createObjectURL(blob);
const a=document.createElement("a");
a.href=url;
a.download=file.name;
a.click();
URL.revokeObjectURL(url);
}
} catch (e) {
console.log("error:",JSON.stringify(e));
}
}
}

const lz4Compressor=new FileCompressor();
lz4Compressor.initialize();

// compressor.files = selectedFiles;
// await compressor.lz4Files();

// compressor.decompressFile = selectedFile;
// await compressor.unLz4();
