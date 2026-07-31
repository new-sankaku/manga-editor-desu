class ComfyUIWorkflowEditor {
constructor(options) {
options=options||{};
this.providerKey=options.providerKey||'local';
this.workflowRepo=options.workflowRepo||comfyUIWorkflowRepo_local;
this.objectInfoRepo=options.objectInfoRepo||comfyObjectInfoRepo;
this.provider=options.provider||null;
this.containerEl=options.containerEl||document;
this.tabs=new Map();
this.nodeTypes=null;
this.activeTabId=null;
}

async updateObjectInfoAndWorkflows() {
var self=this;
async function doUpdate(){
try {
const response=await comfyuiFetch(comfyUIUrls.objectInfoOnly);
if (!response.ok) {
throw new Error(`ObjectInfo取得失敗: ステータス ${response.status}`);
}

self.nodeTypes=await response.json();
await self.objectInfoRepo.saveObjectInfo(self.nodeTypes);
comfyuiLogger.debug("updateObjectInfoAndWorkflows",Object.keys(self.nodeTypes).length,"nodes");

self.tabs.forEach((tab)=>{
tab.renderNodes();
});
} catch (error) {
comfyuiLogger.error("ObjectInfoとWorkflowの更新中にエラー:",error);
}
}
if (this.provider) {
await comfyUIExecWithProvider(this.provider,doUpdate);
} else {
await doUpdate();
}
}


async initialize() {
this.nodeTypes=await this.objectInfoRepo.getObjectInfo();
// if (!this.nodeTypes) {
//   console.info("set default ObjectInfo");
//   this.nodeTypes = defaultObjectInfo;
// }

this.setupFileInput();
this.setupTabEvents();

await this.addDefaultWorkflows();
const workflows=await this.workflowRepo.getAllWorkflows();

let enabledTabId=null;
let firstTabId=null;

for (const workflowData of workflows) {
const {id,name,workflowJson,type,enabled}=workflowData;
const file=new File([JSON.stringify(workflowJson)],name,{
type: "application/json",
});

if (!workflowJson.id) {
workflowJson.id=id;
}

try {
await this.createTab(file,id,type,enabled);
if (enabled) {
enabledTabId=id;
}
if (!firstTabId) {
firstTabId=id;
}
} catch (error) {
comfyuiLogger.error(`ワークフロー "${name}" の読み込みに失敗しました:`,error);
}
}


if (enabledTabId) {
this.activeTabId=enabledTabId;
const enabledTab=this.tabs.get(enabledTabId);
if (enabledTab) {
this.tabs.forEach((tab)=>{
if (tab.id!==enabledTabId) {
tab.deactivate();
}
});
enabledTab.activate();
}
}else if (firstTabId) {
this.activeTabId=firstTabId;
const firstTab=this.tabs.get(firstTabId);
if (firstTab) {
firstTab.enabled=true;
firstTab.saveWorkflow();
this.onTabEnabledChanged(firstTab.type,firstTabId);

this.tabs.forEach((tab)=>{
if (tab.id!==firstTabId) {
tab.deactivate();
}
});
firstTab.activate();
}
}


this.renderTabs();

comfyui_monitorConnection_v2(this);
}

async addDefaultWorkflows() {
for (const workflow of comfyuiDefaultWorkflows) {
if (this.isDefaultWorkflowDeleted(workflow.name)) continue;
const exists=await this.workflowRepo.existsByName(workflow.name);
if (!exists) {
const id=`workflow-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

await this.workflowRepo.saveWorkflow(
workflow.type,
id,
workflow.name,
workflow.workflow,
workflow.enabled
);
}
}
}

getDeletedDefaultsKey() {
return `deletedDefaultWorkflows_${this.providerKey}`;
}

isDefaultWorkflowDeleted(name) {
try {
const deleted=JSON.parse(localStorage.getItem(this.getDeletedDefaultsKey())||'[]');
return deleted.includes(name);
} catch {
return false;
}
}

markDefaultWorkflowDeleted(name) {
const isDefault=comfyuiDefaultWorkflows.some(w=>w.name===name);
if (!isDefault) return;
try {
const deleted=JSON.parse(localStorage.getItem(this.getDeletedDefaultsKey())||'[]');
if (!deleted.includes(name)) {
deleted.push(name);
localStorage.setItem(this.getDeletedDefaultsKey(),JSON.stringify(deleted));
}
} catch {
// ignore
}
}

setupFileInput() {
this.containerEl
.querySelector("#workflowFile")
.addEventListener("change",async (e)=>{
const files=Array.from(e.target.files);
for (const file of files) {
await this.createTab(file,null);
}
e.target.value="";
this.renderTabs();
});
}

renderTabs() {
const tabList=this.containerEl.querySelector("#tabList");
tabList.innerHTML="";
const groupedTabs=this.groupTabsByType();
Object.keys(groupedTabs).forEach((type)=>{
const typeSeparator=document.createElement("div");
typeSeparator.className="comfui-tab-type-separator";
typeSeparator.innerText=type;
tabList.appendChild(typeSeparator);
groupedTabs[type].forEach((tab)=>{
const tabButton=tab.createTabButton();
tabList.appendChild(tabButton);
});
});
if (this.activeTabId) this.activateTab(this.activeTabId);
}

async createTab(file,id=null,type="T2I",enabled=false) {
try {
const text=await file.text();
const workflow=JSON.parse(text);

const tab=new ComfyUIWorkflowTab(file,workflow,this,id,type,enabled);
const tabContent=this.containerEl.querySelector("#tabContentContainer");
tabContent.appendChild(tab.createContent());
this.tabs.set(tab.id,tab);
this.activateTab(tab.id);
tab.renderNodes();
this.renderTabs();
if (!id) {
await tab.saveWorkflow();
}
} catch (error) {
comfyuiLogger.error("タブ作成エラー:",error);
}
}

groupTabsByType() {
return Array.from(this.tabs.values()).reduce((groups,tab)=>{
const type=tab.type||"T2I";
if (!groups[type]) groups[type]=[];
groups[type].push(tab);
return groups;
},{});
}

onTabEnabledChanged(type,tabId) {
this.tabs.forEach((tab)=>{
if (tab.workflow.type===type) {
tab.workflow.enabled=tab.id===tabId;
tab.enabled=tab.id===tabId;
}
});

this.renderTabs();
}

setupTabEvents() {
this.containerEl.querySelector("#tabList").addEventListener("click",(e)=>{
const tabButton=e.target.closest(".comfui-tab-button");
if (!tabButton) return;

const tabId=tabButton.dataset.tabId;
const tab=this.tabs.get(tabId);
if (!tab) return;

if (e.target.closest(".comfui-tab-close")) {
this.closeTab(tabId);
} else if (e.target.closest(".comfui-tab-download")) {
tab.downloadWorkflow();
} else {
this.activateTab(tabId);
}
});
}

activateTab(tabId) {
const oldTab=this.tabs.get(this.activeTabId);
if (oldTab) oldTab.deactivate();
const newTab=this.tabs.get(tabId);
if (newTab) {
this.activeTabId=tabId;
newTab.activate();
}
}

async closeTab(tabId) {
const tab=this.tabs.get(tabId);
if (!tab){
comfyuiLogger.warn("closeTab tab is null");
return;
}

try {
if (tabId) {
this.markDefaultWorkflowDeleted(tab.file.name);
const result=await this.workflowRepo.deleteWorkflow(tabId);
if (!result) {
comfyuiLogger.error(`Workflow delete is fail. ${tabId}`);
return;
}
}

tab.destroy();
this.tabs.delete(tabId);

if (this.activeTabId===tabId) {
const nextTab=Array.from(this.tabs.keys())[0];
if (nextTab) {
this.activateTab(nextTab);
}
}

this.renderTabs();
} catch (error) {
comfyuiLogger.error('タブの削除中にエラーが発生しました:',error);
}
}

getNodeType(className) {
return this.nodeTypes?.[className]||null;
}
}

let comfyUIWorkflowEditor;
document.addEventListener("DOMContentLoaded",async ()=>{
var localEditor=new ComfyUIWorkflowEditor({providerKey:'local',workflowRepo:comfyUIWorkflowRepo_local,objectInfoRepo:comfyObjectInfoRepo_local});
await localEditor.addDefaultWorkflows();
var runpodEditor=new ComfyUIWorkflowEditor({providerKey:'runpod',workflowRepo:comfyUIWorkflowRepo_runpod,objectInfoRepo:comfyObjectInfoRepo_runpod});
await runpodEditor.addDefaultWorkflows();
});