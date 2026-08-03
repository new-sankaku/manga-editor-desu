// セリフの推敲・口調変更・文字数調整・翻訳
const LLM_DIALOGUE_LANGUAGES=[
{code:'ja',label:'日本語'},
{code:'en',label:'English'},
{code:'ko',label:'한국어'},
{code:'zh',label:'中文'},
{code:'fr',label:'Français'},
{code:'de',label:'Deutsch'},
{code:'es',label:'Español'},
{code:'ru',label:'Русский'}
];

// 文面は llm_doc/manga-page-guideline.md の11章がそのまま元
const LLM_DIALOGUE_BASE_RULES=[
'このセリフは漫画の吹き出しに入ります。',
'',
'■ 吹き出しに入る言葉',
'',
'・声に出して言える言葉にする。吹き出しに入るのは誰かが口に出したことで、地の文ではありません',
'・1つの吹き出しは短いほうが読まれます。主語 → 目的語 → 動作の順に置くと読みやすい',
'',
// 指針11章。絵が言っていることをセリフで繰り返さない
'・絵が既に見せていることを言い直すと、その分の文字が読者に何も渡しません。',
'  どこにいるか、何をしているかはコマが見せています',
'',
// 指針11章。モノローグは情景描写ではなく心理の変化
'・口に出さず心の中で言う言葉なら、その人物の考えが何から何へ変わったかを書くと効きます。',
'  情景の描写を入れると、絵と重なります',
'',
'【必ず守ること】',
'',
'・吹き出しに要る改行は残す。理由なく増やさない',
'',
'【出力】',
'・書き直した1行だけ。説明・引用符・ラベル・コードフェンスを入れない'
].join('\n');

function estimateTextCapacity(textObject){
var fontSize=textObject.fontSize||14;
var lineHeight=textObject.lineHeight||1.16;
var width=(textObject.width||0)*(textObject.scaleX||1);
var height=(textObject.height||0)*(textObject.scaleY||1);
if(fontSize<=0||width<=0||height<=0)return 0;
var vertical=isVerticalText(textObject);
var perLine=Math.floor((vertical?height:width)/fontSize);
var lines=Math.floor((vertical?width:height)/(fontSize*lineHeight));
if(perLine<1||lines<1)return 0;
return perLine*lines;
}

function buildDialogueMessages(provider,operation,sourceText,option){
var instruction;
if(operation==='polish'){
instruction='このセリフを、漫画のセリフとして自然に読めるように推敲してください。意味・話し手・言語は変えないでください。';
}else if(operation==='tone'){
instruction='このセリフを次の口調・話し方で書き直してください。意味と言語は変えないでください。\n口調: '+option;
}else if(operation==='fit'){
instruction='このセリフを'+option+'文字以内に収まるように書き直してください。意味・話し手・言語は変えないでください。情報を落とすより先に、言い回しを短くしてください。';
}else if(operation==='translate'){
instruction='このセリフを'+option+'に翻訳してください。逐語訳ではなく、漫画の吹き出しに入る自然な話し言葉にしてください。';
}else{
throw new Error('Unknown dialogue operation: '+operation);
}
var userPrompt=instruction+'\n\nセリフ:\n'+sourceText;
return provider.buildTextMessages(LLM_DIALOGUE_BASE_RULES,userPrompt);
}

function normalizeDialogueOutput(text){
var body=text.replace(/```[a-z]*\n?/gi,'').replace(/```/g,'').trim();
body=body.replace(/^["'「『]/,'').replace(/["'」』]$/,'');
return body.trim();
}

async function llmDialogue(operation,sourceText,option){
var target=requireLLMProvider(AI_ROLES.Text2Text);
var messages=buildDialogueMessages(target.provider,operation,sourceText,option);
var raw=await target.queue.add(function(){
return target.provider.chat(messages,{temperature:0.7});
});
var result=normalizeDialogueOutput(raw);
if(!result){
throw new Error(target.provider.name+': '+i18next.t('llmErrorEmptyResponse'));
}
return result;
}

function applyDialogueText(textObject,value){
textObject.set('text',value);
if(typeof textObject.initDimensions==='function'){
textObject.initDimensions();
}
textObject.setCoords();
canvas.renderAll();
commitHistory();
updateLayerPanel();
}
