function rundomPanelCut() {
var panel=getRandomPanel();
var maxRetryCount=2;

if (panel===null) {
createToastError("Panel is ZERO.");
return;
}

var vRandomCount=generateRandomInt($("verticalRandomPanelCount").value);
var hRandomCount=generateRandomInt($("horizontalRandamPanelCount").value);

// console.log("vRandomCount", vRandomCount);
// console.log("hRandomCount", hRandomCount);


try {
changeDoNotSaveHistory();

var cuts=createCuts(vRandomCount,hRandomCount);

var maxRetryCountSum=maxRetryCount*cuts.length;
var retry=0;

while (cuts.length>0) {
if (retry>maxRetryCountSum) {
// console.log("split retryCount over.");
return;
}

var currentCut=cuts[0];
var isSplit=blindSplitPanel(panel,currentCut==='vertical');

if (isSplit) {
cuts.shift();
panel=getRandomPanel();
} else {
retry++;
}
}
} finally {
changeDoSaveHistory();
canvas.requestRenderAll();
}
}


function createCuts(vRandomCount,hRandomCount) {
var cuts=[];
const alternateCount=Math.min(4,Math.min(vRandomCount,hRandomCount)*2);
for (let i=0;i<alternateCount;i++) {
cuts.push(i%2===0 ? 'vertical' : 'horizontal');
}
const remainingV=Math.max(0,vRandomCount-alternateCount/2);
const remainingH=Math.max(0,hRandomCount-alternateCount/2);
for (let i=0;i<remainingV;i++) cuts.push('vertical');
for (let i=0;i<remainingH;i++) cuts.push('horizontal');

if (cuts.length>4) {
const fixed=cuts.slice(0,4);
const rest=cuts.slice(4).sort(()=>Math.random()-0.5);
cuts=[...fixed,...rest];
}

return cuts;
}



async function generateMultipage(){
const loading=OP_showLoading({icon: 'process',step: 'Step1',substep: 'Multi Page',progress: 0});
await new Promise(requestAnimationFrame);

try{
const pageCount=$("pageCount").value;
var newPage=false;
const selectedValue=getSelectedValueByGroup("multiPageType");
for (let page=1;page<=pageCount;page++) {

OP_updateLoadingState(loading,{
icon: 'process',step: 'Step2',substep: 'Page:'+page,progress: 50
});
await new Promise(requestAnimationFrame);

panelLogger.debug("----- "+page+" -----")
if(selectedValue==='mPortrait'){
await loadBookSize(210,297,true,newPage);
rundomPanelCut();
}
if(selectedValue==='mLandscape'){
await loadBookSize(297,210,true,newPage);
rundomPanelCut();
}
newPage=true;
}
await btmSaveProjectFile();
} finally {
OP_hideLoading(loading);
}
}
$on($("panelRandamCutButton"),"click",()=>rundomPanelCut());
$on($("multiPageGenerate"),"click",()=>generateMultipage());