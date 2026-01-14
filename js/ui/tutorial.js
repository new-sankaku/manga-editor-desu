var tutorialLogger=new SimpleLogger('tutorial',LogLevel.DEBUG);
var TutorialManager={
STORAGE_KEY:'manga_tutorial_state',
LANG_STORAGE_KEY:'tutorial_lang_selected',
state:null,
activeHint:null,
languages:[
{code:'ja',name:'日本語',flag:'jp'},
{code:'en',name:'English',flag:'us'},
{code:'ko',name:'한국어',flag:'kr'},
{code:'zh',name:'中文',flag:'cn'},
{code:'fr',name:'Français',flag:'fr'},
{code:'de',name:'Deutsch',flag:'de'},
{code:'es',name:'Español',flag:'es'},
{code:'pt',name:'Português',flag:'pt'},
{code:'ru',name:'Русский',flag:'ru'},
{code:'th',name:'ไทย',flag:'th'}
],
init:function(){
this.loadState();
this.setupEventListeners();
var langSelected=localStorage.getItem(this.LANG_STORAGE_KEY);
if(!langSelected){
this.showLanguageSelection();
}else if(!this.state.quickStartCompleted){
this.showQuickStartPrompt();
}
},
loadState:function(){
try{
var saved=localStorage.getItem(this.STORAGE_KEY);
this.state=saved?JSON.parse(saved):{
quickStartCompleted:false,
hintsShown:{},
comfyUIGuideShown:false
};
}catch(e){
this.state={quickStartCompleted:false,hintsShown:{},comfyUIGuideShown:false};
}
},
saveState:function(){
try{
localStorage.setItem(this.STORAGE_KEY,JSON.stringify(this.state));
}catch(e){
tutorialLogger.error('Failed to save tutorial state');
}
},
resetState:function(){
this.state={quickStartCompleted:false,hintsShown:{},comfyUIGuideShown:false};
localStorage.removeItem(this.LANG_STORAGE_KEY);
this.saveState();
},
showLanguageSelection:function(){
var self=this;
var overlay=document.createElement('div');
overlay.className='tutorial-overlay';
var langButtons='';
for(var i=0;i<this.languages.length;i++){
var lang=this.languages[i];
langButtons+='<button class="tutorial-lang-btn" data-lang="'+lang.code+'"><span class="flag-icon flag-icon-'+lang.flag+'"></span>'+lang.name+'</button>';
}
overlay.innerHTML='<div class="tutorial-prompt">'+
'<div class="tutorial-prompt-title">Select Language / 言語選択</div>'+
'<div class="tutorial-prompt-body">Choose your preferred language</div>'+
'<div class="tutorial-lang-grid">'+langButtons+'</div>'+
'</div>';
document.body.appendChild(overlay);
overlay.querySelectorAll('.tutorial-lang-btn').forEach(function(btn){
btn.addEventListener('click',function(){
var langCode=this.getAttribute('data-lang');
self.selectLanguage(langCode,overlay);
});
});
},
selectLanguage:function(langCode,overlay){
var self=this;
localStorage.setItem(this.LANG_STORAGE_KEY,'true');
if(typeof changeLanguage==='function'){
changeLanguage(langCode);
}else if(typeof i18next!=='undefined'){
i18next.changeLanguage(langCode);
}
overlay.remove();
setTimeout(function(){
if(!self.state.quickStartCompleted){
self.showQuickStartPrompt();
}
},300);
},
showQuickStartPrompt:function(){
var self=this;
var overlay=document.createElement('div');
overlay.className='tutorial-overlay';
overlay.innerHTML='<div class="tutorial-prompt">'+
'<div class="tutorial-prompt-title">'+getText('tutorialWelcomeTitle')+'</div>'+
'<div class="tutorial-prompt-body">'+getText('tutorialWelcomeBody')+'</div>'+
'<div class="tutorial-prompt-buttons">'+
'<button class="tutorial-btn tutorial-btn-primary" id="tutorialStartBtn">'+getText('tutorialStart')+'</button>'+
'<button class="tutorial-btn tutorial-btn-secondary" id="tutorialSkipBtn">'+getText('tutorialSkip')+'</button>'+
'</div>'+
'</div>';
document.body.appendChild(overlay);
document.getElementById('tutorialStartBtn').addEventListener('click',function(){
overlay.remove();
self.startQuickStart();
});
document.getElementById('tutorialSkipBtn').addEventListener('click',function(){
overlay.remove();
self.state.quickStartCompleted=true;
self.saveState();
});
},
startQuickStart:function(){
var self=this;
var steps=[
{element:'#intro_svg-container-vertical',title:getText('tutorialStep1Title'),body:getText('tutorialStep1Body'),position:'right'},
{element:'#canvas-area',title:getText('tutorialStep2Title'),body:getText('tutorialStep2Body'),position:'left'},
{element:'#intro_speech-bubble-area1',title:getText('tutorialStep3Title'),body:getText('tutorialStep3Body'),position:'right'},
{element:'#intro_text-area',title:getText('tutorialStep4Title'),body:getText('tutorialStep4Body'),position:'right'},
{element:'#canvas-area',title:getText('tutorialStep5Title'),body:getText('tutorialStep5Body'),position:'left'}
];
this.runSteps(steps,0,function(){
self.state.quickStartCompleted=true;
self.saveState();
createToast(getText('tutorialCompleteTitle'),getText('tutorialCompleteBody'),3000);
});
},
runSteps:function(steps,index,onComplete){
var self=this;
if(index>=steps.length){
if(onComplete)onComplete();
return;
}
var step=steps[index];
this.showStepHighlight(step,index+1,steps.length,function(){
self.runSteps(steps,index+1,onComplete);
});
},
showStepHighlight:function(step,current,total,onNext){
var self=this;
this.removeActiveHint();
var targetEl=document.querySelector(step.element);
if(!targetEl){
tutorialLogger.warn('Tutorial target not found:',step.element);
onNext();
return;
}
var rect=targetEl.getBoundingClientRect();
var overlay=document.createElement('div');
overlay.className='tutorial-step-overlay';
var highlight=document.createElement('div');
highlight.className='tutorial-highlight';
highlight.style.top=(rect.top-6)+'px';
highlight.style.left=(rect.left-6)+'px';
highlight.style.width=(rect.width+12)+'px';
highlight.style.height=(rect.height+12)+'px';
var tooltip=document.createElement('div');
tooltip.className='tutorial-tooltip tutorial-tooltip-'+step.position;
var tooltipLeft,tooltipTop;
if(step.position==='right'){
tooltipLeft=rect.right+24;
tooltipTop=rect.top;
}else if(step.position==='left'){
tooltipLeft=rect.left-370;
tooltipTop=rect.top;
}else if(step.position==='bottom'){
tooltipLeft=rect.left;
tooltipTop=rect.bottom+24;
}else{
tooltipLeft=rect.left;
tooltipTop=rect.top-180;
}
tooltip.style.left=Math.max(10,tooltipLeft)+'px';
tooltip.style.top=Math.max(10,tooltipTop)+'px';
tooltip.innerHTML='<div class="tutorial-tooltip-header">'+
'<span class="tutorial-step-indicator">'+current+'/'+total+'</span>'+
'<span class="tutorial-tooltip-title">'+step.title+'</span>'+
'</div>'+
'<div class="tutorial-tooltip-body">'+step.body+'</div>'+
'<div class="tutorial-tooltip-footer">'+
'<button class="tutorial-btn tutorial-btn-secondary tutorial-btn-sm" id="tutorialExitBtn">'+getText('tutorialExit')+'</button>'+
'<button class="tutorial-btn tutorial-btn-primary tutorial-btn-sm" id="tutorialNextBtn">'+(current<total?getText('tutorialNext'):getText('tutorialFinish'))+'</button>'+
'</div>';
overlay.appendChild(highlight);
overlay.appendChild(tooltip);
document.body.appendChild(overlay);
this.activeHint=overlay;
document.getElementById('tutorialNextBtn').addEventListener('click',function(){
self.removeActiveHint();
onNext();
});
document.getElementById('tutorialExitBtn').addEventListener('click',function(){
self.removeActiveHint();
self.state.quickStartCompleted=true;
self.saveState();
});
},
removeActiveHint:function(){
if(this.activeHint){
this.activeHint.remove();
this.activeHint=null;
}
},
showContextHint:function(hintId,element,title,body,position){
if(this.state.hintsShown[hintId])return;
var self=this;
var targetEl=typeof element==='string'?document.querySelector(element):element;
if(!targetEl)return;
this.removeActiveHint();
var rect=targetEl.getBoundingClientRect();
var overlay=document.createElement('div');
overlay.className='tutorial-context-overlay';
var tooltip=document.createElement('div');
tooltip.className='tutorial-tooltip tutorial-tooltip-context tutorial-tooltip-'+(position||'bottom');
var tooltipLeft,tooltipTop;
position=position||'bottom';
if(position==='right'){
tooltipLeft=rect.right+12;
tooltipTop=rect.top;
}else if(position==='left'){
tooltipLeft=rect.left-320;
tooltipTop=rect.top;
}else if(position==='top'){
tooltipLeft=rect.left;
tooltipTop=rect.top-150;
}else{
tooltipLeft=rect.left;
tooltipTop=rect.bottom+12;
}
tooltip.style.left=Math.max(10,tooltipLeft)+'px';
tooltip.style.top=Math.max(10,tooltipTop)+'px';
tooltip.innerHTML='<div class="tutorial-tooltip-header">'+
'<span class="tutorial-tooltip-title">'+title+'</span>'+
'<button class="tutorial-tooltip-close" id="tutorialCloseHint">&times;</button>'+
'</div>'+
'<div class="tutorial-tooltip-body">'+body+'</div>'+
'<div class="tutorial-tooltip-footer">'+
'<label class="tutorial-dont-show"><input type="checkbox" id="tutorialDontShow"> '+getText('tutorialDontShowAgain')+'</label>'+
'<button class="tutorial-btn tutorial-btn-primary tutorial-btn-sm" id="tutorialGotIt">'+getText('tutorialGotIt')+'</button>'+
'</div>';
overlay.appendChild(tooltip);
document.body.appendChild(overlay);
this.activeHint=overlay;
var closeHint=function(){
var dontShow=document.getElementById('tutorialDontShow');
if(dontShow&&dontShow.checked){
self.state.hintsShown[hintId]=true;
self.saveState();
}
self.removeActiveHint();
};
document.getElementById('tutorialCloseHint').addEventListener('click',closeHint);
document.getElementById('tutorialGotIt').addEventListener('click',function(){
self.state.hintsShown[hintId]=true;
self.saveState();
self.removeActiveHint();
});
overlay.addEventListener('click',function(e){
if(e.target===overlay)closeHint();
});
},
markHintShown:function(hintId){
this.state.hintsShown[hintId]=true;
this.saveState();
},
setupEventListeners:function(){
var self=this;
document.addEventListener('click',function(e){
if(e.target.id==='Intro_Tutorial'){
e.preventDefault();
self.startQuickStart();
}
});
}
};
var ComfyUIGuide={
STORAGE_KEY:'comfyui_guide_state',
state:null,
init:function(){
this.loadState();
},
loadState:function(){
try{
var saved=localStorage.getItem(this.STORAGE_KEY);
this.state=saved?JSON.parse(saved):{
setupGuideShown:false,
testGenerateHintShown:false,
nodeErrorHintShown:false,
modelErrorHintShown:false
};
}catch(e){
this.state={setupGuideShown:false,testGenerateHintShown:false,nodeErrorHintShown:false,modelErrorHintShown:false};
}
},
saveState:function(){
try{
localStorage.setItem(this.STORAGE_KEY,JSON.stringify(this.state));
}catch(e){
tutorialLogger.error('Failed to save ComfyUI guide state');
}
},
resetState:function(){
this.state={setupGuideShown:false,testGenerateHintShown:false,nodeErrorHintShown:false,modelErrorHintShown:false};
this.saveState();
},
showSetupGuide:function(isOnline,forceShow){
if(this.state.setupGuideShown&&!forceShow)return;
var self=this;
var container=document.querySelector('.comfui-right-sidebar');
if(!container)return;
var existingGuide=container.querySelector('.comfyui-setup-guide');
if(existingGuide)existingGuide.remove();
var guide=document.createElement('div');
guide.className='comfyui-setup-guide'+(isOnline?'':' warning');
if(isOnline){
guide.innerHTML='<div class="guide-header">'+
'<span class="guide-icon" style="font-size:20px;">&#9989;</span>'+
'<span class="guide-title">'+getText('comfyGuideOnlineTitle')+'</span>'+
'<button class="guide-close">&times;</button>'+
'</div>'+
'<div class="guide-content">'+
'<div class="guide-step"><span class="step-num">1</span><span>'+getText('comfyGuideOnlineStep1')+'</span></div>'+
'<div class="guide-step"><span class="step-num">2</span><span>'+getText('comfyGuideOnlineStep2')+'</span></div>'+
'<div class="guide-step"><span class="step-num">3</span><span>'+getText('comfyGuideOnlineStep3')+'</span></div>'+
'</div>'+
'<div class="guide-footer">'+
'<label class="tutorial-dont-show"><input type="checkbox" id="comfyGuideDontShow"> '+getText('tutorialDontShowAgain')+'</label>'+
'<button class="tutorial-btn tutorial-btn-primary tutorial-btn-sm guide-got-it">'+getText('tutorialGotIt')+'</button>'+
'</div>';
}else{
guide.innerHTML='<div class="guide-header warning">'+
'<span class="guide-icon" style="font-size:20px;">&#9888;</span>'+
'<span class="guide-title">'+getText('comfyGuideOfflineTitle')+'</span>'+
'<button class="guide-close">&times;</button>'+
'</div>'+
'<div class="guide-content">'+
'<div class="guide-step"><span class="step-num warn">1</span><span>'+getText('comfyGuideOfflineStep1')+'</span></div>'+
'<div class="guide-step"><span class="step-num warn">2</span><span>'+getText('comfyGuideOfflineStep2')+'</span></div>'+
'<div class="guide-step highlight warn">'+getText('comfyGuideOfflineStep3')+'</div>'+
'</div>'+
'<div class="guide-footer">'+
'<label class="tutorial-dont-show"><input type="checkbox" id="comfyGuideDontShow"> '+getText('tutorialDontShowAgain')+'</label>'+
'<button class="tutorial-btn tutorial-btn-primary tutorial-btn-sm guide-got-it">'+getText('tutorialGotIt')+'</button>'+
'</div>';
}
container.insertBefore(guide,container.firstChild);
guide.querySelector('.guide-close').addEventListener('click',function(){
var dontShow=document.getElementById('comfyGuideDontShow');
if(dontShow&&dontShow.checked){
self.state.setupGuideShown=true;
self.saveState();
}
guide.remove();
});
guide.querySelector('.guide-got-it').addEventListener('click',function(){
var dontShow=document.getElementById('comfyGuideDontShow');
if(dontShow&&dontShow.checked){
self.state.setupGuideShown=true;
self.saveState();
}
guide.remove();
});
},
showNodeErrorGuide:function(missingNodes){
var container=document.querySelector('.comfui-right-sidebar');
if(!container)return;
var existingGuide=container.querySelector('.comfyui-error-guide');
if(existingGuide)existingGuide.remove();
var nodeList=missingNodes.filter(function(n){return n!=='---';}).join(', ');
var guide=document.createElement('div');
guide.className='comfyui-error-guide';
guide.innerHTML='<div class="guide-header error">'+
'<span class="guide-icon">&#10060;</span>'+
'<span class="guide-title">'+getText('comfyGuideNodeErrorTitle')+'</span>'+
'<button class="guide-close">&times;</button>'+
'</div>'+
'<div class="guide-content">'+
'<div class="guide-error-nodes">'+getText('comfyGuideNodeErrorMissing')+': <code>'+nodeList+'</code></div>'+
'<div class="guide-step"><span class="step-num">1</span>'+getText('comfyGuideNodeErrorStep1')+'</div>'+
'<div class="guide-step"><span class="step-num">2</span>'+getText('comfyGuideNodeErrorStep2')+'</div>'+
'<div class="guide-tip">'+getText('comfyGuideNodeErrorTip')+'</div>'+
'</div>';
container.insertBefore(guide,container.firstChild);
guide.querySelector('.guide-close').addEventListener('click',function(){
guide.remove();
});
},
showGenerationErrorGuide:function(errorMessage){
var container=document.querySelector('.comfui-right-sidebar');
if(!container)return;
var existingGuide=container.querySelector('.comfyui-error-guide');
if(existingGuide)existingGuide.remove();
var guide=document.createElement('div');
guide.className='comfyui-error-guide';
guide.innerHTML='<div class="guide-header error">'+
'<span class="guide-icon">&#9888;</span>'+
'<span class="guide-title">'+getText('comfyGuideGenErrorTitle')+'</span>'+
'<button class="guide-close">&times;</button>'+
'</div>'+
'<div class="guide-content">'+
'<div class="guide-step"><span class="step-num">1</span>'+getText('comfyGuideGenErrorStep1')+'</div>'+
'<div class="guide-step"><span class="step-num">2</span>'+getText('comfyGuideGenErrorStep2')+'</div>'+
'<div class="guide-example">'+getText('comfyGuideGenErrorExample')+'</div>'+
'<div class="guide-step"><span class="step-num">3</span>'+getText('comfyGuideGenErrorStep3')+'</div>'+
'</div>';
container.insertBefore(guide,container.firstChild);
guide.querySelector('.guide-close').addEventListener('click',function(){
guide.remove();
});
}
};
document.addEventListener('DOMContentLoaded',function(){
TutorialManager.init();
ComfyUIGuide.init();
});
