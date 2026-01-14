class ComfyUIWorkflowWindow {
constructor() {
this.element=null;
this.x=0;
this.y=0;
}


initializeWindow() {
if (this.element) return;

this.element=document.createElement("div");
this.element.style.position="fixed";
this.element.style.top="50%";
this.element.style.left="50%";
this.element.style.transform="translate(-50%, -50%)";
this.element.style.backgroundColor="var(--background-color-A)";
this.element.style.boxShadow="0 0 0 1px var(--color-border), 0 4px 30px rgba(0, 0, 0, 0.7)";
this.element.style.border="2px solid var(--color-accent)";
this.element.style.borderRadius="8px";
this.element.style.display="none";
this.element.style.width="97vw";
this.element.style.height="97vh";
this.element.style.zIndex="1000";

const addWorkflowLabel=getText("comfyUI_addWorkflow");
const testGenerate=getText("comfyUI_testGenerate");
const workflowHelp=getText("comfyUI_workflowHelp");

this.element.innerHTML=`
<button id="closeButton" style="position: absolute; right: -30px; top: 0; padding: 5px 10px; background: var(--background-color-B); border: 1px solid var(--color-border); color: var(--component-text-color); cursor: pointer; z-index: 1001; font-size: 16px; border-radius: 4px;">✕</button>
<div class="comfui-container" style="width: 100%; height: 100%; background-color: var(--background-color-A); margin: 0; padding: 8px; border-radius: 0;">
 <div class="comfui-sidebar">
<div class="comfui-sidebar-header" style="cursor: move;">
 <label class="comfui-file-input-button">
+ ${addWorkflowLabel}
<input type="file" id="workflowFile" accept=".json,.txt" multiple>
 </label>
</div>
<div class="comfui-tab-list" id="tabList"></div>
 </div>

 <div class="comfui-main-content">
<div class="comfui-tab-content-container" id="tabContentContainer"></div>
 </div>

 <div class="comfui-right-sidebar">
<div id="apiSettingsUrlHelpe">
 <label id="ExternalService_Heartbeat_Label_fw">Connection:</label>
</div>
<button id="comfyUIFwGenerateButton" class="comfui-sidebar-button">${testGenerate}</button>
<div id="generatedImageContainer" class="comfui-generated-image-container">
 <div id="generatedImagePlaceholder" class="comfui-image-placeholder" style="display:flex;align-items:center;justify-content:center;height:150px;border:2px dashed rgba(255,215,0,0.3);border-radius:8px;color:#888;font-size:12px;text-align:center;padding:10px;">Test Generate to preview</div>
 <img id="generatedImage" style="display:none;cursor:pointer;max-width:100%;border-radius:8px;" title="Click to enlarge">
</div>

<div>
<label>
${workflowHelp}
</label>
</div>
 </div>
</div>`;

document.body.appendChild(this.element);

const closeButton=this.element.querySelector("#closeButton");
closeButton.addEventListener("click",()=>this.hide());

const generatedImage=this.element.querySelector("#generatedImage");
generatedImage.addEventListener("click",()=>{
if(!generatedImage.src)return;
const overlay=document.createElement("div");
overlay.style.cssText="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);display:flex;align-items:center;justify-content:center;z-index:9999;cursor:pointer;";
const img=document.createElement("img");
img.src=generatedImage.src;
img.style.cssText="max-width:95%;max-height:95%;object-fit:contain;";
overlay.appendChild(img);
overlay.addEventListener("click",()=>overlay.remove());
document.body.appendChild(overlay);
});

this.setupEventListeners();
}




setupEventListeners() {
interact(this.element)
.draggable({
enabled: false,
ignoreFrom: 'textarea, input[type="text"]',
inertia: true,
modifiers: [
interact.modifiers.restrictRect({
restriction: "parent",
endOnly: true,
}),
],
listeners: {
start: ()=>{
const rect=this.element.getBoundingClientRect();
this.x=rect.left;
this.y=rect.top;
},
move: (event)=>{
this.x+=event.dx;
this.y+=event.dy;

this.element.style.transform=`translate(0, 0)`;
this.element.style.top=`${this.y}px`;
this.element.style.left=`${this.x}px`;
},
},
})
.resizable({
edges: {left: true,right: true,bottom: true,top: true},
restrictEdges: {
outer: "parent",
endOnly: true,
},
restrictSize: {
min: {width: 400,height: 300},
},
inertia: true,
})
.on("resizemove",(event)=>{
Object.assign(event.target.style,{
width: `${event.rect.width}px`,
height: `${event.rect.height}px`,
});
});

var comfyUIFwGenerateButton=this.element.querySelector("#comfyUIFwGenerateButton");
var testGenerateText=getText("comfyUI_testGenerate");
comfyUIFwGenerateButton.addEventListener("click",async function(){
var tabId=comfyUIWorkflowEditor.activeTabId;
if(!tabId)return;
var tab=comfyUIWorkflowEditor.tabs.get(tabId);
if(!tab)return;
comfyUIFwGenerateButton.disabled=true;
comfyUIFwGenerateButton.innerHTML='<span class="spinner-border spinner-border-sm text-light"></span>';
try{
var result=await comfyui_put_queue_v2(tab.workflow);
if(result&&result.error){
if(typeof ComfyUIGuide!=='undefined'){
ComfyUIGuide.showGenerationErrorGuide(result.message);
}
}else if(result){
var generatedImage=document.querySelector("#generatedImage");
var placeholder=document.querySelector("#generatedImagePlaceholder");
if(generatedImage){
generatedImage.src=result;
generatedImage.style.display="block";
}
if(placeholder){
placeholder.style.display="none";
}
}
}finally{
comfyUIFwGenerateButton.disabled=false;
comfyUIFwGenerateButton.textContent=testGenerateText;
}
});
}

show() {
if (!this.element) {
this.initializeWindow();
}
this.element.style.display="block";
var self=this;
setTimeout(function(){
if(typeof ComfyUIGuide!=='undefined'){
comfyui_apiHeartbeat_v2().then(function(isOnline){
ComfyUIGuide.showSetupGuide(isOnline);
});
}
},300);
}

hide() {
if (this.element) {
this.element.style.display="none";
}
}
}
let comfyUIWorkflowWindow=null;

document.addEventListener("DOMContentLoaded",()=>{
const openButton=document.getElementById("openWorkflowButton");
openButton.addEventListener("click",()=>{
if (!comfyUIWorkflowWindow) {
comfyUIWorkflowWindow=new ComfyUIWorkflowWindow();
}
comfyUIWorkflowWindow.show();

if (!comfyUIWorkflowEditor) {
comfyUIWorkflowEditor=new ComfyUIWorkflowEditor();
comfyUIWorkflowEditor.initialize();
comfyui_monitorConnection_v2();
}
});
});
