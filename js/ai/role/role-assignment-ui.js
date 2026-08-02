// Role Assignment: Role×プロバイダーのマトリクスUI
var roleAssignmentUI=(function(){
var PROVIDER_COLUMNS=[
{id:ROLE_NONE,label:'None'},
{id:'localComfyUI',label:'ComfyUI (Local)'},
{id:'runpodComfyUI',label:'RunPod ComfyUI'},
{id:'localSDWebUI',label:'SD WebUI (A1111/Forge)'},
{id:'falai',label:'Fal.ai'},
{id:'grok',label:'Grok'},
{id:'ollama',label:'Ollama'}
];
var ROLE_ROWS=ROLE_MATRIX_ROWS;
var tempAssignments={};
function open(){
unifiedSettingsWindow.open();
}
function close(){
unifiedSettingsWindow.close();
}
function applyAssignments(){
ROLE_ROWS.forEach(function(row){
providerRegistry.setRoleAssignment(row.role,tempAssignments[row.role]);
});
updateLayerPanel();
raLogger.info('Role assignments applied');
debouncedSettingsSave();
}
function buildMatrix(){
tempAssignments={};
ROLE_ROWS.forEach(function(row){
tempAssignments[row.role]=providerRegistry.getRoleAssignment(row.role);
});
var tbody=$('roleMatrixBody');
tbody.innerHTML='';
ROLE_ROWS.forEach(function(row){
var tr=document.createElement('tr');
var tdLabel=document.createElement('td');
tdLabel.setAttribute('data-i18n',row.labelKey);
tdLabel.innerHTML=i18next.t(row.labelKey);
tr.appendChild(tdLabel);
var effective=providerRegistry.getProviderForRole(row.role);
PROVIDER_COLUMNS.forEach(function(col){
var isNoneColumn=(col.id===ROLE_NONE);
var td=document.createElement('td');
if(isNoneColumn)td.classList.add('role-col-none');
var radio=document.createElement('input');
radio.type='radio';
radio.name='roleAssign_'+row.role;
radio.className='role-radio';
radio.value=col.id;
if(!isNoneColumn){
var provider=providerRegistry.get(col.id);
if(!provider||!provider.supportsRole(row.role)){
radio.disabled=true;
td.className='role-provider-unavailable';
}
}
var assigned=tempAssignments[row.role];
if(assigned&&assigned!=='default'){
radio.checked=(assigned===col.id);
}else if(effective){
radio.checked=(effective.id===col.id);
}else{
radio.checked=isNoneColumn;
}
radio.addEventListener('change',function(){
if(this.checked){
tempAssignments[row.role]=col.id;
providerRegistry.setRoleAssignment(row.role,col.id);
updateWorkflowType();
updateLayerPanel();
debouncedSettingsSave();
apiHeartbeat();
}
});
td.appendChild(radio);
tr.appendChild(td);
});
tbody.appendChild(tr);
});
}
return{
open:open,
close:close,
apply:applyAssignments,
applyAssignments:applyAssignments,
buildMatrix:buildMatrix
};
})();
