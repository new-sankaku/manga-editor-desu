var DEBUG_FLAGS={
settingsHighlight:false
};

const TestRunner={
results:[],
passed:0,
failed:0,

reset:function(){
this.results=[];
this.passed=0;
this.failed=0;
},

assert:function(condition,testName,details=''){
const result={name:testName,passed:condition,details:details};
this.results.push(result);
if(condition){
this.passed++;
}else{
this.failed++;
}
return condition;
},

assertEquals:function(expected,actual,testName){
const passed=expected===actual;
const details=passed?'':`Expected: ${JSON.stringify(expected)}, Actual: ${JSON.stringify(actual)}`;
return this.assert(passed,testName,details);
},

assertNotNull:function(value,testName){
const passed=value!==null&&value!==undefined;
const details=passed?'':`Value is ${value}`;
return this.assert(passed,testName,details);
},

assertType:function(value,expectedType,testName){
const actualType=typeof value;
const passed=actualType===expectedType;
const details=passed?'':`Expected type: ${expectedType}, Actual type: ${actualType}`;
return this.assert(passed,testName,details);
},

assertInstanceOf:function(value,expectedClass,testName){
const passed=value instanceof expectedClass;
const details=passed?'':`Not instance of ${expectedClass.name}`;
return this.assert(passed,testName,details);
},

assertThrows:function(fn,testName){
let threw=false;
try{
fn();
}catch(e){
threw=true;
}
return this.assert(threw,testName,threw?'':'Expected function to throw');
},

assertAsync:async function(asyncFn,testName){
try{
const result=await asyncFn();
return this.assert(result,testName,'');
}catch(e){
return this.assert(false,testName,`Async error: ${e.message}`);
}
},

printResults:function(suiteName){
console.group(`%c[Test Suite] ${suiteName}`,`color:${this.failed===0?'green':'orange'};font-weight:bold`);
this.results.forEach(r=>{
if(r.passed){
console.log(`%c  ✓ ${r.name}`,'color:green');
}else{
console.log(`%c  ✗ ${r.name}`,'color:red');
if(r.details)console.log(`    ${r.details}`);
}
});
console.log(`%cTotal: ${this.passed} passed, ${this.failed} failed`,'font-weight:bold');
console.groupEnd();
return this.failed===0;
}
};

function verifyLoggers(){
const loggerList=[
{name:'logger',instance:typeof logger!=='undefined'?logger:null},
{name:'workflowLogger',instance:typeof workflowLogger!=='undefined'?workflowLogger:null},
{name:'eventLogger',instance:typeof eventLogger!=='undefined'?eventLogger:null},
{name:'comfyuiLogger',instance:typeof comfyuiLogger!=='undefined'?comfyuiLogger:null},
{name:'sdwebuiLogger',instance:typeof sdwebuiLogger!=='undefined'?sdwebuiLogger:null},
{name:'dbLogger',instance:typeof dbLogger!=='undefined'?dbLogger:null},
{name:'canvasLogger',instance:typeof canvasLogger!=='undefined'?canvasLogger:null},
{name:'projectLogger',instance:typeof projectLogger!=='undefined'?projectLogger:null},
{name:'layerLogger',instance:typeof layerLogger!=='undefined'?layerLogger:null},
{name:'fontLogger',instance:typeof fontLogger!=='undefined'?fontLogger:null},
{name:'uiLogger',instance:typeof uiLogger!=='undefined'?uiLogger:null},
{name:'effectLogger',instance:typeof effectLogger!=='undefined'?effectLogger:null},
{name:'textLogger',instance:typeof textLogger!=='undefined'?textLogger:null},
{name:'imageLogger',instance:typeof imageLogger!=='undefined'?imageLogger:null},
{name:'panelLogger',instance:typeof panelLogger!=='undefined'?panelLogger:null},
{name:'compressionLogger',instance:typeof compressionLogger!=='undefined'?compressionLogger:null},
{name:'serviceLogger',instance:typeof serviceLogger!=='undefined'?serviceLogger:null}
];

TestRunner.reset();
loggerList.forEach(item=>{
TestRunner.assertNotNull(item.instance,`${item.name} is defined`);
if(item.instance){
TestRunner.assertType(item.instance.info,'function',`${item.name}.info is function`);
TestRunner.assertType(item.instance.error,'function',`${item.name}.error is function`);
TestRunner.assertType(item.instance.setLevel,'function',`${item.name}.setLevel is function`);
}
});
return TestRunner.printResults('Logger Verification');
}

