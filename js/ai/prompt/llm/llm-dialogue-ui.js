// セリフ支援のフローティングウインドウ
var llmDialogueTarget=null;

function closeLLMDialogueWindow(){
var existing=document.querySelector('.llm-dialogue-window');
if(existing)existing.remove();
llmDialogueTarget=null;
}

function openLLMDialogueWindow(){
if(hasNotRole(AI_ROLES.Text2Text)){
createToastError(i18next.t('llmDialogueTitle'),i18next.t('llmErrorNoProvider'));
return;
}
var activeObject=canvas.getActiveObject();
if(!isText(activeObject)){
createToastError(i18next.t('llmDialogueTitle'),i18next.t('llmDialogueNeedText'));
return;
}
closeLLMDialogueWindow();
llmDialogueTarget=activeObject;
var capacity=estimateTextCapacity(activeObject);
var languageOptions=LLM_DIALOGUE_LANGUAGES.map(function(lang){
return'<option value="'+lang.label+'">'+lang.label+'</option>';
}).join('');
var win=document.createElement('div');
win.className='floating-windowPromptClass llm-dialogue-window';
win.style.cursor='move';
win.innerHTML=`
<h4>${i18next.t('llmDialogueTitle')}</h4>
<div class="llm-prompt-field">
<label for="llmDialogueSource">${i18next.t('llmDialogueSourceLabel')}</label>
<textarea id="llmDialogueSource" rows="3"></textarea>
</div>
<div class="llm-prompt-field">
<label for="llmDialogueOperation">${i18next.t('llmDialogueOperationLabel')}</label>
<select id="llmDialogueOperation">
<option value="polish">${i18next.t('llmDialogueOpPolish')}</option>
<option value="tone">${i18next.t('llmDialogueOpTone')}</option>
<option value="fit">${i18next.t('llmDialogueOpFit')}</option>
<option value="translate">${i18next.t('llmDialogueOpTranslate')}</option>
</select>
</div>
<div class="llm-prompt-field" id="llmDialogueToneField">
<label for="llmDialogueTone">${i18next.t('llmDialogueToneLabel')}</label>
<input type="text" id="llmDialogueTone" placeholder="${i18next.t('llmDialogueTonePlaceholder')}">
</div>
<div class="llm-prompt-field" id="llmDialogueFitField">
<label for="llmDialogueFit">${i18next.t('llmDialogueFitLabel')}</label>
<input type="number" id="llmDialogueFit" min="1" max="500" value="${capacity||20}">
<span class="llm-prompt-status">${capacity?i18next.t('llmDialogueFitEstimate')+' '+capacity:i18next.t('llmDialogueFitUnknown')}</span>
</div>
<div class="llm-prompt-field" id="llmDialogueLangField">
<label for="llmDialogueLang">${i18next.t('llmDialogueLangLabel')}</label>
<select id="llmDialogueLang">${languageOptions}</select>
</div>
<div class="llm-prompt-actions">
<button id="llmDialogueGenerate">${i18next.t('llmText2PromptGenerate')}</button>
<span id="llmDialogueStatus" class="llm-prompt-status"></span>
</div>
<div class="llm-prompt-field">
<label for="llmDialogueResult">${i18next.t('llmText2PromptResultLabel')}</label>
<textarea id="llmDialogueResult" rows="3"></textarea>
<span id="llmDialogueCount" class="llm-prompt-status"></span>
</div>
<div class="llm-prompt-actions">
<button id="llmDialogueApply">${i18next.t('llmDialogueApply')}</button>
<button id="llmDialogueClose">${i18next.t('llmText2PromptClose')}</button>
</div>
`;
document.body.appendChild(win);
makeDraggable(win);
$('llmDialogueSource').value=activeObject.text||'';

var operationSelect=$('llmDialogueOperation');
operationSelect.addEventListener('change',updateLLMDialogueFields);
updateLLMDialogueFields();

$('llmDialogueResult').addEventListener('input',updateLLMDialogueCount);

var generateButton=$('llmDialogueGenerate');
var statusEl=$('llmDialogueStatus');
generateButton.addEventListener('click',async function(){
var sourceText=$('llmDialogueSource').value.trim();
if(!sourceText){
statusEl.textContent=i18next.t('llmDialogueNeedSource');
return;
}
var operation=operationSelect.value;
var option='';
if(operation==='tone'){
option=$('llmDialogueTone').value.trim();
if(!option){
statusEl.textContent=i18next.t('llmDialogueNeedTone');
return;
}
}else if(operation==='fit'){
option=parseInt($('llmDialogueFit').value,10);
if(!option||option<1){
statusEl.textContent=i18next.t('llmDialogueNeedFit');
return;
}
}else if(operation==='translate'){
option=$('llmDialogueLang').value;
}
generateButton.disabled=true;
statusEl.textContent=i18next.t('llmText2PromptGenerating');
try{
var result=await llmDialogue(operation,sourceText,option);
$('llmDialogueResult').value=result;
updateLLMDialogueCount();
statusEl.textContent='';
}catch(error){
statusEl.textContent='';
createToastError(i18next.t('llmDialogueTitle'),error.message,1000*10);
llmLogger.error('llmDialogue failed: '+error.message);
}finally{
generateButton.disabled=false;
}
});

$('llmDialogueApply').addEventListener('click',function(){
var value=$('llmDialogueResult').value;
if(!value.trim()){
$('llmDialogueStatus').textContent=i18next.t('llmText2PromptNeedResult');
return;
}
if(!llmDialogueTarget||canvas.getObjects().indexOf(llmDialogueTarget)===-1){
createToastError(i18next.t('llmDialogueTitle'),i18next.t('llmDialogueTargetLost'));
return;
}
applyDialogueText(llmDialogueTarget,value);
createToast(i18next.t('llmDialogueTitle'),value);
closeLLMDialogueWindow();
});

$('llmDialogueClose').addEventListener('click',function(){
closeLLMDialogueWindow();
});
}

function updateLLMDialogueFields(){
var operation=$('llmDialogueOperation').value;
$('llmDialogueToneField').style.display=operation==='tone'?'flex':'none';
$('llmDialogueFitField').style.display=operation==='fit'?'flex':'none';
$('llmDialogueLangField').style.display=operation==='translate'?'flex':'none';
}

function updateLLMDialogueCount(){
var value=$('llmDialogueResult').value;
$('llmDialogueCount').textContent=i18next.t('llmDialogueCharCount')+' '+Array.from(value.replace(/\n/g,'')).length;
}
