// パフォーマンス統計のlocalforage永続化
var dashboardPerfLogger=new SimpleLogger('dashboard-perf',LogLevel.DEBUG);
var PerformanceStorage=(function(){
var store=localforage.createInstance({
name:'MangaEditor_Performance',
storeName:'performanceStats',
});
var historyStore=localforage.createInstance({
name:'MangaEditor_Performance',
storeName:'generationHistory',
});
var timeStore=localforage.createInstance({
name:'MangaEditor_Performance',
storeName:'timeBasedStats',
});
var MODES=['T2I','I2I','I2I_Angle','Inpaint','Upscaler','Rembg'];
var MAX_HISTORY_PER_MODE=100;
var MAX_DAILY_RECORDS=90;
function getDefaultStats(){
return{
count:0,
totalTime:0,
avg:0,
min:null,
max:null,
lastUpdated:null,
};
}
async function getStats(mode){
try{
var stats=await store.getItem('stats_'+mode);
return stats||getDefaultStats();
}catch(error){
dashboardPerfLogger.error('Error getting stats:',error);
return getDefaultStats();
}
}
async function getAllStats(){
var allStats={};
for(var i=0;i<MODES.length;i++){
allStats[MODES[i]]=await getStats(MODES[i]);
}
return allStats;
}
async function recordTime(mode,timeMs){
try{
var stats=await getStats(mode);
var now=Date.now();
stats.count+=1;
stats.totalTime+=timeMs;
stats.avg=Math.round(stats.totalTime/stats.count);
stats.min=stats.min===null?timeMs:Math.min(stats.min,timeMs);
stats.max=stats.max===null?timeMs:Math.max(stats.max,timeMs);
stats.lastUpdated=now;
await store.setItem('stats_'+mode,stats);
await addToHistory(mode,timeMs);
await recordHourlyStats(now);
await recordDailyStats(now);
return stats;
}catch(error){
dashboardPerfLogger.error('Error recording time:',error);
return null;
}
}
async function addToHistory(mode,timeMs){
try{
var history=(await historyStore.getItem('history_'+mode))||[];
history.push({
time:timeMs,
timestamp:Date.now(),
});
if(history.length>MAX_HISTORY_PER_MODE){
history=history.slice(-MAX_HISTORY_PER_MODE);
}
await historyStore.setItem('history_'+mode,history);
return history;
}catch(error){
dashboardPerfLogger.error('Error adding to history:',error);
return[];
}
}
async function recordHourlyStats(timestamp){
try{
var date=new Date(timestamp);
var hour=date.getHours();
var dayOfWeek=date.getDay();
var hourlyData=(await timeStore.getItem('hourlyStats'))||{};
if(!hourlyData[dayOfWeek]){
hourlyData[dayOfWeek]={};
}
if(!hourlyData[dayOfWeek][hour]){
hourlyData[dayOfWeek][hour]=0;
}
hourlyData[dayOfWeek][hour]+=1;
await timeStore.setItem('hourlyStats',hourlyData);
return hourlyData;
}catch(error){
dashboardPerfLogger.error('Error recording hourly stats:',error);
return{};
}
}
async function getHourlyStats(){
try{
return(await timeStore.getItem('hourlyStats'))||{};
}catch(error){
dashboardPerfLogger.error('Error getting hourly stats:',error);
return{};
}
}
async function recordDailyStats(timestamp){
try{
var date=new Date(timestamp);
var dateKey=date.getFullYear()+'-'+String(date.getMonth()+1).padStart(2,'0')+'-'+String(date.getDate()).padStart(2,'0');
var dailyData=(await timeStore.getItem('dailyStats'))||{};
if(!dailyData[dateKey]){
dailyData[dateKey]=0;
}
dailyData[dateKey]+=1;
var keys=Object.keys(dailyData).sort();
if(keys.length>MAX_DAILY_RECORDS){
var toRemove=keys.slice(0,keys.length-MAX_DAILY_RECORDS);
toRemove.forEach(function(key){delete dailyData[key];});
}
await timeStore.setItem('dailyStats',dailyData);
return dailyData;
}catch(error){
dashboardPerfLogger.error('Error recording daily stats:',error);
return{};
}
}
async function getDailyStats(){
try{
return(await timeStore.getItem('dailyStats'))||{};
}catch(error){
dashboardPerfLogger.error('Error getting daily stats:',error);
return{};
}
}
async function getWeeklyStats(){
try{
var dailyData=await getDailyStats();
var weeklyData={};
Object.entries(dailyData).forEach(function(entry){
var dateKey=entry[0];
var count=entry[1];
var date=new Date(dateKey);
var day=date.getDay();
var diff=date.getDate()-day+(day===0?-6:1);
var monday=new Date(date.setDate(diff));
var weekKey=monday.getFullYear()+'-'+String(monday.getMonth()+1).padStart(2,'0')+'-'+String(monday.getDate()).padStart(2,'0');
if(!weeklyData[weekKey]){
weeklyData[weekKey]=0;
}
weeklyData[weekKey]+=count;
});
return weeklyData;
}catch(error){
dashboardPerfLogger.error('Error getting weekly stats:',error);
return{};
}
}
async function getMonthlyStats(){
try{
var dailyData=await getDailyStats();
var monthlyData={};
Object.entries(dailyData).forEach(function(entry){
var monthKey=entry[0].substring(0,7);
if(!monthlyData[monthKey]){
monthlyData[monthKey]=0;
}
monthlyData[monthKey]+=entry[1];
});
return monthlyData;
}catch(error){
dashboardPerfLogger.error('Error getting monthly stats:',error);
return{};
}
}
async function getHistory(mode){
try{
return(await historyStore.getItem('history_'+mode))||[];
}catch(error){
dashboardPerfLogger.error('Error getting history:',error);
return[];
}
}
async function getAllHistory(){
var allHistory={};
for(var i=0;i<MODES.length;i++){
allHistory[MODES[i]]=await getHistory(MODES[i]);
}
return allHistory;
}
async function clearStats(mode){
try{
await store.removeItem('stats_'+mode);
await historyStore.removeItem('history_'+mode);
return true;
}catch(error){
dashboardPerfLogger.error('Error clearing stats:',error);
return false;
}
}
async function clearAllStats(){
try{
for(var i=0;i<MODES.length;i++){
await clearStats(MODES[i]);
}
await timeStore.removeItem('hourlyStats');
await timeStore.removeItem('dailyStats');
await store.removeItem('launchInfo');
return true;
}catch(error){
dashboardPerfLogger.error('Error clearing all stats:',error);
return false;
}
}
async function recordLaunch(){
try{
var now=Date.now();
var launchInfo=await store.getItem('launchInfo');
if(!launchInfo){
launchInfo={
count:0,
firstLaunchDate:now,
lastLaunchDate:now,
};
}
launchInfo.count+=1;
launchInfo.lastLaunchDate=now;
await store.setItem('launchInfo',launchInfo);
return launchInfo;
}catch(error){
dashboardPerfLogger.error('Error recording launch:',error);
return null;
}
}
async function getLaunchInfo(){
try{
var launchInfo=await store.getItem('launchInfo');
return launchInfo||{
count:0,
firstLaunchDate:null,
lastLaunchDate:null,
};
}catch(error){
dashboardPerfLogger.error('Error getting launch info:',error);
return{
count:0,
firstLaunchDate:null,
lastLaunchDate:null,
};
}
}
async function getSummary(){
var allStats=await getAllStats();
var totalCount=0;
var totalTime=0;
var globalMin=null;
var globalMax=null;
for(var i=0;i<MODES.length;i++){
var stats=allStats[MODES[i]];
totalCount+=stats.count;
totalTime+=stats.totalTime;
if(stats.min!==null){
globalMin=globalMin===null?stats.min:Math.min(globalMin,stats.min);
}
if(stats.max!==null){
globalMax=globalMax===null?stats.max:Math.max(globalMax,stats.max);
}
}
return{
totalCount:totalCount,
totalTime:totalTime,
globalAvg:totalCount>0?Math.round(totalTime/totalCount):0,
globalMin:globalMin,
globalMax:globalMax,
};
}
return{
MODES:MODES,
getStats:getStats,
getAllStats:getAllStats,
recordTime:recordTime,
getHistory:getHistory,
getAllHistory:getAllHistory,
getHourlyStats:getHourlyStats,
getDailyStats:getDailyStats,
getWeeklyStats:getWeeklyStats,
getMonthlyStats:getMonthlyStats,
clearStats:clearStats,
clearAllStats:clearAllStats,
getSummary:getSummary,
recordLaunch:recordLaunch,
getLaunchInfo:getLaunchInfo,
};
})();
PerformanceStorage.recordLaunch();
