// プロンプトタグ頻度のlocalforage永続化
var dashboardTagLogger=new SimpleLogger('dashboard-tag',LogLevel.DEBUG);
var PromptFrequencyStorage=(function(){
var store=localforage.createInstance({
name:'MangaEditor_PromptFrequency',
storeName:'tagFrequency',
});
var MAX_TAGS=500;
var MAX_COOCCURRENCE=500;
function parsePrompt(prompt){
if(!prompt||typeof prompt!=='string') return[];
var tags=prompt
.split(',')
.map(function(tag){return tag.trim().toLowerCase();})
.map(function(tag){return tag.replace(/\s{2,}/g,' ');})
.filter(function(tag){return tag.length>0&&tag.length<100;});
return[...new Set(tags)];
}
async function getAllFrequencies(){
try{
var data=await store.getItem('frequencies');
return data||{};
}catch(error){
dashboardTagLogger.error('Error getting frequencies:',error);
return{};
}
}
async function recordPrompt(prompt){
try{
var tags=parsePrompt(prompt);
if(tags.length===0) return null;
var frequencies=await getAllFrequencies();
var now=Date.now();
for(var i=0;i<tags.length;i++){
var tag=tags[i];
if(frequencies[tag]){
frequencies[tag].count+=1;
frequencies[tag].lastUsed=now;
}else{
frequencies[tag]={
count:1,
firstUsed:now,
lastUsed:now,
};
}
}
var tagList=Object.entries(frequencies);
if(tagList.length>MAX_TAGS){
tagList.sort(function(a,b){
if(a[1].count!==b[1].count){
return a[1].count-b[1].count;
}
return a[1].lastUsed-b[1].lastUsed;
});
var toRemove=tagList.length-MAX_TAGS;
for(var i=0;i<toRemove;i++){
delete frequencies[tagList[i][0]];
}
}
await store.setItem('frequencies',frequencies);
if(tags.length>=2){
await recordCoOccurrence(tags);
}
return frequencies;
}catch(error){
dashboardTagLogger.error('Error recording prompt:',error);
return null;
}
}
async function recordCoOccurrence(tags){
try{
var coData=(await store.getItem('cooccurrence'))||{};
for(var i=0;i<tags.length;i++){
for(var j=i+1;j<tags.length;j++){
var pair=[tags[i],tags[j]].sort().join('|||');
if(!coData[pair]){
coData[pair]=0;
}
coData[pair]+=1;
}
}
var entries=Object.entries(coData);
if(entries.length>MAX_COOCCURRENCE){
entries.sort(function(a,b){return a[1]-b[1];});
var toRemove=entries.length-MAX_COOCCURRENCE;
for(var i=0;i<toRemove;i++){
delete coData[entries[i][0]];
}
}
await store.setItem('cooccurrence',coData);
}catch(error){
dashboardTagLogger.error('Error recording co-occurrence:',error);
}
}
async function getCoOccurrence(limit){
limit=limit||20;
try{
var coData=(await store.getItem('cooccurrence'))||{};
var entries=Object.entries(coData);
entries.sort(function(a,b){return b[1]-a[1];});
return entries.slice(0,limit).map(function(entry){
var tags=entry[0].split('|||');
return{tag1:tags[0],tag2:tags[1],count:entry[1]};
});
}catch(error){
dashboardTagLogger.error('Error getting co-occurrence:',error);
return[];
}
}
async function getTopTags(limit){
limit=limit||20;
try{
var frequencies=await getAllFrequencies();
var tagList=Object.entries(frequencies);
tagList.sort(function(a,b){return b[1].count-a[1].count;});
return tagList.slice(0,limit).map(function(entry){
return{
tag:entry[0],
count:entry[1].count,
lastUsed:entry[1].lastUsed,
};
});
}catch(error){
dashboardTagLogger.error('Error getting top tags:',error);
return[];
}
}
async function getStats(){
try{
var frequencies=await getAllFrequencies();
var tagList=Object.entries(frequencies);
if(tagList.length===0){
return{
totalUniqueTags:0,
totalUsage:0,
avgUsagePerTag:0,
};
}
var totalUsage=tagList.reduce(function(sum,entry){return sum+entry[1].count;},0);
return{
totalUniqueTags:tagList.length,
totalUsage:totalUsage,
avgUsagePerTag:Math.round((totalUsage/tagList.length)*10)/10,
};
}catch(error){
dashboardTagLogger.error('Error getting stats:',error);
return{
totalUniqueTags:0,
totalUsage:0,
avgUsagePerTag:0,
};
}
}
async function clearAll(){
try{
await store.removeItem('frequencies');
await store.removeItem('cooccurrence');
return true;
}catch(error){
dashboardTagLogger.error('Error clearing frequencies:',error);
return false;
}
}
async function searchTags(query,limit){
limit=limit||10;
try{
var frequencies=await getAllFrequencies();
var queryLower=query.toLowerCase();
var matches=Object.entries(frequencies)
.filter(function(entry){return entry[0].includes(queryLower);})
.sort(function(a,b){return b[1].count-a[1].count;})
.slice(0,limit)
.map(function(entry){
return{
tag:entry[0],
count:entry[1].count,
};
});
return matches;
}catch(error){
dashboardTagLogger.error('Error searching tags:',error);
return[];
}
}
return{
recordPrompt:recordPrompt,
getAllFrequencies:getAllFrequencies,
getTopTags:getTopTags,
getStats:getStats,
clearAll:clearAll,
searchTags:searchTags,
parsePrompt:parsePrompt,
getCoOccurrence:getCoOccurrence,
};
})();
