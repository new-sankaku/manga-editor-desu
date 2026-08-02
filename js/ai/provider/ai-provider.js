// AIプロバイダー基底クラス
class AIProvider{
constructor(id,name){
this.id=id;
this.name=name;
this._logger=new SimpleLogger('provider:'+id,LogLevel.DEBUG);
}
getSupportedRoles(){
return[];
}
supportsRole(role){
return this.getSupportedRoles().includes(role);
}
needsApiKey(){
return false;
}
getStatusReason(){
return'';
}
getApiKey(){
return null;
}
getEndpointUrl(){
return'';
}
async heartbeat(){
return false;
}
async executeT2I(layer,spinnerId){
throw new Error(this.id+' does not support T2I');
}
async executeI2I(layer,spinnerId){
throw new Error(this.id+' does not support I2I');
}
async executeRembg(layer,spinnerId){
throw new Error(this.id+' does not support Rembg');
}
async executeUpscale(layer,spinnerId){
throw new Error(this.id+' does not support Upscale');
}
async executeInpaint(layer,spinnerId){
throw new Error(this.id+' does not support Inpaint');
}
async executeAngle(layer,spinnerId,anglePrompt){
throw new Error(this.id+' does not support Angle');
}
async fetchModels(){
}
async fetchSamplers(){
}
async fetchUpscalers(){
}
async fetchDiffusionInformation(){
}
canUseInpaint(){
return this.supportsRole(AI_ROLES.Inpaint);
}
canUseAngle(){
return this.supportsRole(AI_ROLES.I2I_Angle);
}
}