async function testArrayBufferUtils(){
if(typeof ArrayBufferUtils==='undefined'){
console.warn('[Test Skip] ArrayBufferUtils not loaded');
return false;
}

TestRunner.reset();

TestRunner.assertNotNull(ArrayBufferUtils,'ArrayBufferUtils class exists');

try{
const strBuffer=await ArrayBufferUtils.toArrayBuffer('Hello');
TestRunner.assertInstanceOf(strBuffer,ArrayBuffer,'String to ArrayBuffer');

const arrBuffer=await ArrayBufferUtils.toArrayBuffer([1,2,3,4,5]);
TestRunner.assertInstanceOf(arrBuffer,ArrayBuffer,'Array to ArrayBuffer');

const numBuffer=await ArrayBufferUtils.toArrayBuffer(10);
TestRunner.assertEquals(10,numBuffer.byteLength,'Number creates buffer of that size');

const uint8=new Uint8Array([72,101,108,108,111]);
const viewBuffer=await ArrayBufferUtils.toArrayBuffer(uint8);
TestRunner.assertInstanceOf(viewBuffer,ArrayBuffer,'TypedArray to ArrayBuffer');

const blob=new Blob(['Test']);
const blobBuffer=await ArrayBufferUtils.toArrayBuffer(blob);
TestRunner.assertInstanceOf(blobBuffer,ArrayBuffer,'Blob to ArrayBuffer');

const testBuffer=new TextEncoder().encode('Test').buffer;
const str=ArrayBufferUtils.fromArrayBufferToString(testBuffer);
TestRunner.assertEquals('Test',str,'ArrayBuffer to String');

const arr=ArrayBufferUtils.fromArrayBufferToArray(new Uint8Array([1,2,3]).buffer);
TestRunner.assertEquals(3,arr.length,'ArrayBuffer to Array length');

const resultBlob=ArrayBufferUtils.fromArrayBufferToBlob(testBuffer,'text/plain');
TestRunner.assertInstanceOf(resultBlob,Blob,'ArrayBuffer to Blob');

const int32Buffer=new ArrayBuffer(4);
new DataView(int32Buffer).setInt32(0,12345);
const num=ArrayBufferUtils.fromArrayBufferToNumber(int32Buffer);
TestRunner.assertEquals(12345,num,'ArrayBuffer to Number (Int32)');

let threwOnNull=false;
try{await ArrayBufferUtils.toArrayBuffer(null);}catch(e){threwOnNull=true;}
TestRunner.assert(threwOnNull,'Throws on null input');

let threwOnUndefined=false;
try{await ArrayBufferUtils.toArrayBuffer(undefined);}catch(e){threwOnUndefined=true;}
TestRunner.assert(threwOnUndefined,'Throws on undefined input');

}catch(e){
TestRunner.assert(false,`ArrayBufferUtils error: ${e.message}`);
}

return TestRunner.printResults('ArrayBufferUtils');
}

function testJsUtil(){
if(typeof generateRandomInt==='undefined'){
console.warn('[Test Skip] js-util not loaded');
return false;
}

TestRunner.reset();

TestRunner.assertEquals(0,generateRandomInt(0),'generateRandomInt(0) returns 0');

for(let i=0;i<20;i++){
const result=generateRandomInt(10);
TestRunner.assert(result>=1&&result<=10,`generateRandomInt(10) in range [1,10]: ${result}`);
}

TestRunner.assertEquals(0,generateRandomInt('abc'),'generateRandomInt(NaN) returns 0');

for(let i=0;i<20;i++){
const result=getRandomNumber(5,15);
TestRunner.assert(result>=5&&result<=15,`getRandomNumber(5,15) in range [5,15]: ${result}`);
}

TestRunner.assertType(getRandomNumber(1,10),'number','getRandomNumber returns number');

return TestRunner.printResults('JS Utilities');
}

