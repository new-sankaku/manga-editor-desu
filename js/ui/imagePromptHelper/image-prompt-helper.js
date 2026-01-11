let iphData={};
let iphCurrentPath=[];
let iphSelectedTagGroups=[];
let iphSelectedImages=[];
let iphImageCache=new Map();
let iphImageWrappers=[];

function loadJsResource(language,namespace,callback) {
loadJS(`json_js/01_trans_${language}.js`,'head')
.then(()=>{
const resources=window[`trans_${language}`];
callback(null,resources);
})
.catch(error=>{
uiLogger.error(`Error loading language file for ${language}:`,error);
callback(error,null);
});
}

function initI18next(lang) {
uiLogger.debug("lang",lang);
return i18next
.use({
type: 'backend',
read: loadJsResource,
})
.init({
lng: lang,
fallbackLng: 'en',
});
}

function iphInitializeUI() {
const languageDropdown=$('iph-language-dropdown');
const modelDropdown=$('iph-model-dropdown');
languageDropdown.addEventListener('change',iphLoadJsonAndRefresh);
modelDropdown.addEventListener('change',iphLoadJsonAndRefresh);

iphLoadJsonAndRefresh();

$('iph-download-button').addEventListener('click',()=>{
if (iphSelectedTagGroups.length>0) {
const content=iphSelectedTagGroups.join(',');
const blob=new Blob([content],{type: 'text/plain'});
const a=document.createElement('a');
a.href=URL.createObjectURL(blob);
a.download='selected_tags.txt';
a.click();
}
});

$('iph-copy-button').addEventListener('click',()=>{
if (iphSelectedTagGroups.length>0) {
const content=iphSelectedTagGroups.join(',');
navigator.clipboard.writeText(content).then(()=>{
}).catch(err=>{
uiLogger.error('クリップボードへのコピーに失敗しました:',err);
});
}
});
}

function iphLoadJsonAndRefresh() {
iphData={};
iphLoadLocalStorage()
.then(()=>iphLoadData())
.then(()=>{
iphRefreshUI();
});
}

function iphLoadLocalStorage() {
return new Promise((resolve)=>{
const customSetJson=localStorage.getItem('CustomSet');
if (customSetJson) {
const customSet=JSON.parse(customSetJson);


if (customSet&&customSet['Custom Set']) {
iphData['Custom Set']={};

Object.entries(customSet['Custom Set']).forEach(([name,content])=>{
iphData['Custom Set'][name]={
url: content.url,
alias: content.alias
};
});
}
}
resolve();
});
}

function iphRefreshUI() {
iphCurrentPath=[];
iphSelectedTagGroups=[];
iphSelectedImages=[];
iphShowTag1();
iphUpdateSelectedTagsDisplay();
iphUpdateImageDisplay();
}

async function iphLoadData() {
const language=$('iph-language-dropdown').value;
const model=$('iph-model-dropdown').value.toLowerCase();

try {
await Promise.all([
loadJS('json_js/00_base.js','head'),
loadJS(`json_js/00_prompt_${model}_base.js`,'head')
]);

iphData={
...iphData,
...window[`prompt_${model}_base`],
...window.base
};

if (language==='en') {
iphData=iphFilterEnglishData(iphData);
}

uiLogger.debug('Data loaded successfully');
} catch (error) {
uiLogger.error('Error loading data:',error);
}
}

function iphFilterEnglishData(data) {
const filteredData={};
for (const key in data) {
if (key==='hr') {
filteredData[key]=data[key];
} else if (data[key].hasOwnProperty('en')) {
filteredData[data[key].en]=iphFilterEnglishData(data[key]);
} else if (typeof data[key]==='object'&&!Array.isArray(data[key])) {
filteredData[key]=iphFilterEnglishData(data[key]);
} else {
filteredData[key]=data[key];
}
}
return filteredData;
}

