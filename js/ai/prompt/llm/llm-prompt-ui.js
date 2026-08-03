// 文章→プロンプト生成のフローティングウインドウ
function llmPromptButtonHtml(){
if(hasNotRole(AI_ROLES.Text2Prompt))return'';
return'<button id="llmPromptGen" data-i18n="llmText2PromptButton">'+i18next.t('llmText2PromptButton')+'</button>';
}

function bindLLMPromptButton(layer){
var button=$('llmPromptGen');
if(!button)return;
button.addEventListener('click',function(){
openLLMPromptWindow(layer);
});
}

function closeLLMPromptWindow(){
var existing=document.querySelector('.llm-prompt-window');
if(existing)existing.remove();
}

function openLLMPromptWindow(layer){
closeLLMPromptWindow();
var win=document.createElement('div');
win.className='floating-windowPromptClass llm-prompt-window';
win.style.cursor='move';
win.innerHTML=`
<h4>${i18next.t('llmText2PromptTitle')}</h4>
<div class="llm-prompt-field">
<label for="llmPromptInput">${i18next.t('llmText2PromptInputLabel')}</label>
<textarea id="llmPromptInput" rows="4" placeholder="${i18next.t('llmText2PromptPlaceholder')}"></textarea>
</div>
<div class="llm-prompt-actions">
<button id="llmPromptGenerate">${i18next.t('llmText2PromptGenerate')}</button>
<span id="llmPromptStatus" class="llm-prompt-status"></span>
</div>
<div class="llm-prompt-field">
<label for="llmPromptResult">${i18next.t('llmText2PromptResultLabel')}</label>
<textarea id="llmPromptResult" rows="5"></textarea>
</div>
<div class="llm-prompt-actions">
<button id="llmPromptReplace">${i18next.t('llmText2PromptReplace')}</button>
<button id="llmPromptAppend">${i18next.t('llmText2PromptAppend')}</button>
<button id="llmPromptClose">${i18next.t('llmText2PromptClose')}</button>
</div>
`;
document.body.appendChild(win);
makeDraggable(win);

var generateButton=$('llmPromptGenerate');
var statusEl=$('llmPromptStatus');

generateButton.addEventListener('click',async function(){
var description=$('llmPromptInput').value.trim();
if(!description){
statusEl.textContent=i18next.t('llmText2PromptNeedInput');
return;
}
generateButton.disabled=true;
statusEl.textContent=i18next.t('llmText2PromptGenerating');
try{
var tags=await llmText2Prompt(description,$('llmPromptResult').value);
$('llmPromptResult').value=tags;
statusEl.textContent='';
}catch(error){
statusEl.textContent='';
createToastError(i18next.t('llmText2PromptTitle'),error.message,1000*10);
llmLogger.error('llmText2Prompt failed: '+error.message);
}finally{
generateButton.disabled=false;
}
});

$('llmPromptReplace').addEventListener('click',function(){
applyLLMPromptResult(layer,false);
});
$('llmPromptAppend').addEventListener('click',function(){
applyLLMPromptResult(layer,true);
});
$('llmPromptClose').addEventListener('click',function(){
closeLLMPromptWindow();
});
}

function applyLLMPromptResult(layer,append){
var tags=$('llmPromptResult').value.trim();
if(!tags){
$('llmPromptStatus').textContent=i18next.t('llmText2PromptNeedResult');
return;
}
// 画風タグと見切れのネガティブはコマ一括経路と同じものを通す
promptApplyTagsToLayer(layer,tags,append);
refreshPromptPanel(layer);
createToast(i18next.t('llmText2PromptTitle'),layer.text2img_prompt);
closeLLMPromptWindow();
}
