var unifiedSettingsWindow=(function(){
var overlayEl=null;
function open(){
if(!overlayEl)overlayEl=$('unifiedSettingsOverlay');
overlayEl.classList.add('active');
roleAssignmentUI.buildMatrix();
var falaiProvider=providerRegistry.get('falai');
if(falaiProvider&&falaiProvider.getApiKey()&&isProviderInUse('falai')){
falaiProvider.fetchModelsIfNeeded();
}
llmFetchModelsIfConfigured();
}
function close(){
if(!overlayEl)return;
overlayEl.classList.remove('active');
}
function apply(){
close();
}
function switchTab(idx){
var tabs=overlayEl.querySelectorAll('.us-tab');
var contents=overlayEl.querySelectorAll('.us-tab-content');
tabs.forEach(function(t,i){
t.classList.toggle('active',i===idx);
});
contents.forEach(function(c,i){
c.classList.toggle('active',i===idx);
});
}
return{
open:open,
close:close,
apply:apply,
switchTab:switchTab
};
})();
