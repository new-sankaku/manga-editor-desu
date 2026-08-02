// GrokプロバイダーxAI: OpenAI互換API（https://api.x.ai/v1）
class GrokProvider extends LLMProvider{
constructor(){
super('grok','Grok');
}
needsApiKey(){
return true;
}
getApiKey(){
var el=$('grokApiKey');
return el?el.value.trim():'';
}
getEndpointUrl(){
return'https://api.x.ai';
}
getBaseUrl(){
return'https://api.x.ai/v1';
}
getModelSelectIds(){
return{text:'grokModelText',vision:'grokModelVision'};
}
getNoticeElementId(){
return'grokConnNotice';
}
getHelpUrl(){
return'html/API_Help/llm_settings.html#grok';
}
_listHeaders(){
var apiKey=this.getApiKey();
if(!apiKey)return{};
return{'Authorization':'Bearer '+apiKey};
}
_requestHeaders(){
var apiKey=this.getApiKey();
if(!apiKey){
throw new Error(this.name+': '+i18next.t('llmErrorNoApiKey'));
}
return{
'Authorization':'Bearer '+apiKey,
'Content-Type':'application/json'
};
}
async fetchModels(options){
if(!this.getApiKey()){
this._populateSelects([]);
this.setConnectionNotice('noApiKey');
return;
}
return super.fetchModels(options);
}
}
