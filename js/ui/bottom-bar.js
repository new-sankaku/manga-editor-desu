//{guid, { imageLink, blob }} blob is lz4
const btmProjectsMap=new Map();

const btmDrawer=$("btm-drawer");
const btmDrawerHandle=$("btm-drawer-handle");
const btmImageContainer=$("btm-image-container");
const btmScrollLeftBtn=$("btm-scroll-left");
const btmScrollRightBtn=$("btm-scroll-right");

let btmScrollPosition=0;
let btmIsDragging=false;

function btmToggleDrawer() {
btmDrawer.classList.toggle("btm-closed");
btmUpdateHandleText();
btmUpdateScrollButtons();
}

function btmCloseDrawer() {
btmDrawer.classList.add("btm-closed");
btmUpdateHandleText();
}

function btmUpdateHandleText() {
btmDrawerHandle.textContent=btmDrawer.classList.contains("btm-closed") ? "OPEN" : "CLOSE";
}


function btmAddImage(imageLink,blob,guid) {
const projectData=btmProjectsMap.get(guid);

if (projectData) {
btmProjectsMap.set(guid,{imageLink,blob});
const image=document.querySelector(`.btm-image[data-index="${guid}"]`);
if (image) {
image.src=imageLink.href;
const pageNumber=image.parentElement.querySelector(".btm-page-number");
if (pageNumber) {
pageNumber.textContent=btmGetGuidIndex(guid)+1;
}
}
} else {
const imageWrapper=document.createElement("div");
imageWrapper.className="btm-image-wrapper";

const pageNumber=document.createElement("div");
pageNumber.className="btm-page-number";

let index=btmGetGuidIndex(guid);
if (index===-1) {
pageNumber.textContent=btmGetGuidsSize()+1;
} else {
pageNumber.textContent=index+1;
}

const moveLeftBtn=document.createElement("button");
moveLeftBtn.innerHTML="←";
moveLeftBtn.className="btm-move-btn btm-move-left";
moveLeftBtn.addEventListener("click",(e)=>{
e.stopPropagation();
const currentIndex=btmGetGuidIndex(guid);
if (currentIndex>0) {
const previousGuid=btmGetGuidByIndex(currentIndex-1);
swapImages(guid,previousGuid);
updateAllPageNumbers();
}
});

const image=document.createElement("img");
image.src=imageLink.href;
image.className="btm-image";
image.dataset.index=guid;
image.addEventListener("click",()=>{
if (stateStack.length>2) {
btmSaveProjectFile().then(()=>{});
}
chengeCanvasByGuid(guid);
});

const moveRightBtn=document.createElement("button");
moveRightBtn.innerHTML="→";
moveRightBtn.className="btm-move-btn btm-move-right";
moveRightBtn.addEventListener("click",(e)=>{
e.stopPropagation();
const currentIndex=btmGetGuidIndex(guid);
if (currentIndex<btmGetGuidsSize()-1) {
const nextGuid=btmGetGuidByIndex(currentIndex+1);
swapImages(guid,nextGuid);
updateAllPageNumbers();
}
});

const deleteBtn=document.createElement("button");
deleteBtn.textContent="🗑";
deleteBtn.className="btm-delete-btn";
deleteBtn.addEventListener("click",(e)=>{
e.stopPropagation();
if (btmGetGuidsSize()>1) {
btmProjectsMap.delete(guid);
imageWrapper.remove();
btmUpdateScrollButtons();
updateAllPageNumbers();
}
});

imageWrapper.appendChild(pageNumber);
imageWrapper.appendChild(moveLeftBtn);
imageWrapper.appendChild(image);
imageWrapper.appendChild(moveRightBtn);
imageWrapper.appendChild(deleteBtn);
btmImageContainer.appendChild(imageWrapper);
btmProjectsMap.set(guid,{imageLink,blob});
}

if (btmDrawer.classList.contains("btm-closed")) {
btmToggleDrawer();
} else {
btmUpdateScrollButtons();
}
}

function updateAllPageNumbers() {
const pageNumbers=document.querySelectorAll(".btm-page-number");
pageNumbers.forEach((numberElement,index)=>{
numberElement.textContent=index+1;
});
}

