// ダッシュボードUIコンポーネント（モーダル表示）
var dashboardLogger=new SimpleLogger('dashboard',LogLevel.DEBUG);
var DashboardUI=(function(){
var isInitialized=false;
var isOpen=false;
var generationTimeChart=null;
var trendChart=null;
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
var WORDCLOUD_COLORS_DARK=['#00bcd4','#4caf50','#ff9800','#e91e63','#9c27b0','#607d8b','#03a9f4','#8bc34a'];
var WORDCLOUD_COLORS_LIGHT=['#0097a7','#388e3c','#f57c00','#c2185b','#7b1fa2','#455a64','#0288d1','#689f38'];
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
}
async function refresh(){
await Promise.all([
refreshStats(),
refreshGenerationTimeChart(),
refreshHeatmap(),
refreshTrendChart(),
refreshTopTags(),
refreshWordcloud(),
]);
}
function formatDate(timestamp){
if(!timestamp) return '-';
var date=new Date(timestamp);
return date.toLocaleDateString();
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
html+='<div class="heatmap-cell" style="background-color:'+bgColor+'" title="'+DAY_LABELS[day]+' '+hour+':00 - '+count+' '+(getText('dashboardGenerations')||'generations')+'"></div>';
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
async function recordGeneration(mode,timeMs,prompt){
await PerformanceStorage.recordTime(mode,timeMs);
if(prompt){
await PromptFrequencyStorage.recordPrompt(prompt);
}
if(isOpen){
if(!isInitialized){
await init();
}
await refresh();
}
}
return{
init:init,
open:open,
close:close,
refresh:refresh,
recordGeneration:recordGeneration,
MODE_LABELS:MODE_LABELS,
};
})();
function openDashboardModal(){
DashboardUI.open();
}
function closeDashboardModal(){
DashboardUI.close();
}
