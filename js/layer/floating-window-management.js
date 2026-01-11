function makeDraggable(element) {
let posX=0,posY=0,posInitX=0,posInitY=0;
let isDragging=false;

element.onmousedown=function (e) {
if (e.target.tagName==="INPUT"||e.target.tagName==="TEXTAREA"||e.target.tagName==="SELECT") {
return;
}
e=e||window.event;
e.preventDefault();
posInitX=e.clientX;
posInitY=e.clientY;
document.onmouseup=closeDragElement;
document.onmousemove=elementDrag;
isDragging=false;
};

function elementDrag(e) {
e=e||window.event;
e.preventDefault();
posX=posInitX-e.clientX;
posY=posInitY-e.clientY;
posInitX=e.clientX;
posInitY=e.clientY;
element.style.top=(element.offsetTop-posY)+"px";
element.style.left=(element.offsetLeft-posX)+"px";
isDragging=true;
}

function closeDragElement() {
document.onmouseup=null;
document.onmousemove=null;
if (isDragging) {
setTimeout(()=>isDragging=false,100);
}
}

element.onclick=function (e) {
if (isDragging) {
e.stopImmediatePropagation();
}
}
}


function isNotVisibleFloatingWindow() {
return!(isVisibleFloatingWindow());
}

function isVisibleFloatingWindow() {
const classNames=[
'floating-window',
'floating-windowPromptClass'
];

const ids=[
'aaaaaaaaaaaaaaaId1',
'aaaaaaaaaaaaaaaId2'
];
for (let className of classNames) {
const windows=document.querySelectorAll(`.${className}`);
for (let i=0;i<windows.length;i++) {
const win=windows[i];
const style=window.getComputedStyle(win);
if (style.display!=='none'&&style.visibility!=='hidden') {
return true;
}
}
}
for (let id of ids) {
const win=$(id);
if (win) {
const style=window.getComputedStyle(win);
if (style.display!=='none'&&style.visibility!=='hidden') {
return true;
}
}
}
return false;
}