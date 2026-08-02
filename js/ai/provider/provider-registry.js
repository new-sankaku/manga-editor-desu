// プロバイダーレジストリ: プロバイダー登録とRole→プロバイダーのルーティング管理
var providerRegistry=(function(){
var providers={};
var activeProviderId=null;
var apiModeToProviderId={};
var roleAssignments={};
function register(provider){
providers[provider.id]=provider;
registryLogger.debug('Registered provider: '+provider.id);
}
function get(id){
return providers[id]||null;
}
function getAll(){
return Object.values(providers);
}
function mapApiMode(apiModeValue,providerId){
apiModeToProviderId[apiModeValue]=providerId;
}
function syncFromApiMode(apiModeValue){
var id=apiModeToProviderId[apiModeValue];
if(id){
setActive(id);
return true;
}
registryLogger.debug('No provider mapped for apiMode: '+apiModeValue);
return false;
}
function setActive(id){
if(!providers[id]){
registryLogger.error('Provider not found: '+id);
return false;
}
activeProviderId=id;
registryLogger.info('Active provider: '+id);
return true;
}
function getActive(){
if(!activeProviderId)return null;
return providers[activeProviderId]||null;
}
function getActiveId(){
return activeProviderId;
}
function setRoleAssignment(role,providerId){
if(providerId==='default'||!providerId){
delete roleAssignments[role];
}else{
roleAssignments[role]=providerId;
}
registryLogger.debug('Role assignment: '+role+' -> '+(providerId||'default'));
}
function getRoleAssignment(role){
return roleAssignments[role]||'default';
}
function getAllRoleAssignments(){
return Object.assign({},roleAssignments);
}
function loadRoleAssignments(data){
roleAssignments={};
if(data&&typeof data==='object'){
Object.keys(data).forEach(function(key){
if(data[key]&&data[key]!=='default'){
roleAssignments[key]=data[key];
}
});
}
}
function getProviderForRole(role){
var assignedId=roleAssignments[role];
if(assignedId===ROLE_NONE)return null;
if(assignedId&&assignedId!=='default'){
var provider=providers[assignedId];
if(provider&&provider.supportsRole(role)){
return provider;
}
registryLogger.debug('Assigned provider '+assignedId+' does not support role: '+role);
return null;
}
var active=getActive();
if(active&&active.supportsRole(role)){
return active;
}
return null;
}
return{
register:register,
get:get,
getAll:getAll,
mapApiMode:mapApiMode,
syncFromApiMode:syncFromApiMode,
setActive:setActive,
getActive:getActive,
getActiveId:getActiveId,
setRoleAssignment:setRoleAssignment,
getRoleAssignment:getRoleAssignment,
getAllRoleAssignments:getAllRoleAssignments,
loadRoleAssignments:loadRoleAssignments,
getProviderForRole:getProviderForRole
};
})();
