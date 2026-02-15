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
var MAX_DAILY_RECORDS=365;
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
async function recordTime(mode,timeMs,promptLength){
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
await addToHistory(mode,timeMs,promptLength);
await recordHourlyStats(now);
await recordDailyStats(now);
return stats;
}catch(error){
dashboardPerfLogger.error('Error recording time:',error);
return null;
}
}
async function addToHistory(mode,timeMs,promptLength){
try{
var history=(await historyStore.getItem('history_'+mode))||[];
var entry={
time:timeMs,
timestamp:Date.now(),
};
if(promptLength!==undefined&&promptLength!==null){
entry.promptLength=promptLength;
}
history.push(entry);
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
await timeStore.removeItem('failureStats');
await store.removeItem('modelStats');
await timeStore.removeItem('sessionSummary');
await timeStore.removeItem('currentSession');
await store.removeItem('goals');
await timeStore.removeItem('longestStreak');
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
function getDateKey(date){
return date.getFullYear()+'-'+String(date.getMonth()+1).padStart(2,'0')+'-'+String(date.getDate()).padStart(2,'0');
}
async function getStreak(){
try{
var dailyData=await getDailyStats();
var keys=Object.keys(dailyData).sort().reverse();
var currentStreak=0;
var today=new Date();
today.setHours(0,0,0,0);
var checkDate=new Date(today);
var todayKey=getDateKey(today);
var todayCount=dailyData[todayKey]||0;
if(dailyData[todayKey]){
currentStreak=1;
checkDate.setDate(checkDate.getDate()-1);
}else{
checkDate.setDate(checkDate.getDate()-1);
var yesterdayKey=getDateKey(checkDate);
if(!dailyData[yesterdayKey]){
var longestStreak=(await timeStore.getItem('longestStreak'))||0;
return{currentStreak:0,longestStreak:longestStreak,todayCount:todayCount};
}
currentStreak=1;
checkDate.setDate(checkDate.getDate()-1);
}
for(var i=0;i<366;i++){
var key=getDateKey(checkDate);
if(dailyData[key]){
currentStreak++;
checkDate.setDate(checkDate.getDate()-1);
}else{
break;
}
}
var longestStreak=(await timeStore.getItem('longestStreak'))||0;
if(currentStreak>longestStreak){
longestStreak=currentStreak;
await timeStore.setItem('longestStreak',longestStreak);
}
return{currentStreak:currentStreak,longestStreak:longestStreak,todayCount:todayCount};
}catch(error){
dashboardPerfLogger.error('Error getting streak:',error);
return{currentStreak:0,longestStreak:0,todayCount:0};
}
}
async function recordFailure(mode){
try{
var failureStats=(await timeStore.getItem('failureStats'))||{};
if(!failureStats[mode]){
failureStats[mode]={count:0,lastFailure:null};
}
failureStats[mode].count+=1;
failureStats[mode].lastFailure=Date.now();
await timeStore.setItem('failureStats',failureStats);
return failureStats;
}catch(error){
dashboardPerfLogger.error('Error recording failure:',error);
return null;
}
}
async function getFailureStats(){
try{
return(await timeStore.getItem('failureStats'))||{};
}catch(error){
dashboardPerfLogger.error('Error getting failure stats:',error);
return{};
}
}
async function getSuccessRate(){
try{
var allStats=await getAllStats();
var failureStats=await getFailureStats();
var totalSuccess=0;
var totalFailure=0;
for(var i=0;i<MODES.length;i++){
totalSuccess+=allStats[MODES[i]].count;
var fs=failureStats[MODES[i]];
if(fs) totalFailure+=fs.count;
}
var total=totalSuccess+totalFailure;
return{
totalSuccess:totalSuccess,
totalFailure:totalFailure,
total:total,
rate:total>0?Math.round((totalSuccess/total)*1000)/10:0,
};
}catch(error){
dashboardPerfLogger.error('Error getting success rate:',error);
return{totalSuccess:0,totalFailure:0,total:0,rate:0};
}
}
async function startSession(){
try{
var now=Date.now();
var currentSession={
startTime:now,
generationCount:0,
};
await timeStore.setItem('currentSession',currentSession);
return currentSession;
}catch(error){
dashboardPerfLogger.error('Error starting session:',error);
return null;
}
}
async function recordSessionGeneration(){
try{
var currentSession=await timeStore.getItem('currentSession');
if(!currentSession) return;
currentSession.generationCount+=1;
await timeStore.setItem('currentSession',currentSession);
}catch(error){
dashboardPerfLogger.error('Error recording session generation:',error);
}
}
async function endSession(){
try{
var currentSession=await timeStore.getItem('currentSession');
if(!currentSession) return;
var duration=Date.now()-currentSession.startTime;
var summary=(await timeStore.getItem('sessionSummary'))||{
totalSessions:0,
totalDuration:0,
totalGenerations:0,
};
summary.totalSessions+=1;
summary.totalDuration+=duration;
summary.totalGenerations+=currentSession.generationCount;
await timeStore.setItem('sessionSummary',summary);
await timeStore.removeItem('currentSession');
}catch(error){
dashboardPerfLogger.error('Error ending session:',error);
}
}
async function getSessionStats(){
try{
var currentSession=await timeStore.getItem('currentSession');
var summary=(await timeStore.getItem('sessionSummary'))||{
totalSessions:0,
totalDuration:0,
totalGenerations:0,
};
var currentDuration=currentSession?(Date.now()-currentSession.startTime):0;
var currentGenCount=currentSession?currentSession.generationCount:0;
var avgSessionDuration=summary.totalSessions>0?Math.round(summary.totalDuration/summary.totalSessions):0;
var avgGenPerSession=summary.totalSessions>0?Math.round((summary.totalGenerations/summary.totalSessions)*10)/10:0;
return{
currentDuration:currentDuration,
currentGenCount:currentGenCount,
avgSessionDuration:avgSessionDuration,
avgGenPerSession:avgGenPerSession,
totalSessions:summary.totalSessions,
};
}catch(error){
dashboardPerfLogger.error('Error getting session stats:',error);
return{currentDuration:0,currentGenCount:0,avgSessionDuration:0,avgGenPerSession:0,totalSessions:0};
}
}
async function recordModel(modelName){
try{
if(!modelName) return null;
var modelStats=(await store.getItem('modelStats'))||{};
if(!modelStats[modelName]){
modelStats[modelName]={count:0,lastUsed:null};
}
modelStats[modelName].count+=1;
modelStats[modelName].lastUsed=Date.now();
await store.setItem('modelStats',modelStats);
return modelStats;
}catch(error){
dashboardPerfLogger.error('Error recording model:',error);
return null;
}
}
async function getModelStats(){
try{
var modelStats=(await store.getItem('modelStats'))||{};
var list=Object.entries(modelStats);
list.sort(function(a,b){return b[1].count-a[1].count;});
return list.map(function(entry){
return{name:entry[0],count:entry[1].count,lastUsed:entry[1].lastUsed};
});
}catch(error){
dashboardPerfLogger.error('Error getting model stats:',error);
return[];
}
}
async function setGoal(type,target){
try{
var goals=(await store.getItem('goals'))||{};
goals[type]={target:target,updatedAt:Date.now()};
await store.setItem('goals',goals);
return goals;
}catch(error){
dashboardPerfLogger.error('Error setting goal:',error);
return null;
}
}
async function getGoal(){
try{
return(await store.getItem('goals'))||{};
}catch(error){
dashboardPerfLogger.error('Error getting goal:',error);
return{};
}
}
async function getGoalProgress(){
try{
var goals=await getGoal();
var dailyData=await getDailyStats();
var today=new Date();
var todayKey=getDateKey(today);
var todayCount=dailyData[todayKey]||0;
var weekCount=0;
var weekStart=new Date(today);
weekStart.setDate(weekStart.getDate()-weekStart.getDay());
weekStart.setHours(0,0,0,0);
Object.entries(dailyData).forEach(function(entry){
var d=new Date(entry[0]);
if(d>=weekStart) weekCount+=entry[1];
});
var dailyGoal=goals.daily?goals.daily.target:0;
var weeklyGoal=goals.weekly?goals.weekly.target:0;
return{
daily:{current:todayCount,target:dailyGoal,percent:dailyGoal>0?Math.min(100,Math.round((todayCount/dailyGoal)*100)):0},
weekly:{current:weekCount,target:weeklyGoal,percent:weeklyGoal>0?Math.min(100,Math.round((weekCount/weeklyGoal)*100)):0},
};
}catch(error){
dashboardPerfLogger.error('Error getting goal progress:',error);
return{daily:{current:0,target:0,percent:0},weekly:{current:0,target:0,percent:0}};
}
}
async function getCalendarData(){
try{
return await getDailyStats();
}catch(error){
dashboardPerfLogger.error('Error getting calendar data:',error);
return{};
}
}
async function exportAllData(){
try{
var allStats=await getAllStats();
var allHistory=await getAllHistory();
var hourlyStats=await getHourlyStats();
var dailyStats=await getDailyStats();
var launchInfo=await getLaunchInfo();
var summary=await getSummary();
var failureStats=await getFailureStats();
var successRate=await getSuccessRate();
var modelStats=await getModelStats();
var sessionStats=await getSessionStats();
var streak=await getStreak();
var goals=await getGoal();
var goalProgress=await getGoalProgress();
var tagFrequencies=await PromptFrequencyStorage.getAllFrequencies();
var tagStats=await PromptFrequencyStorage.getStats();
var coOccurrence=await PromptFrequencyStorage.getCoOccurrence(50);
return{
exportDate:new Date().toISOString(),
stats:allStats,
history:allHistory,
hourlyStats:hourlyStats,
dailyStats:dailyStats,
launchInfo:launchInfo,
summary:summary,
failureStats:failureStats,
successRate:successRate,
modelStats:modelStats,
sessionStats:sessionStats,
streak:streak,
goals:goals,
goalProgress:goalProgress,
tagFrequencies:tagFrequencies,
tagStats:tagStats,
coOccurrence:coOccurrence,
};
}catch(error){
dashboardPerfLogger.error('Error exporting data:',error);
return null;
}
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
getStreak:getStreak,
recordFailure:recordFailure,
getFailureStats:getFailureStats,
getSuccessRate:getSuccessRate,
startSession:startSession,
recordSessionGeneration:recordSessionGeneration,
endSession:endSession,
getSessionStats:getSessionStats,
recordModel:recordModel,
getModelStats:getModelStats,
setGoal:setGoal,
getGoal:getGoal,
getGoalProgress:getGoalProgress,
getCalendarData:getCalendarData,
exportAllData:exportAllData,
};
})();
PerformanceStorage.recordLaunch();
PerformanceStorage.startSession();
window.addEventListener('beforeunload',function(){
PerformanceStorage.endSession();
});
