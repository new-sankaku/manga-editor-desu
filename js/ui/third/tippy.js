// Tooltip initialization using Tippy.js
var tippyInstances=[];

function removeTooltips(){
tippyInstances.forEach(function(instance){
instance.destroy();
});
tippyInstances=[];
}

var tippyTheme="light";

function addTooltipByElement(element,translationKey){
if(!element){
uiLogger.warn("Element not found for tooltip:"+translationKey);
return;
}
var tooltipText=getText(translationKey);
var instance=tippy(element,{
content:tooltipText,
arrow:true,
theme:tippyTheme,
delay:[800,0],
duration:0,
placement:'bottom',
});
tippyInstances.push(instance);
}

function addTooltip(elementId,translationKey){
var element=$(elementId);
if(!element){
uiLogger.warn("Element with ID "+elementId+" not found");
return;
}
var tooltipText=getText(translationKey);
var instance=tippy(element,{
content:tooltipText,
arrow:true,
theme:tippyTheme,
duration:1000,
});
tippyInstances.push(instance);
}

var sidebarTooltipMap=[
{id:'intro_svg-container-template',key:'tipTemplate'},
{id:'intro_page-manager-area',key:'tipPageManager'},
{id:'intro_auto-generate-area',key:'tipAutoGenerate'},
{id:'intro_prompt-manager-area',key:'tipPrompt'},
{id:'intro_speech-bubble-area1',key:'tipTemplateBubble'},
{id:'intro_speech-bubble-area2',key:'tipFreeBubble'},
{id:'intro_text-area',key:'tipText'},
{id:'intro_text-area2',key:'tipImageText'},
{id:'intro_tool-area',key:'tipPen'},
{id:'intro_manga-tone-area',key:'tipTone'},
{id:'intro_manga-effect-area',key:'tipEffect'},
{id:'intro_control-area',key:'tipControl'},
{id:'intro_shape-area',key:'tipShape'},
];

function addSidebarTooltips(){
sidebarTooltipMap.forEach(function(item){
var icon=$(item.id);
if(!icon)return;
var wrapper=icon.closest('.icon-wrapper');
if(!wrapper)return;
var tooltipText=getText(item.key);
var instance=tippy(wrapper,{
content:tooltipText,
arrow:true,
theme:tippyTheme,
delay:[500,0],
duration:0,
placement:'right',
});
tippyInstances.push(instance);
});
}

// i18nextのupdateContent()はinnerHTML代入のみで属性翻訳に対応していない。
// 属性に説明文を持たせるとアイコンのリガチャが壊れるため、data-tip属性を
// 走査してtippy側で持つ。要素を増やすたびに登録を書き足す必要をなくす
function addTooltipsByAttribute(){
document.querySelectorAll('[data-tip]').forEach(function(element){
addTooltipByElement(element,element.dataset.tip);
});
}

function setLanguage(language){
i18next.changeLanguage(language,function(){
uiLogger.debug("setLanguage start");
removeTooltips();
addTooltip('zoomIn','zoomIn');
addTooltip('zoomOut','zoomOut');
addTooltip('zoomFit','zoomFit');
addTooltip('clearMode','clearMode');
addTooltip('undo','undo');
addTooltip('redo','redo');
addSidebarTooltips();
addTooltipsByAttribute();
});
}
