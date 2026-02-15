// ダッシュボードUIコンポーネント（モーダル表示）
var dashboardLogger=new SimpleLogger('dashboard',LogLevel.DEBUG);
var DashboardUI=(function(){
var isInitialized=false;
var isOpen=false;
var generationTimeChart=null;
var trendChart=null;
var successRateChart=null;
var promptLengthChart=null;
var modelChart=null;
var currentChartMode='T2I';
var currentTrendPeriod='daily';
var wordcloudResizeObserver=null;
var MODE_LABELS={
T2I:'T2I',
I2I:'I2I',
I2I_Angle:'I2I Angle',
Inpaint:'Inpaint',
Upscaler:'Upscaler',
Rembg:'Rembg',
};
var MODE_COLORS_DARK={
T2I:'#00bcd4',
I2I:'#ff9800',
I2I_Angle:'#9c27b0',
Inpaint:'#e91e63',
Upscaler:'#607d8b',
Rembg:'#4caf50',
};
var MODE_COLORS_LIGHT={
T2I:'#0097a7',
I2I:'#f57c00',
I2I_Angle:'#7b1fa2',
Inpaint:'#c2185b',
Upscaler:'#455a64',
Rembg:'#388e3c',
};
var DAY_LABELS=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
var MONTH_LABELS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
var WORDCLOUD_COLORS_DARK=['#00bcd4','#4caf50','#ff9800','#e91e63','#9c27b0','#607d8b','#03a9f4','#8bc34a'];
var WORDCLOUD_COLORS_LIGHT=['#0097a7','#388e3c','#f57c00','#c2185b','#7b1fa2','#455a64','#0288d1','#689f38'];
var BADGES=[
{id:'gen10',icon:'\u2B50',key:'dashboardBadge10Gen',check:function(d){return d.summary.totalCount>=10;}},
{id:'gen50',icon:'\u2B50',key:'dashboardBadge50Gen',check:function(d){return d.summary.totalCount>=50;}},
{id:'gen100',icon:'\u1F31F',key:'dashboardBadge100Gen',check:function(d){return d.summary.totalCount>=100;}},
{id:'gen500',icon:'\u1F48E',key:'dashboardBadge500Gen',check:function(d){return d.summary.totalCount>=500;}},
{id:'gen1000',icon:'\u1F451',key:'dashboardBadge1000Gen',check:function(d){return d.summary.totalCount>=1000;}},
{id:'streak7',icon:'\u1F525',key:'dashboardBadge7Streak',check:function(d){return d.streak.longestStreak>=7;}},
{id:'streak30',icon:'\u1F525',key:'dashboardBadge30Streak',check:function(d){return d.streak.longestStreak>=30;}},
{id:'streak100',icon:'\u1F525',key:'dashboardBadge100Streak',check:function(d){return d.streak.longestStreak>=100;}},
{id:'tags10',icon:'\u1F3F7',key:'dashboardBadge10Tags',check:function(d){return d.tagStats.totalUniqueTags>=10;}},
{id:'tags50',icon:'\u1F3F7',key:'dashboardBadge50Tags',check:function(d){return d.tagStats.totalUniqueTags>=50;}},
{id:'tags100',icon:'\u1F3F7',key:'dashboardBadge100Tags',check:function(d){return d.tagStats.totalUniqueTags>=100;}},
{id:'launch10',icon:'\u1F680',key:'dashboardBadge10Launch',check:function(d){return d.launchInfo.count>=10;}},
{id:'launch50',icon:'\u1F680',key:'dashboardBadge50Launch',check:function(d){return d.launchInfo.count>=50;}},
{id:'modeT2I',icon:'\u1F5BC',key:'dashboardBadgeT2I',check:function(d){return d.allStats.T2I&&d.allStats.T2I.count>=1;}},
{id:'modeI2I',icon:'\u1F504',key:'dashboardBadgeI2I',check:function(d){return d.allStats.I2I&&d.allStats.I2I.count>=1;}},
{id:'modeAngle',icon:'\u1F4D0',key:'dashboardBadgeAngle',check:function(d){return d.allStats.I2I_Angle&&d.allStats.I2I_Angle.count>=1;}},
{id:'modeInpaint',icon:'\u1F58C',key:'dashboardBadgeInpaint',check:function(d){return d.allStats.Inpaint&&d.allStats.Inpaint.count>=1;}},
{id:'modeUpscaler',icon:'\u1F50D',key:'dashboardBadgeUpscaler',check:function(d){return d.allStats.Upscaler&&d.allStats.Upscaler.count>=1;}},
{id:'modeRembg',icon:'\u2702',key:'dashboardBadgeRembg',check:function(d){return d.allStats.Rembg&&d.allStats.Rembg.count>=1;}},
{id:'time1h',icon:'\u23F0',key:'dashboardBadge1hTime',check:function(d){return d.summary.totalTime>=3600000;}},
];
function getTheme(){
return document.body.classList.contains('dark-mode')?'dark':'light';
}
function getThemeColors(){
if(getTheme()==='light'){
return{
modeColors:MODE_COLORS_LIGHT,
gridColor:'rgba(0,0,0,0.05)',
textColor:'#999999',
bgColor:'#ffffff',
bgSecondary:'#f5f5f5',
accentColor:'#0097a7',
barColor:'#0097a7',
};
}
return{
modeColors:MODE_COLORS_DARK,
gridColor:'rgba(255,255,255,0.08)',
textColor:'#888888',
bgColor:'#1a1a1a',
bgSecondary:'#2a2a2a',
accentColor:'#00bcd4',
barColor:'#00bcd4',
};
}
function getWordcloudColors(){
if(getTheme()==='light') return WORDCLOUD_COLORS_LIGHT;
return WORDCLOUD_COLORS_DARK;
}
function open(){
if(isOpen) return;
isOpen=true;
var modal=document.getElementById('dashboard-modal');
if(modal) modal.style.display='flex';
init();
dashboardLogger.debug("Dashboard opened");
}
function close(){
if(!isOpen) return;
isOpen=false;
var modal=document.getElementById('dashboard-modal');
if(modal) modal.style.display='none';
if(generationTimeChart){
generationTimeChart.destroy();
generationTimeChart=null;
}
if(trendChart){
trendChart.destroy();
trendChart=null;
}
if(successRateChart){
successRateChart.destroy();
successRateChart=null;
}
if(promptLengthChart){
promptLengthChart.destroy();
promptLengthChart=null;
}
if(modelChart){
modelChart.destroy();
modelChart=null;
}
dashboardLogger.debug("Dashboard closed");
}
async function init(){
if(isInitialized){
await refresh();
return;
}
setupEventListeners();
await refresh();
isInitialized=true;
}
function setupEventListeners(){
var modeSelector=document.getElementById('dashboardModeSelector');
if(modeSelector){
modeSelector.addEventListener('change',async function(e){
currentChartMode=e.target.value;
await refreshGenerationTimeChart();
});
}
var trendSelector=document.getElementById('dashboardTrendSelector');
if(trendSelector){
trendSelector.addEventListener('change',async function(e){
currentTrendPeriod=e.target.value;
await refreshTrendChart();
});
}
var clearBtn=document.getElementById('dashboardClearStats');
if(clearBtn){
clearBtn.addEventListener('click',async function(){
if(confirm(getText('dashboardConfirmClear'))){
await PerformanceStorage.clearAllStats();
await PromptFrequencyStorage.clearAll();
await refresh();
}
});
}
var clearTagsBtn=document.getElementById('dashboardClearTags');
if(clearTagsBtn){
clearTagsBtn.addEventListener('click',async function(){
if(confirm(getText('dashboardConfirmClearTags'))){
await PromptFrequencyStorage.clearAll();
await refreshTopTags();
await refreshWordcloud();
await refreshStats();
}
});
}
var downloadBtn=document.getElementById('dashboardDownloadWordcloud');
if(downloadBtn){
downloadBtn.addEventListener('click',downloadWordcloud);
}
var wordcloudCanvas=document.getElementById('dashboardWordcloud');
if(wordcloudCanvas&&wordcloudCanvas.parentElement){
var resizeTimeout;
wordcloudResizeObserver=new ResizeObserver(function(){
clearTimeout(resizeTimeout);
resizeTimeout=setTimeout(function(){refreshWordcloud();},300);
});
wordcloudResizeObserver.observe(wordcloudCanvas.parentElement);
}
var closeBtn=document.getElementById('dashboard-close-btn');
if(closeBtn){
closeBtn.addEventListener('click',close);
}
var modal=document.getElementById('dashboard-modal');
if(modal){
modal.addEventListener('click',function(e){
if(e.target===modal) close();
});
}
var saveDailyBtn=document.getElementById('dashboardSaveDailyGoal');
if(saveDailyBtn){
saveDailyBtn.addEventListener('click',async function(){
var input=document.getElementById('dashboardDailyGoalInput');
var val=parseInt(input.value,10);
if(val>0){
await PerformanceStorage.setGoal('daily',val);
await refreshGoals();
}
});
}
var saveWeeklyBtn=document.getElementById('dashboardSaveWeeklyGoal');
if(saveWeeklyBtn){
saveWeeklyBtn.addEventListener('click',async function(){
var input=document.getElementById('dashboardWeeklyGoalInput');
var val=parseInt(input.value,10);
if(val>0){
await PerformanceStorage.setGoal('weekly',val);
await refreshGoals();
}
});
}
var exportJSONBtn=document.getElementById('dashboardExportJSON');
if(exportJSONBtn){
exportJSONBtn.addEventListener('click',exportJSON);
}
var exportCSVBtn=document.getElementById('dashboardExportCSV');
if(exportCSVBtn){
exportCSVBtn.addEventListener('click',exportCSV);
}
}
async function refresh(){
await Promise.all([
refreshStats(),
refreshGenerationTimeChart(),
refreshHeatmap(),
refreshTrendChart(),
refreshTopTags(),
refreshWordcloud(),
refreshStreak(),
refreshSessionStats(),
refreshCalendar(),
refreshSuccessRate(),
refreshPromptLengthChart(),
refreshCoOccurrence(),
refreshModelStats(),
refreshGoals(),
refreshBadges(),
]);
}
function formatDate(timestamp){
if(!timestamp) return '-';
var date=new Date(timestamp);
return date.toLocaleDateString();
}
function formatDuration(ms){
var minutes=Math.floor(ms/60000);
var hours=Math.floor(minutes/60);
if(hours>0) return hours+'h '+minutes%60+'m';
return minutes+'m';
}
async function refreshStats(){
var allStats=await PerformanceStorage.getAllStats();
var summary=await PerformanceStorage.getSummary();
var tagStats=await PromptFrequencyStorage.getStats();
var launchInfo=await PerformanceStorage.getLaunchInfo();
updateElement('dashboardTotalGenerations',summary.totalCount.toLocaleString());
updateElement('dashboardGlobalAvg',summary.globalAvg?summary.globalAvg+' ms':'-');
updateElement('dashboardGlobalMin',summary.globalMin?summary.globalMin+' ms':'-');
updateElement('dashboardGlobalMax',summary.globalMax?summary.globalMax+' ms':'-');
updateElement('dashboardUniqueTags',tagStats.totalUniqueTags.toLocaleString());
updateElement('dashboardLaunchCount',launchInfo.count.toLocaleString());
updateElement('dashboardFirstLaunch',formatDate(launchInfo.firstLaunchDate));
var tableBody=document.getElementById('dashboardStatsTable');
if(tableBody){
var html='';
for(var i=0;i<PerformanceStorage.MODES.length;i++){
var mode=PerformanceStorage.MODES[i];
var stats=allStats[mode];
html+='<tr>';
html+='<td>'+MODE_LABELS[mode]+'</td>';
html+='<td>'+stats.count.toLocaleString()+'</td>';
html+='<td>'+(stats.avg?stats.avg.toLocaleString():'-')+'</td>';
html+='<td>'+(stats.min!==null?stats.min.toLocaleString():'-')+'</td>';
html+='<td>'+(stats.max!==null?stats.max.toLocaleString():'-')+'</td>';
html+='</tr>';
}
tableBody.innerHTML=html;
}
}
async function refreshGenerationTimeChart(){
var canvas=document.getElementById('dashboardChart');
if(!canvas) return;
var history=await PerformanceStorage.getHistory(currentChartMode);
var themeColors=getThemeColors();
var color=themeColors.accentColor;
if(generationTimeChart){
generationTimeChart.destroy();
}
var labels=history.map(function(_,i){return i+1;});
var data=history.map(function(h){return h.time;});
generationTimeChart=new Chart(canvas,{
type:'line',
data:{
labels:labels,
datasets:[{
label:getText('dashboardGenTime')||'Generation Time (ms)',
data:data,
borderColor:color,
backgroundColor:color+'20',
fill:true,
tension:0.3,
pointRadius:3,
pointHoverRadius:5,
}],
},
options:{
responsive:true,
maintainAspectRatio:false,
plugins:{
legend:{display:false},
tooltip:{
callbacks:{
label:function(context){return context.parsed.y+' ms';},
},
},
},
scales:{
x:{
display:true,
title:{
display:true,
text:getText('dashboardRecentGen')||'Recent Generations',
color:themeColors.textColor,
},
grid:{color:themeColors.gridColor},
ticks:{color:themeColors.textColor},
},
y:{
display:true,
title:{
display:true,
text:'ms',
color:themeColors.textColor,
},
grid:{color:themeColors.gridColor},
ticks:{color:themeColors.textColor},
},
},
},
});
}
async function refreshHeatmap(){
var container=document.getElementById('dashboardHeatmap');
if(!container) return;
var hourlyData=await PerformanceStorage.getHourlyStats();
var maxCount=0;
for(var day=0;day<7;day++){
for(var hour=0;hour<24;hour++){
var count=(hourlyData[day]&&hourlyData[day][hour])||0;
maxCount=Math.max(maxCount,count);
}
}
var html='<div class="heatmap-grid">';
html+='<div class="heatmap-row heatmap-header">';
html+='<div class="heatmap-label"></div>';
for(var hour=0;hour<24;hour++){
html+='<div class="heatmap-hour">'+hour+'</div>';
}
html+='</div>';
for(var day=0;day<7;day++){
html+='<div class="heatmap-row">';
html+='<div class="heatmap-label">'+(getText('dashboardDay'+day)||DAY_LABELS[day])+'</div>';
for(var hour=0;hour<24;hour++){
var count=(hourlyData[day]&&hourlyData[day][hour])||0;
var intensity=maxCount>0?count/maxCount:0;
var bgColor=getHeatmapColor(intensity);
var dayLabel=getText('dashboardDay'+day)||DAY_LABELS[day];
html+='<div class="heatmap-cell" style="background-color:'+bgColor+'" title="'+dayLabel+' '+hour+':00 - '+count+' '+(getText('dashboardGenerations')||'generations')+'"></div>';
}
html+='</div>';
}
html+='</div>';
container.innerHTML=html;
}
function getHeatmapColor(intensity){
if(getTheme()==='light'){
if(intensity===0) return '#e8e8e8';
var r=Math.round(200-intensity*200);
var g=Math.round(220-intensity*69);
var b=Math.round(220-intensity*53);
return 'rgb('+r+','+g+','+b+')';
}
if(intensity===0) return '#2a2a2a';
var r=Math.round(30+intensity*0);
var g=Math.round(50+intensity*138);
var b=Math.round(60+intensity*152);
return 'rgb('+r+','+g+','+b+')';
}
function getCalendarColor(intensity){
if(getTheme()==='light'){
if(intensity===0) return '#e8e8e8';
if(intensity<0.25) return '#c6e48b';
if(intensity<0.5) return '#7bc96f';
if(intensity<0.75) return '#239a3b';
return '#196127';
}
if(intensity===0) return '#2a2a2a';
if(intensity<0.25) return '#0e4429';
if(intensity<0.5) return '#006d32';
if(intensity<0.75) return '#26a641';
return '#39d353';
}
async function refreshTrendChart(){
var canvas=document.getElementById('dashboardTrendChart');
if(!canvas) return;
var themeColors=getThemeColors();
var data;
var labels;
var chartLabel;
if(currentTrendPeriod==='daily'){
var dailyData=await PerformanceStorage.getDailyStats();
var sorted=Object.entries(dailyData).sort(function(a,b){return a[0].localeCompare(b[0]);});
labels=sorted.map(function(e){return e[0].substring(5);});
data=sorted.map(function(e){return e[1];});
chartLabel=getText('dashboardDaily')||'Daily';
}else if(currentTrendPeriod==='weekly'){
var weeklyData=await PerformanceStorage.getWeeklyStats();
var sorted=Object.entries(weeklyData).sort(function(a,b){return a[0].localeCompare(b[0]);});
labels=sorted.map(function(e){return e[0].substring(5);});
data=sorted.map(function(e){return e[1];});
chartLabel=getText('dashboardWeekly')||'Weekly';
}else{
var monthlyData=await PerformanceStorage.getMonthlyStats();
var sorted=Object.entries(monthlyData).sort(function(a,b){return a[0].localeCompare(b[0]);});
labels=sorted.map(function(e){return e[0];});
data=sorted.map(function(e){return e[1];});
chartLabel=getText('dashboardMonthly')||'Monthly';
}
if(trendChart){
trendChart.destroy();
}
trendChart=new Chart(canvas,{
type:'bar',
data:{
labels:labels,
datasets:[{
label:chartLabel,
data:data,
backgroundColor:themeColors.barColor+'80',
borderColor:themeColors.barColor,
borderWidth:1,
}],
},
options:{
responsive:true,
maintainAspectRatio:false,
plugins:{
legend:{display:false},
},
scales:{
x:{
display:true,
grid:{color:themeColors.gridColor},
ticks:{
color:themeColors.textColor,
maxRotation:45,
minRotation:45,
},
},
y:{
display:true,
beginAtZero:true,
title:{
display:true,
text:getText('dashboardCount')||'Count',
color:themeColors.textColor,
},
grid:{color:themeColors.gridColor},
ticks:{
color:themeColors.textColor,
stepSize:1,
},
},
},
},
});
}
async function refreshTopTags(){
var topTags=await PromptFrequencyStorage.getTopTags(15);
var container=document.getElementById('dashboardTopTags');
if(!container) return;
if(topTags.length===0){
container.innerHTML='<div class="no-tags">'+(getText('dashboardNoTags')||'No tags recorded')+'</div>';
return;
}
var maxCount=topTags[0]?topTags[0].count:1;
var gradientStart,gradientEnd;
if(getTheme()==='light'){
gradientStart='#0097a7';
gradientEnd='#4db6ac';
}else{
gradientStart='#00bcd4';
gradientEnd='#4caf50';
}
var html='';
topTags.forEach(function(item){
var percentage=Math.round((item.count/maxCount)*100);
html+='<div class="tag-item">';
html+='<div class="tag-info">';
html+='<span class="tag-name">'+escapeHtml(item.tag)+'</span>';
html+='<span class="tag-count">'+item.count+'</span>';
html+='</div>';
html+='<div class="tag-bar-container">';
html+='<div class="tag-bar" style="width:'+percentage+'%;background:linear-gradient(90deg,'+gradientStart+','+gradientEnd+')"></div>';
html+='</div>';
html+='</div>';
});
container.innerHTML=html;
}
async function refreshWordcloud(){
var canvas=document.getElementById('dashboardWordcloud');
if(!canvas||typeof WordCloud==='undefined') return;
var topTags=await PromptFrequencyStorage.getTopTags(100);
var themeColors=getThemeColors();
var wordcloudColors=getWordcloudColors();
var bgColor=themeColors.bgSecondary||themeColors.bgColor;
var dpr=window.devicePixelRatio||1;
var container=canvas.parentElement;
var cssWidth=container?container.getBoundingClientRect().width-16:canvas.width;
var cssHeight=300;
canvas.width=cssWidth*dpr;
canvas.height=cssHeight*dpr;
canvas.style.width=cssWidth+'px';
canvas.style.height=cssHeight+'px';
if(topTags.length===0){
var ctx=canvas.getContext('2d');
ctx.scale(dpr,dpr);
ctx.fillStyle=bgColor;
ctx.fillRect(0,0,cssWidth,cssHeight);
ctx.fillStyle=themeColors.textColor;
ctx.font='14px sans-serif';
ctx.textAlign='center';
ctx.fillText(getText('dashboardNoTags')||'No tags recorded',cssWidth/2,cssHeight/2);
return;
}
var maxCount=topTags[0]?topTags[0].count:1;
var minSize=12*dpr;
var maxSize=60*dpr;
var wordList=topTags.map(function(item){
var size=minSize+(item.count/maxCount)*(maxSize-minSize);
return[item.tag,size];
});
var ctx=canvas.getContext('2d');
ctx.fillStyle=bgColor;
ctx.fillRect(0,0,canvas.width,canvas.height);
WordCloud(canvas,{
list:wordList,
gridSize:Math.round(8*dpr),
weightFactor:1,
fontFamily:'sans-serif',
color:function(){
return wordcloudColors[Math.floor(Math.random()*wordcloudColors.length)];
},
backgroundColor:bgColor,
rotateRatio:0.3,
rotationSteps:2,
shuffle:true,
drawOutOfBound:false,
});
}
async function refreshStreak(){
var streak=await PerformanceStorage.getStreak();
updateElement('dashboardCurrentStreak',streak.currentStreak);
updateElement('dashboardLongestStreak',streak.longestStreak);
updateElement('dashboardTodayCount',streak.todayCount);
}
async function refreshSessionStats(){
var stats=await PerformanceStorage.getSessionStats();
updateElement('dashboardCurrentSession',formatDuration(stats.currentDuration));
updateElement('dashboardSessionGenCount',stats.currentGenCount);
updateElement('dashboardAvgSession',formatDuration(stats.avgSessionDuration));
updateElement('dashboardTotalSessions',stats.totalSessions);
}
async function refreshCalendar(){
var container=document.getElementById('dashboardCalendar');
if(!container) return;
var calendarData=await PerformanceStorage.getCalendarData();
var today=new Date();
today.setHours(0,0,0,0);
var startDate=new Date(today);
startDate.setFullYear(startDate.getFullYear()-1);
startDate.setDate(startDate.getDate()-startDate.getDay());
var maxCount=0;
var values=Object.values(calendarData);
for(var i=0;i<values.length;i++){
if(values[i]>maxCount) maxCount=values[i];
}
var weeks=[];
var currentDate=new Date(startDate);
while(currentDate<=today){
var week=[];
for(var d=0;d<7;d++){
if(currentDate<=today){
var key=currentDate.getFullYear()+'-'+String(currentDate.getMonth()+1).padStart(2,'0')+'-'+String(currentDate.getDate()).padStart(2,'0');
week.push({date:key,count:calendarData[key]||0,dateObj:new Date(currentDate)});
}else{
week.push(null);
}
currentDate.setDate(currentDate.getDate()+1);
}
weeks.push(week);
}
var dayLabels=['','Mon','','Wed','','Fri',''];
var html='<div class="calendar-wrap">';
html+='<div class="calendar-months">';
var lastMonth=-1;
for(var w=0;w<weeks.length;w++){
var firstDay=weeks[w][0]||weeks[w][1]||weeks[w][2];
if(firstDay){
var month=firstDay.dateObj.getMonth();
if(month!==lastMonth){
html+='<span class="calendar-month-label" style="width:'+13*1+'px">'+MONTH_LABELS[month]+'</span>';
lastMonth=month;
}else{
html+='<span class="calendar-month-label" style="width:13px"></span>';
}
}
}
html+='</div>';
html+='<div class="calendar-body">';
html+='<div class="calendar-day-labels">';
for(var d=0;d<7;d++){
html+='<div class="calendar-day-label">'+dayLabels[d]+'</div>';
}
html+='</div>';
html+='<div class="calendar-grid">';
for(var w=0;w<weeks.length;w++){
html+='<div class="calendar-week">';
for(var d=0;d<7;d++){
var cell=weeks[w][d];
if(cell){
var intensity=maxCount>0?cell.count/maxCount:0;
var color=getCalendarColor(intensity);
html+='<div class="calendar-cell" style="background-color:'+color+'" title="'+cell.date+': '+cell.count+'"></div>';
}else{
html+='<div class="calendar-cell-empty"></div>';
}
}
html+='</div>';
}
html+='</div>';
html+='</div>';
var lessText=getText('dashboardLess')||'Less';
var moreText=getText('dashboardMore')||'More';
html+='<div class="calendar-legend">';
html+='<span>'+lessText+'</span>';
html+='<div class="calendar-legend-cell" style="background-color:'+getCalendarColor(0)+'"></div>';
html+='<div class="calendar-legend-cell" style="background-color:'+getCalendarColor(0.1)+'"></div>';
html+='<div class="calendar-legend-cell" style="background-color:'+getCalendarColor(0.4)+'"></div>';
html+='<div class="calendar-legend-cell" style="background-color:'+getCalendarColor(0.7)+'"></div>';
html+='<div class="calendar-legend-cell" style="background-color:'+getCalendarColor(1)+'"></div>';
html+='<span>'+moreText+'</span>';
html+='</div>';
html+='</div>';
container.innerHTML=html;
}
async function refreshSuccessRate(){
var canvas=document.getElementById('dashboardSuccessRateChart');
if(!canvas) return;
var rate=await PerformanceStorage.getSuccessRate();
var themeColors=getThemeColors();
if(successRateChart){
successRateChart.destroy();
}
if(rate.total===0){
var ctx=canvas.getContext('2d');
ctx.clearRect(0,0,canvas.width,canvas.height);
ctx.fillStyle=themeColors.textColor;
ctx.font='13px sans-serif';
ctx.textAlign='center';
ctx.fillText(getText('dashboardNoData')||'No data available',canvas.width/2,canvas.height/2);
return;
}
var successLabel=getText('dashboardSuccess')||'Success';
var failureLabel=getText('dashboardFailure')||'Failure';
successRateChart=new Chart(canvas,{
type:'doughnut',
data:{
labels:[successLabel+'('+rate.totalSuccess+')',failureLabel+'('+rate.totalFailure+')'],
datasets:[{
data:[rate.totalSuccess,rate.totalFailure],
backgroundColor:['#4caf50','#f44336'],
borderWidth:0,
}],
},
options:{
responsive:true,
maintainAspectRatio:true,
plugins:{
legend:{
display:true,
position:'bottom',
labels:{color:themeColors.textColor,font:{size:11}},
},
tooltip:{
callbacks:{
label:function(context){
return context.label+' ('+rate.rate+'%)';
},
},
},
},
},
});
}
async function refreshPromptLengthChart(){
var canvas=document.getElementById('dashboardPromptLengthChart');
if(!canvas) return;
var themeColors=getThemeColors();
var allHistory=await PerformanceStorage.getAllHistory();
var lengths=[];
Object.values(allHistory).forEach(function(modeHistory){
modeHistory.forEach(function(entry){
if(entry.promptLength!==undefined&&entry.promptLength!==null){
lengths.push(entry.promptLength);
}
});
});
if(promptLengthChart){
promptLengthChart.destroy();
}
if(lengths.length===0){
var ctx=canvas.getContext('2d');
ctx.clearRect(0,0,canvas.width,canvas.height);
ctx.fillStyle=themeColors.textColor;
ctx.font='13px sans-serif';
ctx.textAlign='center';
ctx.fillText(getText('dashboardNoData')||'No data available',canvas.width/2,canvas.height/2);
return;
}
var maxLen=Math.max.apply(null,lengths);
var bucketSize=Math.max(50,Math.ceil(maxLen/20));
var buckets={};
lengths.forEach(function(len){
var bucket=Math.floor(len/bucketSize)*bucketSize;
var key=bucket+'-'+(bucket+bucketSize);
if(!buckets[key]) buckets[key]=0;
buckets[key]++;
});
var sorted=Object.entries(buckets).sort(function(a,b){
return parseInt(a[0])-parseInt(b[0]);
});
var labels=sorted.map(function(e){return e[0];});
var data=sorted.map(function(e){return e[1];});
promptLengthChart=new Chart(canvas,{
type:'bar',
data:{
labels:labels,
datasets:[{
label:getText('dashboardPromptLength')||'Prompt Length',
data:data,
backgroundColor:themeColors.accentColor+'80',
borderColor:themeColors.accentColor,
borderWidth:1,
}],
},
options:{
responsive:true,
maintainAspectRatio:false,
plugins:{legend:{display:false}},
scales:{
x:{
display:true,
title:{display:true,text:getText('dashboardLengthChars')||'Characters',color:themeColors.textColor},
grid:{color:themeColors.gridColor},
ticks:{color:themeColors.textColor,maxRotation:45,minRotation:45},
},
y:{
display:true,
beginAtZero:true,
title:{display:true,text:getText('dashboardCount')||'Count',color:themeColors.textColor},
grid:{color:themeColors.gridColor},
ticks:{color:themeColors.textColor,stepSize:1},
},
},
},
});
}
async function refreshCoOccurrence(){
var tableBody=document.getElementById('dashboardCoOccurrenceTable');
if(!tableBody) return;
var coData=await PromptFrequencyStorage.getCoOccurrence(20);
if(coData.length===0){
tableBody.innerHTML='<tr><td colspan="2" style="text-align:center;color:#888">'+(getText('dashboardNoData')||'No data available')+'</td></tr>';
return;
}
var html='';
coData.forEach(function(item){
html+='<tr>';
html+='<td>'+escapeHtml(item.tag1)+' + '+escapeHtml(item.tag2)+'</td>';
html+='<td>'+item.count+'</td>';
html+='</tr>';
});
tableBody.innerHTML=html;
}
async function refreshModelStats(){
var canvas=document.getElementById('dashboardModelChart');
if(!canvas) return;
var themeColors=getThemeColors();
var models=await PerformanceStorage.getModelStats();
if(modelChart){
modelChart.destroy();
}
if(models.length===0){
var ctx=canvas.getContext('2d');
ctx.clearRect(0,0,canvas.width,canvas.height);
ctx.fillStyle=themeColors.textColor;
ctx.font='13px sans-serif';
ctx.textAlign='center';
ctx.fillText(getText('dashboardNoData')||'No data available',canvas.width/2,canvas.height/2);
return;
}
var labels=models.map(function(m){
var name=m.name;
if(name.length>30) name=name.substring(0,27)+'...';
return name;
});
var data=models.map(function(m){return m.count;});
var colors=models.map(function(_,i){
var palette=['#00bcd4','#ff9800','#9c27b0','#e91e63','#4caf50','#607d8b','#03a9f4','#8bc34a'];
return palette[i%palette.length];
});
modelChart=new Chart(canvas,{
type:'bar',
data:{
labels:labels,
datasets:[{
label:getText('dashboardModelUsage')||'Model Usage',
data:data,
backgroundColor:colors.map(function(c){return c+'80';}),
borderColor:colors,
borderWidth:1,
}],
},
options:{
responsive:true,
maintainAspectRatio:false,
indexAxis:'y',
plugins:{legend:{display:false}},
scales:{
x:{
display:true,
beginAtZero:true,
grid:{color:themeColors.gridColor},
ticks:{color:themeColors.textColor,stepSize:1},
},
y:{
display:true,
grid:{color:themeColors.gridColor},
ticks:{color:themeColors.textColor},
},
},
},
});
}
async function refreshGoals(){
var goals=await PerformanceStorage.getGoal();
var progress=await PerformanceStorage.getGoalProgress();
var dailyInput=document.getElementById('dashboardDailyGoalInput');
if(dailyInput&&goals.daily){
dailyInput.value=goals.daily.target;
}
var weeklyInput=document.getElementById('dashboardWeeklyGoalInput');
if(weeklyInput&&goals.weekly){
weeklyInput.value=goals.weekly.target;
}
var dailyBar=document.getElementById('dashboardDailyProgressBar');
if(dailyBar){
dailyBar.style.width=progress.daily.percent+'%';
var dailyText=document.getElementById('dashboardDailyProgressText');
if(dailyText){
if(progress.daily.target>0){
dailyText.textContent=progress.daily.current+'/'+progress.daily.target;
}else{
dailyText.textContent='';
}
}
}
var weeklyBar=document.getElementById('dashboardWeeklyProgressBar');
if(weeklyBar){
weeklyBar.style.width=progress.weekly.percent+'%';
var weeklyText=document.getElementById('dashboardWeeklyProgressText');
if(weeklyText){
if(progress.weekly.target>0){
weeklyText.textContent=progress.weekly.current+'/'+progress.weekly.target;
}else{
weeklyText.textContent='';
}
}
}
}
async function refreshBadges(){
var grid=document.getElementById('dashboardBadgeGrid');
if(!grid) return;
var allStats=await PerformanceStorage.getAllStats();
var summary=await PerformanceStorage.getSummary();
var streak=await PerformanceStorage.getStreak();
var tagStats=await PromptFrequencyStorage.getStats();
var launchInfo=await PerformanceStorage.getLaunchInfo();
var badgeData={
allStats:allStats,
summary:summary,
streak:streak,
tagStats:tagStats,
launchInfo:launchInfo,
};
var html='';
BADGES.forEach(function(badge){
var unlocked=false;
try{
unlocked=badge.check(badgeData);
}catch(e){
unlocked=false;
}
var lockedClass=unlocked?'':'badge-locked';
var name=getText(badge.key)||badge.id;
html+='<div class="badge-item '+lockedClass+'">';
html+='<div class="badge-icon">'+badge.icon+'</div>';
html+='<div class="badge-name">'+escapeHtml(name)+'</div>';
html+='</div>';
});
grid.innerHTML=html;
}
async function exportJSON(){
var data=await PerformanceStorage.exportAllData();
if(!data) return;
var json=JSON.stringify(data,null,2);
var blob=new Blob([json],{type:'application/json'});
var url=URL.createObjectURL(blob);
var link=document.createElement('a');
link.download='dashboard_export_'+new Date().toISOString().slice(0,10)+'.json';
link.href=url;
link.click();
URL.revokeObjectURL(url);
}
async function exportCSV(){
var data=await PerformanceStorage.exportAllData();
if(!data) return;
var rows=[['Mode','Count','Avg(ms)','Min(ms)','Max(ms)']];
PerformanceStorage.MODES.forEach(function(mode){
var s=data.stats[mode];
rows.push([mode,s.count,s.avg,s.min||'',s.max||'']);
});
rows.push([]);
rows.push(['Date','Count']);
Object.entries(data.dailyStats).sort(function(a,b){return a[0].localeCompare(b[0]);}).forEach(function(e){
rows.push([e[0],e[1]]);
});
rows.push([]);
rows.push(['Model','Count']);
data.modelStats.forEach(function(m){
rows.push([m.name,m.count]);
});
var csv=rows.map(function(row){
return row.map(function(cell){
var s=String(cell===null||cell===undefined?'':cell);
if(s.indexOf(',')>=0||s.indexOf('"')>=0){
return '"'+s.replace(/"/g,'""')+'"';
}
return s;
}).join(',');
}).join('\n');
var blob=new Blob([csv],{type:'text/csv'});
var url=URL.createObjectURL(blob);
var link=document.createElement('a');
link.download='dashboard_export_'+new Date().toISOString().slice(0,10)+'.csv';
link.href=url;
link.click();
URL.revokeObjectURL(url);
}
function downloadWordcloud(){
var canvas=document.getElementById('dashboardWordcloud');
if(!canvas) return;
var link=document.createElement('a');
link.download='wordcloud_'+new Date().toISOString().slice(0,10)+'.png';
link.href=canvas.toDataURL('image/png');
link.click();
}
function updateElement(id,text){
var el=document.getElementById(id);
if(el) el.textContent=text;
}
function escapeHtml(text){
var div=document.createElement('div');
div.textContent=text;
return div.innerHTML;
}
async function recordGeneration(mode,timeMs,prompt,modelName){
var promptLength=(prompt&&typeof prompt==='string')?prompt.length:undefined;
await PerformanceStorage.recordTime(mode,timeMs,promptLength);
if(prompt){
await PromptFrequencyStorage.recordPrompt(prompt);
}
if(modelName){
await PerformanceStorage.recordModel(modelName);
}
await PerformanceStorage.recordSessionGeneration();
if(isOpen){
if(!isInitialized){
await init();
}
await refresh();
}
}
async function recordFailure(mode){
await PerformanceStorage.recordFailure(mode);
}
return{
init:init,
open:open,
close:close,
refresh:refresh,
recordGeneration:recordGeneration,
recordFailure:recordFailure,
MODE_LABELS:MODE_LABELS,
};
})();
function openDashboardModal(){
DashboardUI.open();
}
function closeDashboardModal(){
DashboardUI.close();
}
