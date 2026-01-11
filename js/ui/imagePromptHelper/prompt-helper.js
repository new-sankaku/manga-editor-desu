let flowWindowCount=0;

function createImagePromptHelperFlotingWindow(){
flowCreateFloatingWindow('Image Prompt Helper',iphHtmlContent,'rgba(0, 38, 255, 0.7)',95,95,0);

setTimeout(()=>{
const saveButton=$('iph-save-button');
const nameInput=$('iph-name-input');
const freeInput=$('iph-free-input');
const selectedTags=$('iph-selected-tags');
const languageDropdown=$('iph-language-dropdown');
const modelDropdown=$('iph-model-dropdown');

function loadSettings() {
const settings=JSON.parse(localStorage.getItem('uiSettings')||'{}');
if (settings.language) {
languageDropdown.value=settings.language;
}
if (settings.model) {
modelDropdown.value=settings.model;
}
return settings;
}

function saveSettings() {
const settings={
language: languageDropdown.value,
model: modelDropdown.value
};
localStorage.setItem('uiSettings',JSON.stringify(settings));
}

function updateContent() {
document.querySelectorAll('[data-i18n]').forEach(element=>{
const key=element.getAttribute('data-i18n');
if (key.startsWith('[')) {
const attr=key.match(/\[(.*?)\]/)[1];
element.setAttribute(attr,getText(key.substring(key.indexOf(']')+1)));
} else {
element.textContent=getText(key);
}
});
}

function updateLanguageDropdown() {
const selectedOption=languageDropdown.options[languageDropdown.selectedIndex];
const flagCode=selectedOption.getAttribute('data-flag');
languageDropdown.style.backgroundImage=`url(https://cdnjs.cloudflare.com/ajax/libs/flag-icon-css/3.5.0/flags/4x3/${flagCode}.svg)`;
}

function initializeUI() {
initI18next(savedLanguage)
.then(()=>{
updateContent();
updateLanguageDropdown();
iphInitializeUI();
})
.catch(error=>{
uiLogger.error('Failed to initialize i18next:',error);
});
}

languageDropdown.addEventListener('change',function() {
i18next.changeLanguage(this.value)
.then(()=>{
updateContent();
updateLanguageDropdown();
saveSettings();
})
.catch(error=>{
uiLogger.error('Failed to change language:',error);
});
});

modelDropdown.addEventListener('change',function() {
saveSettings();
iphLoadJsonAndRefresh();
});

saveButton.addEventListener('click',function() {
const name=nameInput.value.trim();
const freeText=freeInput.value.trim();

const selectedTagsArray=Array.from(selectedTags.children).map(tag=>{
const clone=tag.cloneNode(true);
const removeButton=clone.querySelector('.iph-remove-tag');
if (removeButton) {
clone.removeChild(removeButton);
}
return clone.textContent.trim();
});

const selectedTagsText=selectedTagsArray.join(', ');

if (!name) {
alert(getText('alerts.nameMissing'));
return;
}

let customSet=JSON.parse(localStorage.getItem('CustomSet')||'{"Custom Set":{}}');
const key=freeText ? `${freeText}, ${selectedTagsText}` : selectedTagsText;

customSet['Custom Set']={
...customSet['Custom Set'],
[key]: {"url": `img/custom-set/${name}.webp`,"alias": name}
};

localStorage.setItem('CustomSet',JSON.stringify(customSet));
uiLogger.debug("custom set",JSON.stringify(customSet));

iphInitializeUI();
});

initializeUI();
},0);
}

