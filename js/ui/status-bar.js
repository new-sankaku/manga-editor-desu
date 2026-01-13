var statusBarLogger=new SimpleLogger('statusBar',LogLevel.DEBUG);
var currentToolName='select';
var previousToolName=null;
var statusBarShiftHintShown=false;

var toolNameMap={
'select': 'statusbar_select',
'freehand': 'statusbar_freehand',
'point': 'statusbar_point',
'knife': 'statusbar_knife',
'Pencil': 'statusbar_pencil',
'OutlinePen': 'statusbar_outlinepen',
'Circle': 'statusbar_circle',
'Square': 'statusbar_square',
'Texture': 'statusbar_texture',
'Crayon': 'statusbar_crayon',
'Ink': 'statusbar_ink',
'Marker': 'statusbar_marker',
'Eraser': 'statusbar_eraser',
'Hline': 'statusbar_hline',
'Vline': 'statusbar_vline',
'Mosaic': 'statusbar_mosaic',
'text': 'statusbar_text',
'speech-bubble': 'statusbar_bubble',
'panel': 'statusbar_panel',
'shape': 'statusbar_shape',
'tone': 'statusbar_tone',
'effect': 'statusbar_effect',
'rough': 'statusbar_rough'
};

function initStatusBar(){
var statusBar=$('status-bar');
if(!statusBar)return;
canvas.on('mouse:move',function(opt){
updateStatusBarCoords(opt.e);
});
updateStatusBarTool('select');
statusBarLogger.debug('StatusBar initialized');
}

function updateStatusBarTool(toolKey){
if(currentToolName!==toolKey){
previousToolName=currentToolName;
}
currentToolName=toolKey;
var toolDisplay=$('status-tool-name');
if(!toolDisplay)return;
var i18nKey=toolNameMap[toolKey]||'statusbar_select';
toolDisplay.setAttribute('data-i18n',i18nKey);
toolDisplay.textContent=i18next.t(i18nKey);
statusBarLogger.trace('Tool changed to:',toolKey);
}

function updateStatusBarCoords(e){
var coordDisplay=$('status-coords');
if(!coordDisplay||!e)return;
var pointer=canvas.getPointer(e);
var x=Math.round(pointer.x);
var y=Math.round(pointer.y);
coordDisplay.textContent='X:'+x+' Y:'+y;
}

function updateStatusBarHint(hintKey){
var hintDisplay=$('status-hint');
if(!hintDisplay)return;
hintDisplay.setAttribute('data-i18n',hintKey);
hintDisplay.textContent=i18next.t(hintKey);
}

function showShiftHint(){
if(statusBarShiftHintShown)return;
var hintDisplay=$('status-hint');
if(!hintDisplay)return;
hintDisplay.setAttribute('data-i18n','statusbar_shift_hint');
hintDisplay.textContent=i18next.t('statusbar_shift_hint');
}

function switchToPreviousTool(){
if(!previousToolName||previousToolName===currentToolName)return;
switchToolByKey(previousToolName);
}

function switchToolByKey(toolKey){
statusBarLogger.debug('switchToolByKey:',toolKey);
switch(toolKey){
case 'pen':
toggleVisibility('tool-area');
break;
case 'eraser':
toggleVisibility('tool-area');
setTimeout(function(){
if(typeof switchPencilType==='function'){
switchPencilType(MODE_PEN_ERASER);
}
},50);
break;
case 'shape':
toggleVisibility('shape-area');
break;
case 'text':
toggleVisibility('text-area');
break;
case 'bubble':
toggleVisibility('speech-bubble-area1');
break;
case 'panel':
toggleVisibility('custom-panel-manager-area');
break;
case 'select':
operationModeClear();
break;
}
}

document.addEventListener('DOMContentLoaded',function(){
setTimeout(initStatusBar,500);
});
