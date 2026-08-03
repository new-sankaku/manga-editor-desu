// LLMによるプロンプト生成: 文章→タグ（Text2Prompt）と画像→タグ（Image2Prompt_LLM）
const LLM_TEXT2PROMPT_SYSTEM=[
'Convert the scene description into Danbooru style tags for one manga panel.',
'',
'Watch these points:',
'',
'- Cover what the description implies: how many people, what they look like, what they wear, their',
'  expression, their pose, the camera angle, the background and the light. Nothing it does not imply.',
'',
// 指針16章。フレーミングタグが効かないことと、その代わりに何を書くか
'- "full body", "wide shot", "upper body" and "close-up" are labels applied to finished pictures,',
'  not instructions. The distance is set by which things you name:',
'    head to shoes  -> name the shoes, the legs, and the floor they stand on',
'    waist up       -> the clothes above the waist, the hands. not the shoes, not the floor',
'    the face       -> eyes, mouth, hair, expression. nothing below the shoulders',
'    the place      -> things in that place too large to fit inside a frame. people out, or far away',
'  Naming something outside the frame you want makes the view pull back to include it.',
'',
// 指針13章。素の感情ラベルは使わせない
'- Do not name an emotion. "angry", "sad", "happy", "surprised" and "smiling" each cover everything',
'  from faint to extreme, and the result is always at the extreme end. Name what the face is doing',
'  instead, and use these tags for expression, gaze and body language and no others:',
MANGA_EXPRESSION_TAGS,
'  Everything else - the place, the clothes, the action, the objects - is ordinary Danbooru',
'  vocabulary with no list.',
'',
// 指針10章。カメラ目線は既定なので明示的に外す
'- Without a gaze direction the model produces one person, chest to knee, facing front, looking at',
'  the camera. A manga panel is rarely any of those. State where the eyes go.',
'',
'- Write what the picture has to show, then stop. With too few tags the model fills the gaps on its',
'  own. With too many each tag gets weaker, including the ones that set the distance.',
'',
'- Do not invent character names or series names that the description does not mention.',
'',
'- Never output "comic", "panel", "border", "speech bubble", "text" or "4koma". The editor draws',
'  the frames and the balloons. Do not write anything about the frame cutting a character off.',
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
// これらのタグは再生成のプロンプトとして使われる。感情ラベルで書くと次の絵が振り切れる。
// 顔の部位で書くほうが記述としても正確
'- For the face, name what it is doing rather than the emotion. Do not write "angry", "sad",',
'  "happy", "surprised" or "smiling": these tags are reused as a generation prompt, and each of',
'  them produces the extreme version of that emotion. Naming the parts is also the more accurate',
'  description. Use these tags for expression, gaze and body language and no others:',
MANGA_EXPRESSION_TAGS,
'  Everything else in the image is ordinary Danbooru vocabulary with no list.',
'',
'- Do not guess character names or series names.',
'',
'- Write what is in the image, then stop. Adding tags that are not there moves the picture away',
'  from the one you were given.',
'',
'- Never output "comic", "panel", "border", "speech bubble", "text" or "4koma", even if the image',
'  contains them. The editor draws the frames and the balloons.',
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
// 画風タグと見切れのネガティブはコマ一括経路と同じものを通す
promptApplyTagsToLayer(layer,tags,true);
createToast(i18next.t('llmImage2PromptTitle'),tags);
refreshPromptPanel(layer);
}).catch(function(error){
createToastError(i18next.t('llmImage2PromptTitle'),error.message,1000*10);
llmLogger.error('llmImage2Prompt failed: '+error.message);
}).finally(function(){
removeSpinner(spinnerId);
});
}