function swapImages(guid1,guid2) {
const wrapper1=document.querySelector(
`.btm-image[data-index="${guid1}"]`
).parentElement;
const wrapper2=document.querySelector(
`.btm-image[data-index="${guid2}"]`
).parentElement;

const tempElement=document.createElement("div");
btmImageContainer.insertBefore(tempElement,wrapper1);
btmImageContainer.insertBefore(wrapper1,wrapper2);
btmImageContainer.insertBefore(wrapper2,tempElement);
tempElement.remove();

const guids=btmGetGuids();
const newMap=new Map();

guids.forEach((guid)=>{
if (guid===guid1) {
newMap.set(guid2,btmProjectsMap.get(guid2));
} else if (guid===guid2) {
newMap.set(guid1,btmProjectsMap.get(guid1));
} else {
newMap.set(guid,btmProjectsMap.get(guid));
}
});

btmProjectsMap.clear();
newMap.forEach((value,key)=>{
btmProjectsMap.set(key,value);
});

updateAllPageNumbers();
}

function reorderImages(targetIndex,newGuid) {
const newWrapper=document.querySelector(
`.btm-image[data-index="${newGuid}"]`
).parentElement;
const targetWrapper=document.querySelector(
`.btm-image[data-index="${btmGetGuidByIndex(targetIndex)}"]`
).parentElement;
btmImageContainer.insertBefore(newWrapper,targetWrapper);

const newMap=new Map();
const guids=btmGetGuids();
const newGuidData=btmProjectsMap.get(newGuid);

guids.forEach((guid,index)=>{
if (index===targetIndex) {
newMap.set(newGuid,newGuidData);
}
if (guid!==newGuid) {
newMap.set(guid,btmProjectsMap.get(guid));
}
});

btmProjectsMap.clear();
newMap.forEach((value,key)=>{
btmProjectsMap.set(key,value);
});

updateAllPageNumbers();
}

function btmUpdateScrollButtons() {
const containerWidth=btmDrawer.querySelector(
".btm-drawer-content"
).offsetWidth;
const scrollWidth=btmImageContainer.scrollWidth;
btmScrollLeftBtn.style.display=btmScrollPosition>0 ? "block" : "none";
btmScrollRightBtn.style.display=
scrollWidth>containerWidth&&
btmScrollPosition<scrollWidth-containerWidth
? "block"
: "none";
}

function btmScroll(direction) {
const containerWidth=btmDrawer.querySelector(
".btm-drawer-content"
).offsetWidth;
btmScrollPosition+=direction*containerWidth;
btmScrollPosition=Math.max(
0,
Math.min(btmScrollPosition,btmImageContainer.scrollWidth-containerWidth)
);
btmImageContainer.style.transform=`translateX(-${btmScrollPosition}px)`;
btmUpdateScrollButtons();
}

document.addEventListener("DOMContentLoaded",function () {
btmDrawerHandle.addEventListener("click",btmToggleDrawer);
btmScrollLeftBtn.addEventListener("click",()=>btmScroll(-1));
btmScrollRightBtn.addEventListener("click",()=>btmScroll(1));

document.addEventListener("mousedown",function (event) {
if (
!btmDrawer.contains(event.target)&&
!btmDrawer.classList.contains("btm-closed")
) {
btmIsDragging=false;
}
});

document.addEventListener("mouseup",function (event) {
if (
!btmDrawer.contains(event.target)&&
!btmDrawer.classList.contains("btm-closed")&&
!btmIsDragging
) {
btmCloseDrawer();
}
btmIsDragging=false;
});

function btmStartDrag(e) {
e.preventDefault();
isDragging=true;
let startX=e.clientX;
let scrollLeft=btmScrollPosition;

function btmDrag(e) {
const diff=startX-e.clientX;
btmScrollPosition=scrollLeft+diff;
btmImageContainer.style.transform=`translateX(-${btmScrollPosition}px)`;
}

function btmStopDrag() {
document.removeEventListener("mousemove",btmDrag);
document.removeEventListener("mouseup",btmStopDrag);
const containerWidth=btmDrawer.querySelector(
".btm-drawer-content"
).offsetWidth;
btmScrollPosition=Math.max(
0,
Math.min(
btmScrollPosition,
btmImageContainer.scrollWidth-containerWidth
)
);
btmImageContainer.style.transform=`translateX(-${btmScrollPosition}px)`;
btmUpdateScrollButtons();
}

document.addEventListener("mousemove",btmDrag);
document.addEventListener("mouseup",btmStopDrag);
}

btmImageContainer.addEventListener("mousedown",btmStartDrag);
window.addEventListener("resize",btmUpdateScrollButtons);
});

