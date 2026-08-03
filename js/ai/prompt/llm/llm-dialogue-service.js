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
'This line goes inside a manga speech balloon.',
'',
'Watch these points:',
'',
'- Keep it speakable. A balloon holds what someone says out loud, not narration.',
'',
'- Keep one balloon short. Order it subject, then object, then action.',
'',
// 指針11章。絵が言っていることをセリフで繰り返さない
'- Do not describe what the picture already shows. The panel shows where they are and what they',
'  are doing, so a line that states either of those is wasted.',
'',
// 指針11章。モノローグは情景描写ではなく心理の変化
'- For a line the character thinks rather than says, write the change in what they think, not a',
'  description of the scene.',
'',
'- Keep the line breaks the balloon needs. Do not add new ones without a reason.',
'',
'- Output ONLY the resulting line. No explanation, no quotation marks, no labels, no code fences.'
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
instruction='Polish this line so it reads naturally and sounds like real manga dialogue. Keep the same meaning, the same speaker and the same language.';
}else if(operation==='tone'){
instruction='Rewrite this line in the following tone or speech style, keeping the same meaning and the same language.\nTone: '+option;
}else if(operation==='fit'){
instruction='Rewrite this line so that it fits in at most '+option+' characters, keeping the same meaning, the same speaker and the same language. Shorten wording rather than dropping information when possible.';
}else if(operation==='translate'){
instruction='Translate this line into '+option+'. Keep it natural spoken dialogue for a manga balloon rather than a literal translation.';
}else{
throw new Error('Unknown dialogue operation: '+operation);
}
var userPrompt=instruction+'\n\nLine:\n'+sourceText;
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
