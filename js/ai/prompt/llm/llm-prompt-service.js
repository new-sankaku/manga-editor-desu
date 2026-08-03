// LLMによるプロンプト生成: 文章→タグ（Text2Prompt）と画像→タグ（Image2Prompt_LLM）
const LLM_TEXT2PROMPT_SYSTEM=[
'場面の説明を、漫画のコマ1つ分の画像生成タグ（Danbooru形式）に変換してください。',
'',
'──────────────────────────────',
'',
'■ 何を書くか',
'',
'説明から読み取れるものを書きます。人数、外見、服、表情、ポーズ、アングル、背景、光。',
'読み取れないものは足しません。',
'',
'■ 距離の決め方',
'',
// 指針16章。フレーミングタグが効かないことと、その代わりに何を書くか
'"full body" "wide shot" "upper body" "close-up" は出来上がった絵に付いたラベルで、',
'書いてもその距離にはなりません。距離はどれを名指しするかで決まります。',
'    頭から靴まで … 靴、脚、立っている床を名指しする',
'    腰から上     … 腰から上の服、手。靴も床も名指ししない',
'    顔           … 目、口、髪、表情。肩から下は名指ししない',
'    その場所     … その場所にあってフレームに収まらない大きさのもの。人は出さないか遠くに置く',
'欲しいフレームの外にあるものを名指しすると、それを含めるために視点が引きます。',
'',
'■ 顔と体',
'',
// 指針13章。素の感情ラベルは使わせない
'"angry" "sad" "happy" "surprised" "smiling" は、かすかな状態から極端な状態までを',
'ひとつの語で覆っているため、書くと極端な側が出ます。',
'感情の名前ではなく、顔が何をしているかを名指ししてください。',
'',
// 指針10章。カメラ目線は既定なので明示的に外す
'指定しないとモデルは「1人・胸から膝・正面・カメラ目線」を出します。',
'視線の方向を書くとそこから外れます。',
'',
'【必ず守ること】',
'',
'・表情・視線・仕草は、次のタグだけを使う',
MANGA_EXPRESSION_TAGS,
'  それ以外（場所・服・動作・物）は通常のDanbooru語彙から自由に選ぶ',
'',
'・説明に出てこないキャラ名・作品名を作らない',
'',
'・"comic" "panel" "border" "speech bubble" "text" "4koma" は出さない。',
'  枠と吹き出しはエディタが描く。フレームが人物を切ることについても書かない',
'',
'・タグの数は、その絵が見せる必要のあるものを書いて止める。',
'  少なすぎるとモデルが勝手に埋め、多すぎると1つ1つが弱くなって距離も決まらなくなる',
'',
'【出力】',
'・小文字のタグをカンマ区切りで並べたものだけ。文章・説明・見出し・コードフェンスを入れない'
].join('\n');

const LLM_IMAGE2PROMPT_SYSTEM=[
'与えられた画像を、Danbooru形式のタグで書き出してください。',
'',
'──────────────────────────────',
'',
'■ 何を書くか',
'',
'実際に見えているものだけ。人数、髪、目、服、表情、ポーズ、構図、背景、光、画風。',
'そこに在るはずだと思ったものは書きません。',
'',
'■ 顔',
'',
// これらのタグは再生成のプロンプトとして使われる。感情ラベルで書くと次の絵が振り切れる。
// 顔の部位で書くほうが記述としても正確
'感情の名前ではなく、顔が何をしているかを名指しします。',
'"angry" "sad" "happy" "surprised" "smiling" は書かないでください。',
'このタグは画像生成のプロンプトとして再利用され、これらの語はその感情の極端な側を出します。',
'部位で書くほうが、記述としても正確です。',
'',
'【必ず守ること】',
'',
'・表情・視線・仕草は、次のタグだけを使う',
MANGA_EXPRESSION_TAGS,
'  それ以外（場所・服・動作・物）は通常のDanbooru語彙から自由に選ぶ',
'',
'・キャラ名・作品名を推測しない',
'',
'・"comic" "panel" "border" "speech bubble" "text" "4koma" は、画像に写っていても出さない。',
'  枠と吹き出しはエディタが描く',
'',
'・画像に無いタグを足すと、元の絵から離れる',
'',
'【出力】',
'・小文字のタグをカンマ区切りで並べたものだけ。文章・説明・見出し・コードフェンスを入れない'
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
var userPrompt='場面の説明:\n'+description;
if(existingPrompt&&existingPrompt.trim()){
userPrompt+='\n\n既にプロンプトへ入っているタグ（繰り返さないでください）:\n'+existingPrompt;
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
'この画像をタグにしてください。',
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
