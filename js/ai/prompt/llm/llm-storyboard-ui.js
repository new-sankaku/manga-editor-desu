// ネームからコマ一括生成のフローティングウインドウ
var llmStoryboardResult=null;

// コマの役割の表示名。未知・未指定は空にする（勝手に近い役割へ寄せない）
function getPanelRoleLabel(role){
if(!role)return'';
return i18next.t('panelRole_'+role);
}

function closeLLMStoryboardWindow(){
var existing=document.querySelector('.llm-storyboard-window');
if(existing)existing.remove();
llmStoryboardResult=null;
}

function openLLMStoryboardWindow(){
if(hasNotRole(AI_ROLES.Text2Prompt)){
createToastError(i18next.t('llmStoryboardTitle'),i18next.t('llmErrorNoProvider'));
return;
}
closeLLMStoryboardWindow();
var win=document.createElement('div');
win.className='floating-windowPromptClass llm-storyboard-window';
win.style.cursor='move';
win.innerHTML=`
<h4>${i18next.t('llmStoryboardTitle')}</h4>
<div class="llm-prompt-field">
<label for="llmStoryboardInput">${i18next.t('llmStoryboardInputLabel')}</label>
<textarea id="llmStoryboardInput" rows="4" placeholder="${i18next.t('llmStoryboardPlaceholder')}"></textarea>
</div>
<div class="llm-prompt-actions">
<label class="llm-storyboard-check"><input type="checkbox" id="llmStoryboardRtl" checked> ${i18next.t('llmStoryboardRightToLeft')}</label>
</div>
<div class="llm-prompt-actions">
<button id="llmStoryboardGenerate">${i18next.t('llmText2PromptGenerate')}</button>
<span id="llmStoryboardStatus" class="llm-prompt-status"></span>
</div>
<div id="llmStoryboardWarning" class="llm-story-note llm-rhythm-warning" style="display:none;"></div>
<div id="llmStoryboardPreview" class="llm-storyboard-preview"></div>
<div class="llm-prompt-actions">
<button id="llmStoryboardReplace" disabled>${i18next.t('llmText2PromptReplace')}</button>
<button id="llmStoryboardAppend" disabled>${i18next.t('llmText2PromptAppend')}</button>
<button id="llmStoryboardClose">${i18next.t('llmText2PromptClose')}</button>
</div>
`;
document.body.appendChild(win);
makeDraggable(win);

var generateButton=$('llmStoryboardGenerate');
var statusEl=$('llmStoryboardStatus');

generateButton.addEventListener('click',async function(){
var synopsis=$('llmStoryboardInput').value.trim();
if(!synopsis){
statusEl.textContent=i18next.t('llmStoryboardNeedInput');
return;
}
generateButton.disabled=true;
statusEl.textContent=i18next.t('llmText2PromptGenerating');
try{
llmStoryboardResult=await llmStoryboard(synopsis,$('llmStoryboardRtl').checked);
renderLLMStoryboardPreview();
statusEl.textContent='';
}catch(error){
statusEl.textContent='';
createToastError(i18next.t('llmStoryboardTitle'),error.message,1000*10);
llmLogger.error('llmStoryboard failed: '+error.message);
}finally{
generateButton.disabled=false;
}
});

$('llmStoryboardReplace').addEventListener('click',function(){
applyLLMStoryboard(false);
});
$('llmStoryboardAppend').addEventListener('click',function(){
applyLLMStoryboard(true);
});
$('llmStoryboardClose').addEventListener('click',function(){
closeLLMStoryboardWindow();
});
}

function renderLLMStoryboardPreview(){
var container=$('llmStoryboardPreview');
container.textContent='';
if(!llmStoryboardResult)return;
var warningEl=$('llmStoryboardWarning');
warningEl.textContent=llmStoryboardResult.warning?i18next.t('storyRhythmWarning'):'';
warningEl.style.display=llmStoryboardResult.warning?'block':'none';
llmStoryboardResult.entries.forEach(function(entry,i){
var row=document.createElement('div');
row.className='llm-storyboard-row';
var label=document.createElement('label');
label.className='llm-storyboard-index';
label.textContent=i18next.t('llmStoryboardPanel')+' '+entry.index;
// どのコマが引き・情景なのかを見せる。ページの緩急をここで確認して作り直せる
var role=document.createElement('span');
role.className='llm-panel-role';
role.textContent=getPanelRoleLabel(entry.role);
label.appendChild(role);
var area=document.createElement('textarea');
area.rows=2;
area.value=entry.prompt;
// 役割から決まる構図タグを読み取り専用で併記する。何が足されるか隠さない
var note=document.createElement('div');
note.className='llm-panel-composition';
note.textContent=buildPanelCompositionNote(entry.panel,entry.role,entry.prompt);
area.addEventListener('input',function(){
llmStoryboardResult.entries[i].prompt=this.value;
note.textContent=buildPanelCompositionNote(entry.panel,entry.role,this.value);
});
area.addEventListener('focus',function(){
canvas.setActiveObject(entry.panel);
canvas.renderAll();
});
row.appendChild(label);
row.appendChild(area);
row.appendChild(note);
container.appendChild(row);
});
$('llmStoryboardReplace').disabled=false;
$('llmStoryboardAppend').disabled=false;
}

function applyLLMStoryboard(append){
if(!llmStoryboardResult){
$('llmStoryboardStatus').textContent=i18next.t('llmText2PromptNeedResult');
return;
}
var applied=0;
llmStoryboardResult.entries.forEach(function(entry){
if(promptApplyToPanel(entry.panel,entry.prompt,append,entry.role)){
applied++;
}
});
refreshPromptPanel(canvas.getActiveObject());
updateLayerPanel();
// カスタム属性への直接代入はset()を通らず自動コミット網に検知されない
saveStateByManual();
createToast(i18next.t('llmStoryboardTitle'),i18next.t('llmStoryboardApplied')+' '+applied);
closeLLMStoryboardWindow();
}
