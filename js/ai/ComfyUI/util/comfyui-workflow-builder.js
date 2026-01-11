class ComfyUIWorkflowBuilder {
constructor(workflow) {
this.originalWorkflow=workflow;
this.hasInitialized=false;
this.workflowCopy=null;
}

initialize() {
if (!this.hasInitialized) {
this.workflowCopy=JSON.parse(JSON.stringify(this.originalWorkflow));
this.hasInitialized=true;
}
}

updateNodesByType(targetClassType,inputs,metaTitle=null) {
this.initialize();

const validInputs={};
Object.entries(inputs).forEach(([key,value])=>{
if (value!==null&&value!==undefined&&value!=="") {
validInputs[key]=value;
}
});

if (Object.keys(validInputs).length>0) {
Object.entries(this.workflowCopy).forEach(([id,node])=>{
const classTypeMatch=node.class_type===targetClassType;
const metaMatch=!metaTitle||(
node._meta&&node._meta.title===metaTitle
);

if (classTypeMatch&&metaMatch) {
node.inputs={
...node.inputs,
...validInputs
};
}
});
}

return this;
}

updateNodesByInputName(inputs) {
this.initialize();

const validInputs={};
Object.entries(inputs).forEach(([key,value])=>{
if (value!==null&&value!==undefined&&value!=="") {
validInputs[key]=value;
}
});
workflowlLogger.trace("validInputs, " ,validInputs);

if (Object.keys(validInputs).length>0) {
Object.entries(this.workflowCopy).forEach(([id,node])=>{
if (node.inputs) {
Object.keys(node.inputs).forEach(inputKey=>{
if (validInputs.hasOwnProperty(inputKey)) {
const originalValue=typeof node.inputs[inputKey];
const newValue=typeof validInputs[inputKey];

if (originalValue===newValue){
workflowlLogger.trace("validInputs, replase1 " ,originalValue,newValue);
node.inputs[inputKey]=validInputs[inputKey];

}else if ((isNumericType(node.inputs[inputKey])&&isNumericType(validInputs[inputKey]))){
workflowlLogger.trace("validInputs, replase2 " ,originalValue,newValue);
node.inputs[inputKey]=validInputs[inputKey];

}
}
});
}
});
}

return this;
}

updateValueByTargetValue(targetValue,replaceValue) {
this.initialize();

const replaceValueInObject=(obj)=>{
for (let key in obj) {
if (obj[key]===null||obj[key]===undefined) continue;

if (typeof obj[key]==='object') {
replaceValueInObject(obj[key]);
} else if (typeof obj[key]==='string') {
if (obj[key].includes(targetValue)) {
obj[key]=obj[key].replaceAll(targetValue,replaceValue);
}
}
}
};

Object.entries(this.workflowCopy).forEach(([id,node])=>{
replaceValueInObject(node);
});

return this;
}

replaceDatePlaceholders() {
this.initialize();

const formatDate=(format)=>{
const now=new Date();
const pad2=(n)=>String(n).padStart(2,'0');
const pad3=(n)=>String(n).padStart(3,'0');
return format
.replace(/yyyy/g,now.getFullYear())
.replace(/yy/g,String(now.getFullYear()).slice(-2))
.replace(/MM/g,pad2(now.getMonth()+1))
.replace(/dd/g,pad2(now.getDate()))
.replace(/HH/g,pad2(now.getHours()))
.replace(/mm/g,pad2(now.getMinutes()))
.replace(/ss/g,pad2(now.getSeconds()))
.replace(/SSS/g,pad3(now.getMilliseconds()));
};

const replaceDateInObject=(obj)=>{
for (let key in obj) {
if (obj[key]===null||obj[key]===undefined) continue;
if (typeof obj[key]==='object') {
replaceDateInObject(obj[key]);
} else if (typeof obj[key]==='string') {
obj[key]=obj[key].replace(/%date:([^%]+)%/g,(match,fmt)=>formatDate(fmt));
}
}
};

Object.entries(this.workflowCopy).forEach(([id,node])=>{
replaceDateInObject(node);
});

return this;
}

build() {
if (!this.hasInitialized) {
return this.originalWorkflow;
}
return this.workflowCopy;
}
}

function isNumericType(value) {
if (typeof value==='number') return true;
if (typeof value==='string'&&!isNaN(value)&&value.trim()!=='') return true;
return false;
}

function createWorkflowBuilder(workflow) {
return new ComfyUIWorkflowBuilder(workflow);
}