function flowCreateFloatingWindow(title,content,shadowColor='rgba(255, 255, 255, 0.5)',widthVw=80,heightVh=80,offsetCount=null) {
const windowOffset=offsetCount!==null ? offsetCount : flowWindowCount++;

const flowWindowId=`flow-window-${windowOffset || 1}`;
const flowWindow=document.createElement('div');
flowWindow.id=flowWindowId;
flowWindow.className='flow-floating-window';

if (windowOffset===0) {
flowWindow.style.left=`5vw`;
flowWindow.style.top=`5vh`;
} else {
flowWindow.style.left=`${5 * windowOffset}vw`;
flowWindow.style.top=`${5 * windowOffset}vh`;
}

flowWindow.style.boxShadow=`0 0 15px ${shadowColor}`;

const initialWidth=Math.min((window.innerWidth*widthVw)/100,window.innerWidth*0.9);
const initialHeight=Math.min((window.innerHeight*heightVh)/100,window.innerHeight*0.9);

flowWindow.style.width=`${initialWidth}px`;
flowWindow.style.height=`${initialHeight}px`;
flowWindow.setAttribute('data-width-vw',widthVw);
flowWindow.setAttribute('data-height-vh',heightVh);

flowWindow.innerHTML=`
   <div class="flow-window-header">
     <span>${title}</span>
     <span class="flow-close-button" onclick="flowCloseWindow('${flowWindowId}')">&times;</span>
   </div>
   <div class="flow-window-content" style="height: calc(100% - 30px); overflow-y: auto;">
     ${content}
   </div>
   <div class="flow-resize-handle"></div>
 `;

document.body.appendChild(flowWindow);
flowMakeDraggable(flowWindow);
flowMakeResizable(flowWindow);

const resizeHandler=function() {
const widthVw=parseFloat(flowWindow.getAttribute('data-width-vw'));
const heightVh=parseFloat(flowWindow.getAttribute('data-height-vh'));

const desiredWidth=Math.min((window.innerWidth*widthVw)/100,window.innerWidth*0.9);
const desiredHeight=Math.min((window.innerHeight*heightVh)/100,window.innerHeight*0.9);

flowWindow.style.width=`${desiredWidth}px`;
flowWindow.style.height=`${desiredHeight}px`;

const rect=flowWindow.getBoundingClientRect();
if (rect.right>window.innerWidth) {
flowWindow.style.left=`${window.innerWidth - rect.width}px`;
}

if (rect.bottom>window.innerHeight) {
flowWindow.style.top=`${window.innerHeight - rect.height}px`;
}
};

window.addEventListener('resize',resizeHandler);

flowWindow.addEventListener('remove',function() {
window.removeEventListener('resize',resizeHandler);
});
}

function flowCloseWindow(flowWindowId) {
const flowWindowToClose=$(flowWindowId);
if (flowWindowToClose) {
flowWindowToClose.remove();
}
}

function flowMakeDraggable(flowWindow) {
const flowHeader=flowWindow.querySelector('.flow-window-header');
let flowIsDragging=false;
let flowStartX,flowStartY;

flowHeader.addEventListener('mousedown',flowStartDragging);

function flowStartDragging(e) {
flowIsDragging=true;
flowStartX=e.clientX-flowWindow.offsetLeft;
flowStartY=e.clientY-flowWindow.offsetTop;
}

document.addEventListener('mousemove',function(e) {
if (flowIsDragging) {
const flowNewX=e.clientX-flowStartX;
const flowNewY=e.clientY-flowStartY;
flowWindow.style.left=`${flowNewX}px`;
flowWindow.style.top=`${flowNewY}px`;
}
});

document.addEventListener('mouseup',function() {
flowIsDragging=false;
});
}

function flowMakeResizable(flowWindow) {
const resizeHandle=flowWindow.querySelector('.flow-resize-handle');
let isResizing=false;
let startX,startY,startWidth,startHeight;

resizeHandle.addEventListener('mousedown',startResize);

function startResize(e) {
isResizing=true;
startX=e.clientX;
startY=e.clientY;
startWidth=parseInt(getComputedStyle(flowWindow).width,10);
startHeight=parseInt(getComputedStyle(flowWindow).height,10);

document.addEventListener('mousemove',doResize);
document.addEventListener('mouseup',stopResize);
e.preventDefault();
}

function doResize(e) {
if (!isResizing) return;

const newWidth=startWidth+(e.clientX-startX);
const newHeight=startHeight+(e.clientY-startY);

const minWidth=300;
const minHeight=200;

const maxWidth=window.innerWidth*0.9;
const maxHeight=window.innerHeight*0.9;

if (newWidth>=minWidth&&newWidth<=maxWidth) {
flowWindow.style.width=`${newWidth}px`;
}

if (newHeight>=minHeight&&newHeight<=maxHeight) {
flowWindow.style.height=`${newHeight}px`;
}
}

function stopResize() {
isResizing=false;
document.removeEventListener('mousemove',doResize);
document.removeEventListener('mouseup',stopResize);
}
}