async function testTaskQueue(){
if(typeof TaskQueue==='undefined'){
console.warn('[Test Skip] TaskQueue not loaded');
return false;
}

TestRunner.reset();

const queue=new TaskQueue(2);
TestRunner.assertNotNull(queue,'TaskQueue instance created');
TestRunner.assertEquals(0,queue.getActiveCount(),'Initial active count is 0');
TestRunner.assertEquals(0,queue.getWaitingCount(),'Initial waiting count is 0');

let task1Completed=false;
let task2Completed=false;
let task3Completed=false;
const executionOrder=[];

const promise1=queue.add(async()=>{
await new Promise(r=>setTimeout(r,50));
executionOrder.push(1);
task1Completed=true;
});

const promise2=queue.add(async()=>{
await new Promise(r=>setTimeout(r,30));
executionOrder.push(2);
task2Completed=true;
});

const promise3=queue.add(async()=>{
executionOrder.push(3);
task3Completed=true;
});

TestRunner.assert(queue.getActiveCount()<=2,'Concurrency limit respected');

await Promise.all([promise1,promise2,promise3]);

TestRunner.assert(task1Completed,'Task 1 completed');
TestRunner.assert(task2Completed,'Task 2 completed');
TestRunner.assert(task3Completed,'Task 3 completed');
TestRunner.assertEquals(0,queue.getActiveCount(),'Active count 0 after completion');

const status=queue.getStatus();
TestRunner.assertNotNull(status,'getStatus returns object');
TestRunner.assertEquals(0,status.active,'Status active is 0');
TestRunner.assertEquals(0,status.waiting,'Status waiting is 0');

return TestRunner.printResults('TaskQueue');
}

function testFabricUtil(){
if(typeof isPanel==='undefined'){
console.warn('[Test Skip] fabric-util not loaded');
return false;
}

TestRunner.reset();

TestRunner.assert(!isPanel(null),'isPanel(null) returns false');
TestRunner.assert(!isPanel({}),'isPanel({}) returns false');
TestRunner.assert(isPanel({isPanel:true}),'isPanel with isPanel:true');

TestRunner.assert(!isPanelType(null),'isPanelType(null) returns false');
TestRunner.assert(isPanelType({type:'rect'}),'isPanelType rect');
TestRunner.assert(isPanelType({type:'circle'}),'isPanelType circle');
TestRunner.assert(isPanelType({type:'polygon'}),'isPanelType polygon');
TestRunner.assert(!isPanelType({type:'image'}),'isPanelType image is false');

TestRunner.assert(!isImage(null),'isImage(null) returns false');
TestRunner.assert(isImage({type:'image'}),'isImage with type:image');
TestRunner.assert(!isImage({type:'rect'}),'isImage rect is false');

TestRunner.assert(!isText(null),'isText(null) returns false');
TestRunner.assert(isText({type:'text'}),'isText with type:text');
TestRunner.assert(isText({type:'i-text'}),'isText with type:i-text');
TestRunner.assert(isText({type:'textbox'}),'isText with type:textbox');
TestRunner.assert(isText({type:'vertical-textbox'}),'isText with type:vertical-textbox');

TestRunner.assert(!isPath(null),'isPath(null) returns false');
TestRunner.assert(isPath({type:'path'}),'isPath with type:path');

TestRunner.assert(!isLine(null),'isLine(null) returns false');
TestRunner.assert(isLine({type:'line'}),'isLine with type:line');

TestRunner.assert(!isGroup(null),'isGroup(null) returns false');
TestRunner.assert(isGroup({type:'group'}),'isGroup with type:group');

TestRunner.assert(!isShapes(null),'isShapes(null) returns false');
TestRunner.assert(isShapes({type:'path'}),'isShapes path');
TestRunner.assert(isShapes({type:'rect'}),'isShapes rect');
TestRunner.assert(isShapes({type:'circle'}),'isShapes circle');

TestRunner.assert(!haveClipPath({}),'haveClipPath empty object');
TestRunner.assert(haveClipPath({clipPath:{}}),'haveClipPath with clipPath');

return TestRunner.printResults('Fabric Utilities');
}

