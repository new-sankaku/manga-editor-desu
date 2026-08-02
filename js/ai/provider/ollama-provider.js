// Ollamaプロバイダー: ローカルLLM。OpenAI互換API（http://localhost:11434/v1）
class OllamaProvider extends LLMProvider{
constructor(){
super('ollama','Ollama');
}
needsApiKey(){
return false;
}
getEndpointUrl(){
var el=$('ollamaUrl');
var url=el?el.value.trim():'';
return url.replace(/\/+$/,'');
}
getBaseUrl(){
var url=this.getEndpointUrl();
if(!url)return'';
return url+'/v1';
}
getModelSelectIds(){
return{text:'ollamaModelText',vision:'ollamaModelVision'};
}
getNoticeElementId(){
return'ollamaConnNotice';
}
getHelpUrl(){
return'html/API_Help/llm_settings.html#ollama';
}
_requestHeaders(){
if(!this.getEndpointUrl()){
throw new Error(this.name+': '+i18next.t('llmErrorNoUrl'));
}
return{'Content-Type':'application/json'};
}
async fetchModels(options){
if(!this.getEndpointUrl()){
this._populateSelects([]);
return;
}
return super.fetchModels(options);
}
async heartbeat(){
if(!this.getEndpointUrl())return false;
return super.heartbeat();
}
}