function iphShowTag1() {
const tag1Container=$('iph-category-container');
tag1Container.innerHTML='';
let hrCount=0;
Object.keys(iphData).forEach(tag=>{
if (tag.startsWith('horizontalLine')) {
const hr=document.createElement('hr');
hr.classList.add('narrow-hr');
tag1Container.appendChild(hr);
hrCount++;
} else {
const button=iphCreateButton(tag,1);
button.addEventListener('click',()=>iphSelectTag(tag,0,iphData[tag]));
tag1Container.appendChild(button);
}
});
}

function iphCreateButton(text,level,url,alias,isCustomSet=false) {
const button=document.createElement('button');
button.classList.add('iph-tag-button',`iph-tag${level}-button`);

if (url) {
const placeholder=document.createElement('div');
placeholder.classList.add('iph-image-placeholder');
placeholder.textContent=getText("loading_image");

button.appendChild(placeholder);

iphLoadImage(url).then(img=>{
placeholder.remove();
button.insertBefore(img,button.firstChild);
}).catch(()=>{
placeholder.textContent=getText("image_load_error");
});

if (isCustomSet) {
button.classList.add('iph-custom-set-button');
const removeButton=document.createElement('span');
removeButton.classList.add('iph-remove-custom-set');
removeButton.innerHTML='✕';
removeButton.onclick=(e)=>{
e.stopPropagation();
e.preventDefault();
iphRemoveCustomSetItem(text,button);
};
button.appendChild(removeButton);
}
}

const span=document.createElement('span');
if (alias) {
span.textContent=alias;
} else {
span.textContent=text;
}
button.appendChild(span);
return button;
}

function iphLoadImage(url) {
if (iphImageCache.has(url)) {
return Promise.resolve(iphImageCache.get(url).cloneNode());
}

return new Promise((resolve,reject)=>{
const img=new Image();
img.onload=()=>{
iphImageCache.set(url,img);
resolve(img.cloneNode());
};
img.onerror=reject;
img.src=url;
img.alt="";
});
}

function iphShowTags(currentData,level) {
const tagLevels=$('iph-sub-category-container');

while (tagLevels.children.length>level) {
tagLevels.removeChild(tagLevels.lastChild);
}

const levelContainer=document.createElement('div');
const buttons=Object.keys(currentData).map(tag=>{
const tagData=currentData[tag];

const url=tagData.url||(typeof tagData==='object'&&tagData.hasOwnProperty('url') ? tagData.url : null);
const alias=tagData.alias||(typeof tagData==='object'&&tagData.hasOwnProperty('alias') ? tagData.alias : null);
const isCustomSet=iphCurrentPath[0]==='Custom Set';
const button=iphCreateButton(tag,level+1,url,alias,isCustomSet);
button.addEventListener('click',()=>iphSelectTag(tag,level,tagData));
return button;
});

Promise.all(buttons.map(button=>{
const img=button.querySelector('img');
return img ? iphLoadImage(img.src) : Promise.resolve();
})).then(()=>{
buttons.forEach(button=>levelContainer.appendChild(button));
tagLevels.appendChild(levelContainer);
});
}

function iphSelectTag(tag,level,data) {
const tagLevels=$('iph-sub-category-container');
while (tagLevels.children.length>level) {
tagLevels.removeChild(tagLevels.lastChild);
}

iphCurrentPath=iphCurrentPath.slice(0,level);
iphCurrentPath.push(tag);

if (typeof data==='object'&&!data.hasOwnProperty('url')) {
iphShowTags(data,level+1);
} else {
iphFinishSelection(tag,data);
}
}

function iphFinishSelection(tag,item) {
iphAddSelectedTag(tag);
iphAddImage(item.url);
iphCurrentPath=[];
}

function iphAddSelectedTag(tag) {
iphSelectedTagGroups.push(tag);
iphUpdateSelectedTagsDisplay();
}