async function chengeCanvasByGuid(guid) {
const projectData=btmProjectsMap.get(guid);
try {
await loadLz4BlobProjectFile(projectData.blob,guid);
} catch (error) {
console.error("Error loading ZIP:",error);
throw error;
}
}

//return [string, string]
function btmGetGuids() {
return Array.from(btmProjectsMap.keys());
}

//return number
function btmGetGuidIndex(targetGuid) {
const guids=Array.from(btmProjectsMap.keys());
return guids.indexOf(targetGuid);
}

//return number
function btmGetGuidsSize() {
return btmProjectsMap.size;
}

//return guid
function btmGetGuidByIndex(index) {
const guids=Array.from(btmProjectsMap.keys());
return guids[index];
}

function btmGetFirstGuidByIndex() {
return Array.from(btmProjectsMap.keys())[0];
}

function btmShowAddPageDialog(guid) {
const dialog=document.createElement("div");
dialog.className="btm-dialog-overlay";
dialog.innerHTML=`
        <div class="btm-dialog">
            <div class="btm-dialog-content">
                <h3>ページサイズを選択</h3>
                <div class="btm-radio-group">
                    <label>
                        <input type="radio" name="page-size" value="a4-portrait" checked>
                        A4縦
                    </label>
                    <label>
                        <input type="radio" name="page-size" value="a4-landscape">
                        A4横
                    </label>
                    <label>
                        <input type="radio" name="page-size" value="b5-portrait">
                        B5縦
                    </label>
                    <label>
                        <input type="radio" name="page-size" value="b5-landscape">
                        B5横
                    </label>
                </div>
                <div class="btm-dialog-buttons">
                    <button class="btm-dialog-button" id="btm-dialog-cancel">キャンセル</button>
                    <button class="btm-dialog-button btm-dialog-submit" id="btm-dialog-submit">作成</button>
                </div>
            </div>
        </div>
    `;

document.body.appendChild(dialog);

// スタイルを追加
const style=document.createElement("style");
style.textContent=`
        .btm-dialog-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        
        .btm-dialog {
            background: white;
            padding: 20px;
            border-radius: 8px;
            min-width: 300px;
        }
        
        .btm-dialog h3 {
            margin: 0 0 20px 0;
            font-size: 18px;
        }
        
        .btm-radio-group {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .btm-radio-group label {
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
        }
        
        .btm-dialog-buttons {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
        }
        
        .btm-dialog-button {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        
        .btm-dialog-submit {
            background: #007bff;
            color: white;
        }
        
        .btm-dialog-submit:hover {
            background: #0056b3;
        }
    `;
document.head.appendChild(style);

// イベントリスナーを設定
const cancelButton=document.getElementById("btm-dialog-cancel");
const submitButton=document.getElementById("btm-dialog-submit");

cancelButton.addEventListener("click",()=>{
document.body.removeChild(dialog);
});

submitButton.addEventListener("click",()=>{
const selectedSize=document.querySelector(
'input[name="page-size"]:checked'
).value;
document.body.removeChild(dialog);
btmSaveProjectFile().then(()=>{
const currentIndex=btmGetGuidIndex(guid);
const newGuid=getCanvasGUID();

console.log("newGuid",newGuid);
if (selectedSize==="a4-portrait") {
loadBookSize(210,297,true);
} else if (selectedSize==="a4-landscape") {
loadBookSize(297,210,true);
} else if (selectedSize==="b5-portrait") {
loadBookSize(257,364,true);
} else if (selectedSize==="b5-landscape") {
loadBookSize(364,257,true);
}

btmSaveProjectFile(newGuid).then(()=>{
console.log("reorderImages前");
reorderImages(currentIndex+1,newGuid);
updateAllPageNumbers();
});
});
});
}
