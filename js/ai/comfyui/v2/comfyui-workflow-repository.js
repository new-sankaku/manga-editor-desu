var comfyUIWorkflowRepositoryProto={
async saveWorkflow(type,id,name,workflowJson,enabled=false) {
const timestamp=new Date().toISOString();

if (!id) {
throw new Error("Workflow ID is required for saving.");
}

if (enabled) {
comfyuiLogger.debug("saveWorkflow: disableWorkflowsByType");
await this.disableWorkflowsByType(type);
}

try {
const existing=await this.store.getItem(id);
if (existing) {
const cleanWorkflow={...workflowJson};
delete cleanWorkflow.id;
delete cleanWorkflow.enabled;
delete cleanWorkflow.type;

await this.store.setItem(id,{
type,
name,
workflowJson: cleanWorkflow,
updatedAt: timestamp,
enabled,
});
return true;
}

const cleanWorkflow={...workflowJson};
delete cleanWorkflow.id;
delete cleanWorkflow.enabled;
delete cleanWorkflow.type;

await this.store.setItem(id,{
type,
name,
workflowJson: cleanWorkflow,
createdAt: timestamp,
updatedAt: timestamp,
enabled,
});
return true;
} catch (error) {
comfyuiLogger.error("Failed to save workflow:",error);
return false;
}
},

async getWorkflow(id) {
try {
const workflowData=await this.store.getItem(id);
if (!workflowData) {
throw new Error(`Workflow with ID ${id} not found.`);
}
return workflowData;
} catch (error) {
comfyuiLogger.error("Failed to retrieve workflow:",error);
return null;
}
},

async getAllWorkflows() {
const workflows=[];
try {
await this.store.iterate((value,key)=>{
workflows.push({id: key,...value});
});
return workflows;
} catch (error) {
comfyuiLogger.error("Failed to retrieve workflow list:",error);
return [];
}
},

async deleteWorkflow(id) {
try {
await this.store.removeItem(id);
return true;
} catch (error) {
comfyuiLogger.error("Failed to delete workflow:",error);
return false;
}
},

async updateWorkflow(name,updatedWorkflowJson,enabled) {
try {
const existing=await this.getWorkflow(name);
if (!existing) throw new Error("Workflow not found");

const timestamp=new Date().toISOString();
const cleanWorkflow={...updatedWorkflowJson};
delete cleanWorkflow.id;
delete cleanWorkflow.enabled;
delete cleanWorkflow.type;

existing.workflowJson=cleanWorkflow;
existing.updatedAt=timestamp;

if (enabled!==undefined) {
existing.enabled=enabled;
}

await this.store.setItem(name,existing);
return true;
} catch (error) {
comfyuiLogger.error("Failed to update workflow:",error);
return false;
}
},

async disableWorkflowsByType(type) {
try {
const workflowsToUpdate=[];
await this.store.iterate((value,key)=>{
if (value.type===type&&value.enabled) {
value.enabled=false;
workflowsToUpdate.push({key,value});
}
});

for (const {key,value} of workflowsToUpdate) {
await this.store.setItem(key,value);
}
return true;
} catch (error) {
comfyuiLogger.error("Failed to disable workflows by type:",error);
return false;
}
},

async getEnabledWorkflowByType(type) {
try {
let enabledWorkflow=null;
await this.store.iterate((value)=>{
comfyuiLogger.debug("value.type value.enabled",value.type,value.enabled);
if (value.type===type&&value.enabled) {
enabledWorkflow=value;
return false;
}
});
if(!enabledWorkflow){
comfyuiLogger.error("No enabled workflow for type: "+type);
return null;
}
return enabledWorkflow.workflowJson;
} catch (error) {
comfyuiLogger.error("Failed to retrieve enabled workflow by type:",error);
return null;
}
},

async existsByName(name) {
try {
let exists=false;
await this.store.iterate((value)=>{
if (value.name===name) {
exists=true;
return false;
}
});
return exists;
} catch (error) {
comfyuiLogger.error("Failed to check workflow existence:",error);
return false;
}
},
};

function createWorkflowRepository(providerKey) {
var repo=Object.create(comfyUIWorkflowRepositoryProto);
repo.store=localforage.createInstance({
name: "workflowStorage_"+providerKey,
storeName: "userWorkflows",
});
return repo;
}

var comfyUIWorkflowRepo_local=createWorkflowRepository('local');
var comfyUIWorkflowRepo_runpod=createWorkflowRepository('runpod');

(function migrateWorkflowStorage() {
if (localStorage.getItem('workflowMigrated_v1')) return;
var oldStore=localforage.createInstance({
name: "workflowStorage",
storeName: "userWorkflows",
});
oldStore.length().then(function(count) {
if (count===0) {
localStorage.setItem('workflowMigrated_v1','true');
return;
}
oldStore.iterate(function(value,key) {
comfyUIWorkflowRepo_local.store.setItem(key,value);
}).then(function() {
oldStore.clear().then(function() {
comfyuiLogger.info("Old workflow storage cleared after migration");
});
localStorage.setItem('workflowMigrated_v1','true');
comfyuiLogger.info("Workflow storage migration completed");
});
});
})();
