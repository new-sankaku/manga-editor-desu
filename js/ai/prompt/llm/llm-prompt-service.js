// LLMによるプロンプト生成: 文章→タグ（Text2Prompt）と画像→タグ（Image2Prompt_LLM）
const LLM_TEXT2PROMPT_SYSTEM=[
'You are a prompt engineer for anime and manga style Stable Diffusion image generation.',
'Convert the scene description into Danbooru style tags.',
'Rules:',
'- Output ONLY comma separated lowercase tags. No sentences, no explanation, no headings, no code fences.',
'- Use common Danbooru tag vocabulary such as 1girl, solo, school uniform, rooftop, crying, from below.',
'- Cover subject count, appearance, clothing, expression, pose, camera angle, background and lighting when the description implies them.',
'- Do not invent character names or series names that the description does not mention.',
'- Output between 15 and 40 tags.'
].join('\n');

const LLM_IMAGE2PROMPT_SYSTEM=[
'You are an image tagger for anime and manga style illustrations.',
'Describe the given image as Danbooru style tags.',
'Rules:',
'- Output ONLY comma separated lowercase tags. No sentences, no explanation, no headings, no code fences.',
'- Describe only what is actually visible: subject count, hair, eyes, clothing, expression, pose, composition, background, lighting and art style.',
'- Do not guess character names or series names.',
'- Output between 15 and 40 tags.'
].join('\n');

const LLM_PROVIDER_IDS=['grok','ollama'];

// 使用サービス表で選ばれているLLMだけモデル一覧を自動取得する（起動時）。
// 「なし」にしたサービスに接続しにいってトーストを出さないため。失敗しても画面内の警告のみ
function llmFetchModelsIfInUse(){
llmFetchModels(function(provider){
return isProviderInUse(provider.id);
});
}

// 設定ウィンドウを開いた時用。ロール未割り当てでも接続情報が入っているLLMは取得する。
// 割り当て前でもモデルを選べるようにするため。silent取得なのでトーストは出ない
function llmFetchModelsIfConfigured(){
llmFetchModels(function(provider){
return provider.isConfigured();
});
}

function llmFetchModels(shouldFetch){
LLM_PROVIDER_IDS.forEach(function(id){
var provider=providerRegistry.get(id);
if(!provider)return;
if(!shouldFetch(provider))return;
if(provider.hasLoadedModels())return;
provider.fetchModels({silent:true});
});
}

function getLLMQueue(provider){
if(provider.id==='grok')return grokQueue;
if(provider.id==='ollama')return ollamaQueue;
return null;
}

function requireLLMProvider(role){
var provider=providerRegistry.getProviderForRole(role);
if(!provider){
throw new Error(i18next.t('llmErrorNoProvider'));
}
var queue=getLLMQueue(provider);
if(!queue){
throw new Error(i18next.t('llmErrorNoProvider'));
}
return{provider:provider,queue:queue};
}

function normalizeTagOutput(text){
var body=text.replace(/```[a-z]*\n?/gi,'').replace(/```/g,'');
body=body.replace(/^[^\S\r\n]*[-*・][^\S\r\n]*/gm,'');
body=body.replace(/[\r\n]+/g,',');
var seen={};
var tags=[];
body.split(',').forEach(function(raw){
var tag=raw.trim().replace(/\s+/g,' ');
if(!tag)return;
var key=tag.toLowerCase();
if(seen[key])return;
seen[key]=true;
tags.push(tag);
});
return tags.join(', ');
}

async function llmText2Prompt(description,existingPrompt){
var target=requireLLMProvider(AI_ROLES.Text2Prompt);
var userPrompt='Scene description:\n'+description;
if(existingPrompt&&existingPrompt.trim()){
userPrompt+='\n\nTags already present in the prompt (do not repeat them):\n'+existingPrompt;
}
var messages=target.provider.buildTextMessages(LLM_TEXT2PROMPT_SYSTEM,userPrompt);
var raw=await target.queue.add(function(){
return target.provider.chat(messages,{temperature:0.4});
});
var tags=normalizeTagOutput(raw);
if(!tags){
throw new Error(target.provider.name+': '+i18next.t('llmErrorEmptyResponse'));
}
return tags;
}

async function llmImage2Prompt(layer,spinnerId){
var target;
try{
target=requireLLMProvider(AI_ROLES.Image2Prompt_LLM);
}catch(e){
createToastError(i18next.t('llmImage2PromptTitle'),e.message);
removeSpinner(spinnerId);
return;
}
var dataUrl=imageObject2DataURL(layer);
var messages=target.provider.buildVisionMessages(
LLM_IMAGE2PROMPT_SYSTEM,
'Tag this image.',
dataUrl
);
var p=target.queue.add(function(){
setCurrentAiTask(spinnerId);
return target.provider.chat(messages,{temperature:0.2,vision:true});
});
updateAiTaskCancelInfo(spinnerId,{queueName:target.provider.id,queueItemId:p._queueItemId});
p.then(function(raw){
var tags=normalizeTagOutput(raw);
if(!tags){
createToastError(i18next.t('llmImage2PromptTitle'),i18next.t('llmErrorEmptyResponse'));
return;
}
if(layer.text2img_prompt){
layer.text2img_prompt=layer.text2img_prompt+', '+tags;
}else{
layer.text2img_prompt=tags;
}
createToast(i18next.t('llmImage2PromptTitle'),tags);
refreshPromptPanel(layer);
}).catch(function(error){
createToastError(i18next.t('llmImage2PromptTitle'),error.message,1000*10);
llmLogger.error('llmImage2Prompt failed: '+error.message);
}).finally(function(){
removeSpinner(spinnerId);
});
}
