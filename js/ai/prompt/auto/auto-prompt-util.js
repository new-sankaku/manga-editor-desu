// generatePageList(btmGetGuidsSize());

const PROMPT_OPENING='PROMPT_OPENING';
const PROMPT_EARLY='PROMPT_EARLY';
const PROMPT_LATE='PROMPT_LATE';
const PROMPT_SEX='PROMPT_SEX';
const PROMPT_FINISH='PROMPT_FINISH';
const PROMPT_AFTER='PROMPT_AFTER';
const PROMPT_CHANGE_SCENE='PROMPT_CHANGE_SCENE';

function getRandomInt(min,max) {
return Math.floor(Math.random()*(max-min+1))+min;
}

function verifyStructure(sections) {
let currentCycle=[];
let isValid=true;
let foundMaeburi=false;

for (let i=0;i<sections.length;i++) {
const section=sections[i];
if (section.type===PROMPT_EARLY) {
if (foundMaeburi) {
if (!currentCycle.every(s=>s.pages>=1)) {
isValid=false;
break;
}
currentCycle=[];
}
foundMaeburi=true;
}
if (foundMaeburi&&[PROMPT_LATE,PROMPT_SEX,PROMPT_FINISH].includes(section.type)) {
currentCycle.push(section);
}
}
if (currentCycle.length>0&&!currentCycle.every(s=>s.pages>=1)) {
isValid=false;
}
return isValid;
}

function adjustPages(sections,targetTotal) {
const MAX_ATTEMPTS=100;
let attempts=0;

while (attempts<MAX_ATTEMPTS) {
let currentTotal=sections.reduce((sum,section)=>sum+section.pages,0);
if (currentTotal===targetTotal&&verifyStructure(sections)) {
return sections;
}
sections=generateInitialStructure(targetTotal);
attempts++;
}
throw new Error('unknwn page generate.');
}

function generateInitialStructure(totalPages) {


const structure=[];
structure.push({type: PROMPT_OPENING,pages: 1});

let remainingPages=totalPages-2;
let cycleCount=0;

while (remainingPages>0&&cycleCount<3) {
if (cycleCount>0) {
if (remainingPages<4) break;
const scenePages=getRandomInt(1,Math.min(2,remainingPages-4));
structure.push({type: PROMPT_CHANGE_SCENE,pages: scenePages});
remainingPages-=scenePages;
}

if (remainingPages<4) break;

const maeburePages=getRandomInt(1,Math.min(3,remainingPages-3));
structure.push({type: PROMPT_EARLY,pages: maeburePages});
remainingPages-=maeburePages;

const atofuriPages=getRandomInt(1,Math.min(3,remainingPages-2));
structure.push({type: PROMPT_LATE,pages: atofuriPages});
remainingPages-=atofuriPages;

const honbunPages=getRandomInt(1,Math.min(3,remainingPages-1));
structure.push({type: PROMPT_SEX,pages: honbunPages});
remainingPages-=honbunPages;

const ochiPages=getRandomInt(1,Math.min(2,remainingPages));
structure.push({type: PROMPT_FINISH,pages: ochiPages});
remainingPages-=ochiPages;

cycleCount++;
}

structure.push({type: PROMPT_FINISH,pages: 1});
return structure;
}


function generatePageList() {

let totalPages=btmGetGuidsSize();

if(totalPages<6){
let structure=[];
if(totalPages==1||totalPages==0){
structure.push({type: PROMPT_SEX,pages: 1});
}else if(totalPages==2){
structure.push({type: PROMPT_OPENING,pages: 1});
structure.push({type: PROMPT_SEX,pages: 2});
}else if(totalPages==3){
structure.push({type: PROMPT_OPENING,pages: 1});
structure.push({type: PROMPT_EARLY,pages: 2});
structure.push({type: PROMPT_SEX,pages: 3});
}else if(totalPages==4){
structure.push({type: PROMPT_OPENING,pages: 1});
structure.push({type: PROMPT_EARLY,pages: 2});
structure.push({type: PROMPT_SEX,pages: 3});
structure.push({type: PROMPT_FINISH,pages: 4});
}else if(totalPages==5){
structure.push({type: PROMPT_OPENING,pages: 1});
structure.push({type: PROMPT_EARLY,pages: 2});
structure.push({type: PROMPT_LATE,pages: 3});
structure.push({type: PROMPT_SEX,pages: 4});
structure.push({type: PROMPT_FINISH,pages: 5});
}
return structure;
}

const structure=adjustPages(generateInitialStructure(totalPages),totalPages);
let currentPage=1;
const pageList=[];
// console.log("structure 100", JSON.stringify(structure));

structure.forEach(section=>{
for (let i=0;i<section.pages;i++) {
pageList.push({
page: currentPage,
type: section.type
});
currentPage++;
}
});
// console.log("pageList 100", JSON.stringify(pageList));

return pageList;
}




async function autoMultiPromptSet(){
let scenarioPromptSelecter=$('ScenarioPromptSelecter').value;
if(!scenarioPromptSelecter){
createToastError("Prompt Set is not selected.","");
return;
}

let firstGuid=btmGetFirstGuidByIndex();
await chengeCanvasByGuid(firstGuid);

let pageList=generatePageList();

for (const [index,page] of pageList.entries()) {
let guid=btmGetGuidByIndex(index);

await chengeCanvasByGuid(guid);

let panelList=getPanelObjectList();
panelList.forEach((panel,panelIndex)=>{
let randomSenario=getRandomSenario(index,scenarioPromptSelecter,page.type)
if(randomSenario){
panel.text2img_prompt=panel.text2img_prompt+","+randomSenario.positive;
panel.text2img_negative=panel.text2img_negative+","+randomSenario.negative;
// console.log("guid index:", index, ":", guid, " panelSize:", panelList.length, " positive:", randomSenario.positive);
}
});

await btmSaveProjectFile();
}
}





function getRandomSenario(index,scenarioName,type){
// console.log("nowSenarioNumber scenarioName, type", scenarioName, type);

let promptNumbers=[];
let array=[];

switch (type) {
case PROMPT_OPENING:
array=getOpeningScenarioPromptNumbers(scenarioName);
promptNumbers=promptNumbers.concat(array);
break;
case PROMPT_EARLY:
array=getSoloScenarioPromptNumbers(scenarioName);
promptNumbers=promptNumbers.concat(array);
array=getEarlyForeplayScenarioPromptNumbers(scenarioName);
promptNumbers=promptNumbers.concat(array);
break;
case PROMPT_LATE:
array=getLateForeplayScenarioPromptNumbers(scenarioName);
promptNumbers=promptNumbers.concat(array);
break;
case PROMPT_SEX:
array=getSexScenarioPromptNumbers(scenarioName);
promptNumbers=promptNumbers.concat(array);
break;
case PROMPT_FINISH:
array=getEjaculationScenarioPromptNumbers(scenarioName);
promptNumbers=promptNumbers.concat(array);
break;
case PROMPT_AFTER:
array=getSexAfterScenarioPromptNumbers(scenarioName);
promptNumbers=promptNumbers.concat(array);
array=getLateSexScenarioPromptNumbers(scenarioName);
promptNumbers=promptNumbers.concat(array);
break;
case PROMPT_CHANGE_SCENE:
array=getOpeningScenarioPromptNumbers(scenarioName);
promptNumbers=promptNumbers.concat(array);
break;
default:

break;
}
const result=promptMultiKeyMap.getRandomByStoryOrders(promptNumbers);
// console.log("index:",index, " promptNumbers:",JSON.stringify(promptNumbers), " randomPromptNumber:",result.positive);

return result;
}