function iphUpdateSelectedTagsDisplay() {
const selectedTagsElement=$('iph-selected-tags');
selectedTagsElement.innerHTML='';
iphSelectedTagGroups.forEach((tag,index)=>{
const groupElement=document.createElement('span');
groupElement.classList.add('iph-selected-tag-group');
groupElement.textContent=tag;
groupElement.addEventListener('click',()=>iphRemoveTagGroup(index));
const removeButton=document.createElement('span');
removeButton.classList.add('iph-remove-tag');
removeButton.innerHTML='✕';
removeButton.addEventListener('click',(e)=>{
e.stopPropagation();
iphRemoveTagGroup(index);
});
groupElement.appendChild(removeButton);
selectedTagsElement.appendChild(groupElement);
});

const downloadButton=$('iph-download-button');
const copyButton=$('iph-copy-button');
const hasSelectedTags=iphSelectedTagGroups.length>0;
downloadButton.disabled=!hasSelectedTags;
copyButton.disabled=!hasSelectedTags;
}

function iphRemoveTagGroup(index) {
iphSelectedTagGroups.splice(index,1);
iphSelectedImages.splice(index,1);
const imageWrapper=iphImageWrappers[index];
if (imageWrapper) {
imageWrapper.remove();
iphImageWrappers.splice(index,1);
iphUpdateImageIndices();
}
iphUpdateSelectedTagsDisplay();
}

function iphUpdateImageIndices() {
iphImageWrappers.forEach((wrapper,index)=>{
const removeButton=wrapper.querySelector('.iph-remove-tag');
removeButton.onclick=(e)=>{
e.stopPropagation();
iphRemoveTagGroup(index);
};
wrapper.querySelector('img').onclick=()=>iphRemoveTagGroup(index);
});
}

function iphAddImage(url) {
if (url) {
iphSelectedImages.push(url);
const imageContainer=$('iph-image-container');
const index=iphSelectedImages.length-1;

iphLoadImage(url).then(img=>{
const wrapper=iphCreateImageWrapper(url,index);
imageContainer.appendChild(wrapper);
iphImageWrappers.push(wrapper);
iphUpdateImageIndices();
});
}
}

function iphCreateImageWrapper(url,index) {
const imageWrapper=document.createElement('div');
imageWrapper.classList.add('iph-image-container');

const imgElement=document.createElement('img');
imgElement.src=url;

const removeButton=document.createElement('span');
removeButton.classList.add('iph-remove-tag');
removeButton.style.display='none';

removeButton.innerHTML='✕';

imageWrapper.appendChild(imgElement);
imageWrapper.appendChild(removeButton);
return imageWrapper;
}

function iphUpdateImageDisplay() {
const imageContainer=$('iph-image-container');
imageContainer.innerHTML='';
iphImageWrappers=[];

iphSelectedImages.forEach((url,index)=>{
iphLoadImage(url).then(img=>{
const wrapper=iphCreateImageWrapper(url,index);
imageContainer.appendChild(wrapper);
iphImageWrappers.push(wrapper);
});
});
}

function iphRemoveCustomSetItem(itemName,buttonElement) {
let customSet=JSON.parse(localStorage.getItem('CustomSet')||'{"Custom Set":{}}');

if (customSet['Custom Set']&&customSet['Custom Set'][itemName]) {
delete customSet['Custom Set'][itemName];
localStorage.setItem('CustomSet',JSON.stringify(customSet));
if (iphData['Custom Set']&&iphData['Custom Set'][itemName]) {
delete iphData['Custom Set'][itemName];
}
if (buttonElement&&buttonElement.parentNode) {
buttonElement.parentNode.removeChild(buttonElement);
}
const index=iphSelectedTagGroups.indexOf(itemName);
if (index!==-1) {
iphRemoveTagGroup(index);
}
if (iphCurrentPath[0]==='Custom Set') {
iphShowTags(iphData['Custom Set'],iphCurrentPath.length-1);
}
}
}
