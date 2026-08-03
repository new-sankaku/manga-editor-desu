// LLMによるプロンプト生成: 文章→タグ（Text2Prompt）と画像→タグ（Image2Prompt_LLM）
const LLM_TEXT2PROMPT_SYSTEM=[
'Convert the scene description into Danbooru style tags.',
'',
'Watch these points:',
'',
// 「1girl, solo, ...」と例を並べると全部の出力に1girlとsoloが入る
'- Cover what the description implies: how many people, what they look like, what they wear, their',
'  expression, their pose, the camera angle, the background and the light. Nothing it does not imply.',
'',
'- "full body", "wide shot", "upper body" and "close-up" are labels put on finished pictures, not',
'  instructions. What decides the framing is which things you name. To show a whole figure name the',
'  shoes and the ground; to show only a face name nothing below the shoulders, or the view pulls',
'  back to fit in whatever you named.',
'',
'- Write what the picture has to show and stop. Too few tags and the model fills the gaps with',
'  whatever it likes; too many and each one gets weaker.',
'',
'- Do not invent character names or series names that the description does not mention.',
'',
'- Output ONLY comma separated lowercase tags. No sentences, no explanation, no headings,',
'  no code fences.'
].join('\n');

const LLM_IMAGE2PROMPT_SYSTEM=[
'Describe the given image as Danbooru style tags.',
'',
'Watch these points:',
'',
'- Only what is actually visible: how many people, hair, eyes, clothing, expression, pose,',
'  composition, background, lighting, art style. Do not tag what you assume is there.',
'',
'- Do not guess character names or series names.',
'',
'- Write what is in the image and stop. Padding the list with tags that are not there moves the',
'  picture away from the one you were given.',
'',
'- Output ONLY comma separated lowercase tags. No sentences, no explanation, no headings,',
'  no code fences.'
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
