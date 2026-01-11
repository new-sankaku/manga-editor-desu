async function autoMultiGenerate() {
const loading=OP_showLoading({icon: 'process',step: 'Step1',substep: 'Multi Page',progress: 0});
await new Promise(requestAnimationFrame);

try{
let onePanelNumber=$("onePanelGenerateNumber").value;

let guidList=btmGetGuids();
for (const [index,guid] of guidList.entries()) {

OP_updateLoadingState(loading,{
icon: 'process',step: 'Step2',substep: 'Page:'+(index+1),progress: 50
});
await new Promise(requestAnimationFrame);

await chengeCanvasByGuid(guid);

for (let i=0;i<onePanelNumber;i++) {
const promises=[];
let panelList=getPanelObjectList();

panelList.forEach((panel,panelIndex)=>{
var spinner=createSpinner(canvasMenuIndex);
promises.push(T2I(panel,spinner));
});

await Promise.all(promises);

while (true) {
if (existsWaitQueue()) {
await new Promise((r)=>setTimeout(r,2000));
continue;
} else {
break;
}
}

}

await btmSaveProjectFile();
}
}finally{
OP_hideLoading(loading);
}
}