function testDeepCopy(){
if(typeof deepCopy==='undefined'){
console.warn('[Test Skip] deepCopy not loaded');
return false;
}

TestRunner.reset();

const simple={a:1,b:'test',c:true};
const simpleCopy=deepCopy(simple);
TestRunner.assertEquals(simple.a,simpleCopy.a,'Simple copy: number');
TestRunner.assertEquals(simple.b,simpleCopy.b,'Simple copy: string');
TestRunner.assertEquals(simple.c,simpleCopy.c,'Simple copy: boolean');
simple.a=999;
TestRunner.assert(simpleCopy.a!==999,'Simple copy is independent');

const nested={outer:{inner:{value:42}}};
const nestedCopy=deepCopy(nested);
TestRunner.assertEquals(42,nestedCopy.outer.inner.value,'Nested copy value');
nested.outer.inner.value=100;
TestRunner.assertEquals(42,nestedCopy.outer.inner.value,'Nested copy is independent');

const withClipPath={name:'test',clipPath:{left:10,top:20}};
const clipCopy=deepCopy(withClipPath);
TestRunner.assertNotNull(clipCopy.clipPath,'ClipPath copied');
TestRunner.assertEquals(10,clipCopy.clipPath.left,'ClipPath left copied');
TestRunner.assertEquals(20,clipCopy.clipPath.top,'ClipPath top copied');

const nullResult=deepCopy(null);
TestRunner.assertNotNull(nullResult,'deepCopy(null) returns object');

return TestRunner.printResults('Deep Copy');
}

function testColorConversion(){
if(typeof rgbaToHex==='undefined'){
console.warn('[Test Skip] color functions not loaded');
return false;
}

TestRunner.reset();

const hex1=rgbaToHex('rgba(255, 0, 0, 1)');
TestRunner.assert(hex1.toLowerCase().includes('ff0000')||hex1.toLowerCase()==='#ff0000','Red RGBA to hex');

const hex2=rgbaToHex('rgba(0, 255, 0, 1)');
TestRunner.assert(hex2.toLowerCase().includes('00ff00')||hex2.toLowerCase()==='#00ff00','Green RGBA to hex');

const hex3=rgbaToHex('rgb(0, 0, 255)');
TestRunner.assert(hex3.toLowerCase().includes('0000ff')||hex3.toLowerCase()==='#0000ff','Blue RGB to hex');

const hex4=rgbaToHex('#ff00ff');
TestRunner.assertEquals('#ff00ff',hex4.toLowerCase(),'Hex passthrough');

return TestRunner.printResults('Color Conversion');
}

async function runAllTests(){
console.log('%c========================================','color:blue;font-weight:bold');
console.log('%c       MANGA EDITOR TEST SUITE         ','color:blue;font-weight:bold');
console.log('%c========================================','color:blue;font-weight:bold');

const results={
loggers:verifyLoggers(),
jsUtil:testJsUtil(),
fabricUtil:testFabricUtil(),
deepCopy:testDeepCopy(),
colorConversion:testColorConversion()
};

results.arrayBuffer=await testArrayBufferUtils();
results.taskQueue=await testTaskQueue();

console.log('%c========================================','color:blue;font-weight:bold');
console.log('%c           TEST SUMMARY                ','color:blue;font-weight:bold');
console.log('%c========================================','color:blue;font-weight:bold');

let allPassed=true;
Object.entries(results).forEach(([name,passed])=>{
const status=passed?'✓ PASS':'✗ FAIL';
const color=passed?'green':'red';
console.log(`%c  ${status}: ${name}`,`color:${color};font-weight:bold`);
if(!passed)allPassed=false;
});

if(allPassed){
console.log('%c\n  ALL TESTS PASSED!','color:green;font-weight:bold;font-size:14px');
}else{
console.log('%c\n  SOME TESTS FAILED','color:red;font-weight:bold;font-size:14px');
}

return allPassed;
}

document.addEventListener('DOMContentLoaded',function(){
verifyLoggers();
});

window.runAllTests=runAllTests;
window.TestRunner=TestRunner;
