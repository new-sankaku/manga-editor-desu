// "Upscaler"
const comfyuiTypes=["T2I","I2I","REMBG","Upscaler"];

class ComfyUIWorkflowTab {
constructor(file,workflow,editor,id,type,enabled) {
this.type=type;
this.enabled=enabled;
this.file=file;
this.workflow=workflow;
this.editor=editor;
this.unsavedNodes=new Set();
if (id) {
this.id=id;
} else {
this.id=`workflow-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}
this.contentElement=null;
this.hiddenNodeTypes=["Note",undefined];
this.isActive=false;
this.masonry=null;
this.resizeObserver=null;
this.buttonElement=null;
}


markNodeAsUnsaved(nodeId) {
this.unsavedNodes.add(nodeId);
const nodeElement=this.contentElement.querySelector(`[data-node-id="${nodeId}"]`).closest('.comfui-node-wrapper');
if (nodeElement) {
nodeElement.classList.add('unsaved');
}
}

createTabButton() {
const button=document.createElement("div");
button.className="comfui-tab-button";
button.dataset.tabId=this.id;

const currentType=this.type||"T2I";
const enabled=this.enabled===true;

button.innerHTML=`
<label class="comfui-custom-radio">
<input type="radio" name="enabled-${currentType}" data-type="${currentType}" class="comfui-tab-enabled-radio" ${
enabled ? "checked" : ""
}>
<span class="comfui-custom-radio-label"></span>
</label>
<select class="comfui-tab-type-dropdown" title="Type">
${comfyuiTypes
.map(
(option) =>
`<option value="${option}" ${
option===currentType ? "selected" : ""
}>${option}</option>`
)
.join("")}
</select>
<span class="comfui-tab-name" title="${this.file.name}">${
this.file.name
}</span>
<div class="comfui-tab-actions">
<span class="comfui-tab-save" title="Save">Save</span>
<span class="comfui-tab-download" title="Download">Down</span>
<span class="comfui-tab-close" title="Close">Delete</span>
</div>
`;

const radioBtn=button.querySelector(".comfui-tab-enabled-radio");
radioBtn.addEventListener("click",async (e)=>{
e.stopPropagation();

document
.querySelectorAll(
`.comfui-tab-enabled-radio[data-type="${currentType}"]`
)
.forEach((radio)=>{
if (radio!==e.target) {
radio.checked=false;
const tabId=radio.closest(".comfui-tab-button").dataset.tabId;
const tab=this.editor.tabs.get(tabId);
if (tab) {
tab.enabled=false;
tab.saveWorkflow();
}
}
});

this.enabled=e.target.checked;
await this.saveWorkflow();
this.editor.onTabEnabledChanged(this.type,this.enabled ? this.id : null);
});

const typeDropdown=button.querySelector(".comfui-tab-type-dropdown");
typeDropdown.addEventListener("change",async (e)=>{
e.stopPropagation();
const oldType=this.type;
this.type=e.target.value;

if (this.enabled) {
this.editor.onTabEnabledChanged(oldType,null);
this.editor.onTabEnabledChanged(this.type,this.id);
}
await this.saveWorkflow();
this.editor.renderTabs();
});

button
.querySelector(".comfui-tab-save")
.addEventListener("click",async (e)=>{
e.stopPropagation();
await this.saveWorkflow();
});

this.buttonElement=button;
return button;
}

async saveWorkflow() {
comfyuiLogger.debug("saveWorkflow() start");
const cleanWorkflow={...this.workflow};

await comfyUIWorkflowRepository
.saveWorkflow(
this.type||"T2I",
this.id,
this.file.name,
cleanWorkflow,
this.enabled
)
.then(()=>{
comfyuiLogger.debug("Workflow saved successfully");
this.clearUnsavedState();
})
.catch((error)=>{
comfyuiLogger.error("Workflowの保存に失敗しました:",error);
});
}
clearUnsavedState() {
this.unsavedNodes.forEach(nodeId=>{
const nodeElement=this.contentElement.querySelector(`[data-node-id="${nodeId}"]`).closest('.comfui-node-wrapper');
if (nodeElement) {
nodeElement.classList.remove('unsaved');
}
});
this.unsavedNodes.clear();
}


createContent() {
const content=document.createElement("div");
content.className="comfui-tab-content";
content.dataset.tabId=this.id;
content.innerHTML=`<div class="comfui-node-list" data-tab-id="${this.id}"></div>`;
this.contentElement=content;
return content;
}

activate() {
this.isActive=true;
this.buttonElement?.classList.add("active");
this.contentElement?.classList.add("active");
this.initMasonry();
}

deactivate() {
this.isActive=false;
this.buttonElement?.classList.remove("active");
this.contentElement?.classList.remove("active");
if (this.masonry) {
this.masonry.destroy();
this.masonry=null;
}
}

destroy() {
this.buttonElement?.remove();
this.contentElement?.remove();
if (this.masonry) {
this.masonry.destroy();
}
if (this.resizeObserver) {
this.resizeObserver.disconnect();
}
}

getInputValue(nodeId,inputName) {
if (!this.workflow[nodeId]) return "";
const inputValue=this.workflow[nodeId].inputs[inputName];
if (inputValue!==undefined&&!Array.isArray(inputValue)) {
return inputValue;
}
return "";
}

getDisplayableInputCount(nodeId,apiNode) {
if (!apiNode?.input?.required) return 0;

return Object.entries(apiNode.input.required).filter(
([inputName,inputDef])=>{
if (inputDef[0]==="MODEL") return false;
const inputValue=this.workflow[nodeId]?.inputs[inputName];
return!Array.isArray(inputValue);
}
).length;
}

createMissingInput() {
return `<div class="comfui-input-container"><span class="comfui-unverified-label">⚠ ${getText('unverifiedNode')||'未確認'}</span></div>`;
}

createInput(nodeId,inputName,inputDef,apiNode) {
if (inputDef[0]==="MODEL") return "";

const inputValue=this.workflow[nodeId]?.inputs[inputName];
if (Array.isArray(inputValue)) return "";

const id=`${this.id}-node-${nodeId}-input-${inputName}`;
const value=this.getInputValue(nodeId,inputName);
const config=inputDef[1]||{};

const getComboOptions=(def)=>{
if (Array.isArray(def[0])) return def[0];
if (def[0]==="COMBO"&&def[1]&&Array.isArray(def[1].options)) return def[1].options;
return [];
};

if (config.image_upload===true) {
const options=getComboOptions(inputDef);
return `<div class="comfui-input-container">
<label class="comfui-input-label" for="${id}">${inputName}</label>
<select id="${id}" data-node-id="${nodeId}" data-input-name="${inputName}">
${options
.map(
(option) =>
`<option value="${option}" ${
value===option ? "selected" : ""
}>${option}</option>`
)
.join("")}
</select>
<div class="comfui-image-upload-area">
<label class="comfui-upload-button" for="file-${id}">
+ Add Image
<input type="file" 
id="file-${id}"
accept="image/*"
data-node-id="${nodeId}"
data-input-name="${inputName}"
data-preview-target="${nodeId}-${inputName}-preview">
</label>
<div class="comfui-image-preview hidden" data-preview-id="${nodeId}-${inputName}-preview">
<img src="" alt="プレビュー" class="comfui-preview-image">
</div>
</div>
</div>`;
}

if (Array.isArray(inputDef[0])||inputDef[0]==="COMBO") {
const options=getComboOptions(inputDef);
return `<div class="comfui-input-container">
<label class="comfui-input-label" for="${id}">${inputName}</label>
<select id="${id}" data-node-id="${nodeId}" data-input-name="${inputName}">
${options
.map(
(option) =>
`<option value="${option}" ${
value===option ? "selected" : ""
}>${option}</option>`
)
.join("")}
</select>
</div>`;
}

const isMultiline=config.multiline===true;
const type=
inputDef[0]==="INT"||inputDef[0]==="FLOAT" ? "number" : "text";

if (isMultiline) {
return `<div class="comfui-input-container">
<label class="comfui-input-label" for="${id}">${inputName}</label>
<textarea id="${id}"
data-node-id="${nodeId}"
data-input-name="${inputName}"
rows="4"
oninput="this.style.height = ''; this.style.height = this.scrollHeight + 'px'"
style="resize: none; overflow: hidden;">${value}</textarea>
</div>`;
}

return `<div class="comfui-input-container">
<label class="comfui-input-label" for="${id}">${inputName}</label>
<input type="${type}" id="${id}" value="${value}"
${config.min !== undefined ? `min="${config.min}"` : ""}
${config.max !== undefined ? `max="${config.max}"` : ""}
${config.step !== undefined ? `step="${config.step}"` : ""}
data-node-id="${nodeId}"
data-input-name="${inputName}">
 </div>`;
}

initMasonry() {
const grid=this.contentElement?.querySelector(".comfui-node-list");
if (!grid) return;

const masonryOptions={
itemSelector: ".comfui-node-wrapper",
columnWidth: ".comfui-node-wrapper",
percentPosition: false,
gutter: 16,
fitWidth: true,
transitionDuration: 0,
initLayout: false,
resize: true
};

setTimeout(()=>{
this.masonry=new Masonry(grid,masonryOptions);
if (this.masonry) {
this.masonry.layout();
}
},100);

let resizeTimeout;
window.addEventListener("resize",()=>{
if (resizeTimeout) {
clearTimeout(resizeTimeout);
}
resizeTimeout=setTimeout(()=>{
if (this.isActive&&this.masonry) {
this.masonry.reloadItems();
this.masonry.layout();
}
},150);
});
}

async initializeImagePreviews() {
const selects=this.contentElement.querySelectorAll(
"select[data-input-name]"
);
for (const select of selects) {
const nodeId=select.dataset.nodeId;
const inputName=select.dataset.inputName;
const selectedValue=select.value;

if (selectedValue) {
const previewTargetId=`${nodeId}-${inputName}-preview`;
const previewContainer=this.contentElement.querySelector(
`[data-preview-id="${previewTargetId}"]`
);

if (previewContainer) {
const previewImage=previewContainer.querySelector("img");
if (previewImage) {
try {
const imageUrl=await comfyui_view_image_v2(selectedValue);
if (imageUrl) {
previewImage.src=imageUrl;
previewContainer.classList.remove("hidden");

previewImage.onload=()=>{
if (this.masonry) {
this.masonry.layout();
}
URL.revokeObjectURL(imageUrl);
};
}
} catch (error) {
comfyuiLogger.error("画像プレビューの読み込みエラー:",error);
}
}
}
}
}
}

async renderNodes() {
const container=this.contentElement.querySelector(".comfui-node-list");

container.innerHTML="";
const nodes=Object.entries(this.workflow)
.filter(([_,node])=>!this.hiddenNodeTypes.includes(node.class_type))
.map(([id,node])=>{
const apiNode=this.editor.getNodeType(node.class_type);
const class_type=node.class_type;
const inputCount=apiNode
? this.getDisplayableInputCount(id,apiNode)
: 0;

return {
id,
node,
apiNode,
inputCount,
class_type
};
})
.sort((a,b)=>b.inputCount-a.inputCount);

const hasUnverifiedNodes=nodes.some(({class_type})=>notExistsWorkflowNodeVsComfyUI(class_type));
if(hasUnverifiedNodes){
const bannerElement=document.createElement("div");
bannerElement.className="comfui-unverified-banner";
bannerElement.innerHTML=`<div class="comfui-unverified-banner-title">⚠ ${getText('missingNode')||'ノード情報が確認できないノードがあります'}</div><div class="comfui-unverified-banner-desc">${getText('missingDescription')||''}</div>`;
container.appendChild(bannerElement);
}

nodes.forEach(({id,node,apiNode,class_type})=>{
const nodeElement=document.createElement("div");
nodeElement.className="comfui-node-wrapper";

const nodeTitle=node._meta?.title||node.class_type;
let nodeTypeDisplay='';
if(notExistsWorkflowNodeVsComfyUI(class_type)){
nodeTypeDisplay=`<div class="comfui-node-title comfui-node-title-warning">${id}: ${nodeTitle}</div>`+this.createMissingInput();
}else{
nodeTypeDisplay=`<div class="comfui-node-title comfui-node-title-normal">${id}: ${nodeTitle}</div>`;
}

let inputsDisplay="";
if (apiNode?.input?.required) {
inputsDisplay=Object.entries(apiNode.input.required)
.map(([inputName,inputDef])=>{
return this.createInput(id,inputName,inputDef,apiNode);
})
.filter((input)=>input!=="")
.join("");
}
nodeElement.innerHTML=nodeTypeDisplay+inputsDisplay;
container.appendChild(nodeElement);
});

if (this.masonry) {
this.masonry.reloadItems();
this.masonry.layout();
} else {
this.initMasonry();
}

this.setupInputListeners();
await this.initializeImagePreviews();
}

setupInputListeners() {
this.contentElement.querySelectorAll('input[type="text"], input[type="number"], select, textarea').forEach((input)=>{
const nodeId=input.dataset.nodeId;
const inputName=input.dataset.inputName;

if (nodeId&&inputName&&this.workflow[nodeId]) {
this.workflow[nodeId].inputs[inputName]=input.value;
}

input.addEventListener("change",async (e)=>{
const nodeId=e.target.dataset.nodeId;
const inputName=e.target.dataset.inputName;
if (this.workflow[nodeId]&&inputName) {
this.workflow[nodeId].inputs[inputName]=e.target.value;
this.markNodeAsUnsaved(nodeId);

if (e.target.tagName.toLowerCase()==="select") {
const selectedValue=e.target.value;
const previewTargetId=`${nodeId}-${inputName}-preview`;
const previewContainer=this.contentElement.querySelector(`[data-preview-id="${previewTargetId}"]`);

if (previewContainer) {
const previewImage=previewContainer.querySelector("img");
if (previewImage) {
comfyuiLogger.debug("selectedValue",selectedValue);
const imageUrl=await comfyui_view_image_v2(selectedValue);
if (imageUrl) {
previewImage.src=imageUrl;
previewContainer.classList.remove("hidden");

previewImage.onload=()=>{
if (this.masonry) {
this.masonry.layout();
}
URL.revokeObjectURL(imageUrl);
};
}
}
}
}
}
});

if (input.tagName.toLowerCase()==="textarea") {
let timeoutId;
input.addEventListener("input",()=>{
if (timeoutId) {
clearTimeout(timeoutId);
}
timeoutId=setTimeout(()=>{
if (this.masonry&&this.isActive) {
this.masonry.layout();
}
},5);

const nodeId=input.dataset.nodeId;
const inputName=input.dataset.inputName;
if (nodeId&&inputName&&this.workflow[nodeId]) {
this.workflow[nodeId].inputs[inputName]=input.value;
this.markNodeAsUnsaved(nodeId);
}
});

if (this.resizeObserver) {
this.resizeObserver.disconnect();
}

this.resizeObserver=new ResizeObserver(()=>{
if (this.masonry) {
window.dispatchEvent(new Event("resize"));
this.masonry.layout();
}
});

this.resizeObserver.observe(input);
}
});

this.contentElement.querySelectorAll('input[type="file"]').forEach((input)=>{
input.addEventListener("change",async (e)=>{
const file=e.target.files[0];
if (!file) return;

const nodeId=e.target.dataset.nodeId;
const inputName=e.target.dataset.inputName;
const previewTargetId=e.target.dataset.previewTarget;

if (this.workflow[nodeId]&&inputName) {
try {
const uploadResult=await comfyui_uploadImage_v2(file);
if (uploadResult.success) {
this.workflow[nodeId].inputs[inputName]=uploadResult.name;
this.markNodeAsUnsaved(nodeId);

const select=this.contentElement.querySelector(
`select[data-node-id="${nodeId}"][data-input-name="${inputName}"]`
);
if (select) {
const exists=Array.from(select.options).some(
(option)=>option.value===uploadResult.name
);
if (!exists) {
const option=new Option(
uploadResult.name,
uploadResult.name,
true,
true
);
select.add(option);
}
select.value=uploadResult.name;
}
}
} catch (error) {
comfyuiLogger.error("アップロードエラー:",error);
}

const reader=new FileReader();
const previewContainer=this.contentElement.querySelector(
`[data-preview-id="${previewTargetId}"]`
);
const previewImage=previewContainer?.querySelector("img");

if (!previewContainer||!previewImage) return;

reader.onload=(e)=>{
previewImage.src=e.target.result;
previewContainer.classList.remove("hidden");
previewImage.onload=()=>{
if (this.masonry) {
this.masonry.layout();
}
};
};

reader.readAsDataURL(file);
}
});
});
}

async downloadWorkflow() {
const fixedWorkflow=await comfyui_fixWorkflowTypes_v2(this.workflow);
const jsonStr=JSON.stringify(fixedWorkflow,null,2);
const blob=new Blob([jsonStr],{type: "application/json"});
const url=URL.createObjectURL(blob);

const a=document.createElement("a");
a.href=url;
a.download=`${this.file.name.replace(/\.[^/.]+$/, "")}_edited.json`;
document.body.appendChild(a);
a.click();
document.body.removeChild(a);
URL.revokeObjectURL(url);
}
}