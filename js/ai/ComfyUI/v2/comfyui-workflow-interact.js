class ComfyUIWorkflowWindow {
constructor() {
this.element = null;
this.x = 0;
this.y = 0;
}


initializeWindow() {
if (this.element) return;

this.element = document.createElement("div");
this.element.style.position = "fixed";
this.element.style.top = "50%";
this.element.style.left = "50%";
this.element.style.transform = "translate(-50%, -50%)";
this.element.style.backgroundColor = "var(--background-color-A)";
this.element.style.boxShadow = "0 0 0 1px var(--color-border), 0 4px 30px rgba(0, 0, 0, 0.7)";
this.element.style.border = "2px solid var(--color-accent)";
this.element.style.borderRadius = "8px";
this.element.style.display = "none";
this.element.style.width = "97vw";
this.element.style.height = "97vh";
this.element.style.zIndex = "1000";

const addWorkflowLabel = getText("comfyUI_addWorkflow");
const testGenerate = getText("comfyUI_testGenerate");
const workflowHelp = getText("comfyUI_workflowHelp");

this.element.innerHTML = `
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
 <img id="generatedImage" class="comfui-preview-image hidden">
</div>

<div>
<label>
${workflowHelp}
</label>
</div>
 </div>
</div>`;

document.body.appendChild(this.element);

const closeButton = this.element.querySelector("#closeButton");
closeButton.addEventListener("click", () => this.hide());

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
start: () => {
const rect = this.element.getBoundingClientRect();
this.x = rect.left;
this.y = rect.top;
},
move: (event) => {
this.x += event.dx;
this.y += event.dy;

this.element.style.transform = `translate(0, 0)`;
this.element.style.top = `${this.y}px`;
this.element.style.left = `${this.x}px`;
},
},
})
.resizable({
edges: { left: true, right: true, bottom: true, top: true },
restrictEdges: {
outer: "parent",
endOnly: true,
},
restrictSize: {
min: { width: 400, height: 300 },
},
inertia: true,
})
.on("resizemove", (event) => {
Object.assign(event.target.style, {
width: `${event.rect.width}px`,
height: `${event.rect.height}px`,
});
});

const comfyUIFwGenerateButton = this.element.querySelector("#comfyUIFwGenerateButton");
comfyUIFwGenerateButton.addEventListener("click", async () => {
const tabId = comfyUIWorkflowEditor.activeTabId;
if (!tabId) return;

const tab = comfyUIWorkflowEditor.tabs.get(tabId);
if (!tab) return;

// console.log("comfyuiQueue Workflow", JSON.stringify(tab.workflow));

const img = await comfyui_put_queue_v2(tab.workflow);
if (!img) return;

const generatedImage = this.element.querySelector("#generatedImage");
generatedImage.src = img;
generatedImage.classList.remove("hidden");
});
}

show() {
if (!this.element) {
this.initializeWindow();
}
this.element.style.display = "block";
}

hide() {
if (this.element) {
this.element.style.display = "none";
}
}
}
let comfyUIWorkflowWindow = null;

document.addEventListener("DOMContentLoaded", () => {
const openButton = document.getElementById("openWorkflowButton");
openButton.addEventListener("click", () => {
if (!comfyUIWorkflowWindow) {
comfyUIWorkflowWindow = new ComfyUIWorkflowWindow();
}
comfyUIWorkflowWindow.show();

if (!comfyUIWorkflowEditor) {
comfyUIWorkflowEditor = new ComfyUIWorkflowEditor();
comfyUIWorkflowEditor.initialize();
comfyui_monitorConnection_v2();
}
});
});
