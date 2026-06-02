// プロジェクトフォルダ選択ダイアログ。FastAPI 開発サーバの /api/folders を利用 (HOME 以下に限定)。

const FOLDER_PICKER_API='/api/folders';
const FOLDER_PICKER_KEY='currentProjectPath';

const folderPickerStore=(typeof localforage!=='undefined')
?localforage.createInstance({name:'folderPicker'})
:null;

window.FolderPicker={
open:openFolderPicker,
getCurrent:async function(){
if(!folderPickerStore) return null;
return folderPickerStore.getItem(FOLDER_PICKER_KEY);
}
};

function fpText(key){
if(typeof i18next!=='undefined'&&i18next.isInitialized){
return i18next.t(key);
}
return key;
}

async function openFolderPicker(){
let initial='';
if(folderPickerStore){
try{
const saved=await folderPickerStore.getItem(FOLDER_PICKER_KEY);
if(saved&&typeof saved.path==='string') initial=saved.path;
}catch(err){
folderPickerLogger.warn('failed to load saved path',err);
}
}
renderFolderPickerDialog(initial);
}

function renderFolderPickerDialog(initialPath){
const overlay=document.createElement('div');
overlay.className='folder-picker-overlay';
overlay.innerHTML=`
<div class="folder-picker-modal" role="dialog" aria-modal="true">
<div class="folder-picker-header">
<h3 class="folder-picker-title" data-i18n="folderPickerTitle"></h3>
<button type="button" class="folder-picker-close" aria-label="Close">&times;</button>
</div>
<div class="folder-picker-path-bar" id="folderPickerPathBar"></div>
<div class="folder-picker-toolbar">
<button type="button" class="folder-picker-btn folder-picker-parent" id="folderPickerParent">
<i class="material-icons">arrow_upward</i>
<span data-i18n="folderPickerParent"></span>
</button>
</div>
<div class="folder-picker-list" id="folderPickerList">
<div class="folder-picker-status" data-i18n="folderPickerLoading"></div>
</div>
<div class="folder-picker-footer">
<button type="button" class="folder-picker-btn folder-picker-cancel" data-i18n="folderPickerCancel"></button>
<button type="button" class="folder-picker-btn folder-picker-select" data-i18n="folderPickerSelect"></button>
</div>
</div>
`;
document.body.appendChild(overlay);

overlay.querySelectorAll('[data-i18n]').forEach(el=>{
el.textContent=fpText(el.getAttribute('data-i18n'));
});

let currentPath=initialPath||'';
let currentDisplayPath='';

const close=()=>{
overlay.remove();
document.removeEventListener('keydown',onKey);
};
const onKey=(e)=>{if(e.key==='Escape') close();};
document.addEventListener('keydown',onKey);

overlay.addEventListener('click',(e)=>{
if(e.target===overlay) close();
});
overlay.querySelector('.folder-picker-close').addEventListener('click',close);
overlay.querySelector('.folder-picker-cancel').addEventListener('click',close);

overlay.querySelector('.folder-picker-select').addEventListener('click',async ()=>{
const payload={path:currentPath,displayPath:currentDisplayPath,timestamp:Date.now()};
if(folderPickerStore){
try{
await folderPickerStore.setItem(FOLDER_PICKER_KEY,payload);
}catch(err){
folderPickerLogger.error('failed to persist selection',err);
}
}
close();
if(window.ProjectLoader&&typeof window.ProjectLoader.loadFromFolder==='function'){
await window.ProjectLoader.loadFromFolder(currentPath,currentDisplayPath);
}else{
const label=currentDisplayPath||currentPath||fpText('folderPickerHome');
createToast(fpText('folderPickerSelected'),[label]);
}
});

overlay.querySelector('#folderPickerParent').addEventListener('click',async ()=>{
if(!currentPath) return;
const idx=currentPath.lastIndexOf('/');
const next=idx>=0?currentPath.substring(0,idx):'';
await navigate(next);
});

const navigate=async (path)=>{
currentPath=path;
const list=overlay.querySelector('#folderPickerList');
const pathBar=overlay.querySelector('#folderPickerPathBar');
const parentBtn=overlay.querySelector('#folderPickerParent');
list.innerHTML=`<div class="folder-picker-status">${fpText('folderPickerLoading')}</div>`;
try{
const res=await fetch(`${FOLDER_PICKER_API}?path=${encodeURIComponent(path)}`);
if(!res.ok) throw new Error('http '+res.status);
const data=await res.json();
currentDisplayPath=data.displayPath;
pathBar.textContent=data.displayPath;
parentBtn.disabled=(data.parent===null);
list.innerHTML='';
if(data.entries.length===0){
const empty=document.createElement('div');
empty.className='folder-picker-status';
empty.textContent=fpText('folderPickerEmpty');
list.appendChild(empty);
return;
}
data.entries.forEach(entry=>{
const item=document.createElement('div');
item.className='folder-picker-item';
item.innerHTML=`<i class="material-icons folder-picker-item-icon">folder</i><span class="folder-picker-item-name"></span>`;
item.querySelector('.folder-picker-item-name').textContent=entry.name;
item.addEventListener('dblclick',()=>navigate(entry.path));
item.addEventListener('click',()=>{
list.querySelectorAll('.folder-picker-item.active').forEach(el=>el.classList.remove('active'));
item.classList.add('active');
currentPath=entry.path;
currentDisplayPath=data.displayPath+'/'+entry.name;
pathBar.textContent=currentDisplayPath;
});
list.appendChild(item);
});
}catch(err){
folderPickerLogger.error('folder fetch failed',err);
const errorEl=document.createElement('div');
errorEl.className='folder-picker-status error';
errorEl.textContent=fpText('folderPickerError');
list.innerHTML='';
list.appendChild(errorEl);
}
};

navigate(currentPath);
}

document.addEventListener('DOMContentLoaded',()=>{
const btn=document.getElementById('projectFolderOpen');
if(!btn) return;
btn.addEventListener('click',(e)=>{
e.preventDefault();
openFolderPicker();
});
});
