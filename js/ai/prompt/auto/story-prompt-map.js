let OpeningScenario=100000
let SoloScenario=200000
let EarlyForeplayScenario=300000
let LateForeplayScenario=400000
let SexScenario=500000
let LateSexScenario=600000
let EjaculationScenario=700000
let SexAfterScenario=800000

class ScenarioPromptMap {
constructor() {
this.ranges=new Map();
}

add(key,values) {
const mappedValues=values.map(Number);
const sortedValues=mappedValues.sort((a,b)=>a-b);
this.ranges.set(key,sortedValues);
}

getInRange(key,start,end) {
const values=this.ranges.get(key);

if (!values) {
return [];
}

const numStart=Number(start);
const numEnd=Number(end);

const filteredValues=values.filter(v=>{
const isInRange=v>=numStart&&v<=numEnd;
return isInRange;
});

return filteredValues;
}

getKeys() {
const keys=Array.from(this.ranges.keys());
return keys;
}
}

const scenarioPromptMap=new ScenarioPromptMap();
scenarioPromptMap.add('normal_sex',[100000,200000,300000,400000,420000,500000,510000,600000,700000,800000]);

// return [300000, 310000, 320000, 330000, 400000]
// console.log(scenarioPromptMap.getInRange('normal_sex', 300000, 400000));


function getScenarioPromptList(){
return scenarioPromptMap.getKeys();
}


function setScenarioPromptSelecter(){
const select=$('ScenarioPromptSelecter');
const keys=getScenarioPromptList();

select.innerHTML='';

const emptyOpt=document.createElement('option');
emptyOpt.value='';
emptyOpt.textContent='';
select.appendChild(emptyOpt);

keys.forEach(key=>{
const opt=document.createElement('option');
opt.value=key;
opt.textContent=getText(key);
select.appendChild(opt);
});
}
setScenarioPromptSelecter();



function getOpeningScenarioPromptNumbers(scenarioName){
let start=100000;
return scenarioPromptMap.getInRange(scenarioName,start,(start+99999));
}
function getSoloScenarioPromptNumbers(scenarioName){
let start=200000;
return scenarioPromptMap.getInRange(scenarioName,start,(start+99999));
}
function getEarlyForeplayScenarioPromptNumbers(scenarioName){
let start=300000;
return scenarioPromptMap.getInRange(scenarioName,start,(start+99999));
}
function getLateForeplayScenarioPromptNumbers(scenarioName){
let start=400000;
return scenarioPromptMap.getInRange(scenarioName,start,(start+99999));
}
function getSexScenarioPromptNumbers(scenarioName){
let start=500000;
return scenarioPromptMap.getInRange(scenarioName,start,(start+99999));
}
function getLateSexScenarioPromptNumbers(scenarioName){
let start=600000;
return scenarioPromptMap.getInRange(scenarioName,start,(start+99999));
}
function getEjaculationScenarioPromptNumbers(scenarioName){
let start=700000;
return scenarioPromptMap.getInRange(scenarioName,start,(start+99999));
}
function getSexAfterScenarioPromptNumbers(scenarioName){
let start=800000;
return scenarioPromptMap.getInRange(scenarioName,start,(start+99999));
}