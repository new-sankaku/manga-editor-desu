function hideById(id) {
const el=$(id);
if (el) {
el.style.display='none';
}
}
function showById(id) {
const el=$(id);
if (el) {
el.style.display='';
}
}

function changeHiddenById(id,showTextKey=null,hiddenTextKey=null) {
const el=$(id);
const headerElement=el.previousElementSibling;

if (el&&headerElement) {
if (el.style.display==='none') {
el.style.display='';
if(showTextKey!==null){
var word=getText(showTextKey);
headerElement.textContent=word;
}
} else {
el.style.display='none';
if(hiddenTextKey!==null){
var word=getText(hiddenTextKey);
headerElement.textContent=word;
}
}
}
}


function unSelectedById(id){
const el=$(id);
if (el) {
el.classList.remove('selected');
}
}
function selectedById(ids){
const el=$(ids);
if (el) {
el.classList.add('selected');
}
}

function getSelectedValueByButton(button) {
return button.dataset.value;
}
function getSelectedValueByGroup(groupName) {
return document.querySelector(`[data-group="${groupName}"] .selected`).dataset.value;
}
function unSelectedByButton(button) {
const group=button.closest('[data-group]');
group.querySelector('.selected')?.classList.remove('selected');
button.classList.add('selected');
}
function selectedByButton(button) {
button.classList.add('selected');
}

function changeSelected(button) {
unSelectedByButton(button);
selectedByButton(button);
}
