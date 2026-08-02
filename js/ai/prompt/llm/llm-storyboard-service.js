// ネーム（あらすじ）からページ内の全コマ分のプロンプトを一括生成する。
// タグを直接書かせず「そのコマが何をするコマか（役割）」を先に宣言させる。
// 「どのコマにも人物が描かれていてページに緩急がない」状態を避けるため

// コマの役割。ここがページの緩急の語彙になる
const MANGA_PANEL_ROLES=[
'- establishing: the place itself, seen wide. "no humans", or the characters are small in the frame.',
'- scenery: mood, weather, or time passing. "no humans". sky, street, window, still objects.',
'- insert: a close detail of an object, a hand, feet or eyes. "no humans" when it is an object.',
'- full: characters head to toe, with the location visible behind them.',
'- medium: waist up or bust up. the ordinary conversation panel.',
'- closeup: face only. emotion.',
'- impact: the big moment of the page. dynamic angle, effect lines, background may be dropped.'
].join('\n');

const MANGA_PANEL_ROLE_NAMES=['establishing','scenery','insert','full','medium','closeup','impact'];

// 人物を出さないコマの役割。この3つだけが「間」を作れる
const MANGA_EMPTY_ROLES=['establishing','scenery','insert'];

// 1ページに最低何枚の人物なしコマを要求するか
function requiredEmptyPanelCount(panelCount) {
if (panelCount>=7) return 2;
if (panelCount>=4) return 1;
return 0;
}

// ネーム用とストーリー用でルール本体を共有する。片方だけ直して食い違うのを防ぐ。
// sourceWord: 何を受け取るかの1文。consistencyRules: 呼び出し側だけに要る一貫性のルール
function buildPanelSystemPrompt(sourceWord,consistencyRules) {
return [
'You are a manga storyboard artist and a Stable Diffusion prompt engineer.',
'You receive '+sourceWord+' and the panel layout of that page in reading order.',
'First decide what job each panel does on the page, then write the prompt for that job.',
'',
'Panel roles:',
MANGA_PANEL_ROLES,
'',
'Output:',
'- Return JSON only, shaped exactly as {"panels":[{"index":1,"role":"establishing","prompt":"tag, tag, tag"}]}.',
'- Give one entry for every panel index you received, in the same order. Do not add or drop panels.',
'- "role" must be one of: '+MANGA_PANEL_ROLE_NAMES.join(', ')+'.',
'- "prompt" must be comma separated lowercase Danbooru style tags. No sentences, no explanation.',
'- 15 to 30 tags per panel.',
'',
'Rhythm of the page. This is the most important part:',
'- A page where every panel shows a person is a failed page. The reader needs empty beats.',
'- With 4 or more panels, at least one panel must be establishing, scenery or insert, and its prompt must contain the tag "no humans".',
'- With 7 or more panels, at least two such panels.',
'- Never use the same role in three panels in a row.',
'- The panel with the largest areaSharePercent takes impact or establishing. The smallest panels take closeup or insert.',
'- landscape shaped panels suit establishing and scenery. portrait shaped panels suit full and impact. small square panels suit closeup and insert.',
'- A panel with "bleed":true runs off the edge of the paper. Give it an open view or the strongest moment of the page.',
'- If the place or the time of day changes on this page, the first panel after the change is establishing.',
'- The panel with "last":true lands the emotion or leaves a hook. Do not end the page on a flat medium shot.',
'',
'Background:',
'- Every establishing, scenery, full and medium panel must carry at least two tags naming the place, and one tag for the light or the time of day.',
'- Panels that happen in the same place must repeat the same place tags word for word, so the reader stays in one location.',
'- closeup, insert and impact panels may drop the location on purpose and use "simple background", "speed lines", "emphasis lines", "motion blur" or "sunburst" instead. That contrast is what creates the rhythm. Dropping the background is a choice, never a shortcut.',
'',
'Page context:',
'- You may also be told where and when this page happens, and what happened on the page before and after. Use them and never contradict them.',
'- Every panel that shows the location must match that place and that time of day.',
'- When you are told that this page opens a new scene, the very first panel must be establishing. The reader has just been moved somewhere else and needs to see where they are.',
'- When the previous page is given, do not repeat its closing shot. Continue from it.',
'- When the next page is given, lead into it. Do not draw it.',
'- Do not put a character in a panel unless what happens on this page implies that they are there.',
'',
'Consistency:'
].concat(consistencyRules).concat([
'- Do not invent character names or series names that you were not given.',
'- Never output "comic", "panel", "border", "speech bubble", "text" or "4koma". The editor draws the frames and the balloons itself.'
]).join('\n');
}

const LLM_STORYBOARD_SYSTEM=buildPanelSystemPrompt(
'the synopsis of one manga page',
['- Repeat the same character appearance tags in every panel where that character appears, so the same person stays recognisable.']
);

function sortPanelsInReadingOrder(panels,rightToLeft) {
var items=panels.map(function (panel) {
return {panel: panel,rect: panel.getBoundingRect()};
});
items.sort(function (a,b) {
return a.rect.top-b.rect.top;
});
var rows=[];
items.forEach(function (item) {
var centerY=item.rect.top+item.rect.height/2;
var row=null;
for (var i=0;i<rows.length;i++) {
if (centerY>=rows[i].top&&centerY<=rows[i].bottom) {
row=rows[i];
break;
}
}
if (!row) {
row={top: item.rect.top,bottom: item.rect.top+item.rect.height,items: []};
rows.push(row);
}
row.items.push(item);
});
var ordered=[];
rows.forEach(function (row) {
row.items.sort(function (a,b) {
return rightToLeft ? b.rect.left-a.rect.left : a.rect.left-b.rect.left;
});
ordered=ordered.concat(row.items);
});
return ordered;
}

function buildPanelLayoutSummary(ordered) {
var canvasWidth=canvas.getWidth();
var canvasHeight=canvas.getHeight();
// 紙面の1%以内に寄っていれば断ち切り扱い。枠線の太さ分だけ内側にあることがある
var edge=Math.max(canvasWidth,canvasHeight)*0.01;
var totalArea=0;
ordered.forEach(function (item) {
totalArea+=item.rect.width*item.rect.height;
});
return ordered.map(function (item,i) {
var area=item.rect.width*item.rect.height;
var ratio=item.rect.width/item.rect.height;
var shape='square';
if (ratio>1.3) shape='landscape';
else if (ratio<0.77) shape='portrait';
return {
index: i+1,
shape: shape,
widthPercent: Math.round(item.rect.width/canvasWidth*100),
heightPercent: Math.round(item.rect.height/canvasHeight*100),
areaSharePercent: totalArea>0 ? Math.round(area/totalArea*100) : 0,
// 断ち切りコマ。紙の外へ抜けるので引きの絵や見せ場に向く
bleed: item.rect.left<=edge
||item.rect.top<=edge
||item.rect.left+item.rect.width>=canvasWidth-edge
||item.rect.top+item.rect.height>=canvasHeight-edge,
first: i===0,
last: i===ordered.length-1
};
});
}

function promptHasTag(prompt,tag) {
return prompt.toLowerCase().split(',').some(function (part) {
return part.trim()===tag;
});
}

// 役割の配分を見て、守られていない点を文にして返す。ページの緩急そのものなので
// 足りないまま黙って通さない。sceneChange: このページが新しい場面で始まるか
function findPanelRhythmProblem(entries,sceneChange) {
var problems=[];
var required=requiredEmptyPanelCount(entries.length);
if (required>0) {
var empty=entries.filter(function (entry) {
return MANGA_EMPTY_ROLES.indexOf(entry.role)>=0&&promptHasTag(entry.prompt,'no humans');
}).length;
if (empty<required) {
problems.push('Only '+empty+' panel(s) are establishing/scenery/insert and tagged "no humans", '
+'but this page of '+entries.length+' panels needs at least '+required+'. '
+'Rewrite the page so it has that many empty beats.');
}
}
// 場面転換の直後に引きの絵が無いと、読者はどこの話か分からないまま次のコマへ進む
if (sceneChange&&entries.length>0&&entries[0].role!=='establishing') {
problems.push('This page opens a new scene, so panel 1 must have the role "establishing", '
+'but it is "'+(entries[0].role||'unknown')+'". Rewrite panel 1 as a wide view of the place.');
}
return problems.length>0 ? problems.join('\n') : null;
}

function parseStoryboardResponse(raw,expectedCount) {
var body=raw.replace(/```[a-z]*\n?/gi, '').replace(/```/g,'').trim();
var parsed;
try {
parsed=JSON.parse(body);
} catch (e) {
throw new Error(i18next.t('llmStoryboardErrorNotJson'));
}
if (!parsed||!Array.isArray(parsed.panels)) {
throw new Error(i18next.t('llmStoryboardErrorNotJson'));
}
var byIndex={};
parsed.panels.forEach(function (entry) {
if (!entry) return;
var index=parseInt(entry.index,10);
if (!index||index<1||index>expectedCount) return;
if (typeof entry.prompt!=='string') return;
var tags=normalizeTagOutput(entry.prompt);
if (!tags) return;
var role=typeof entry.role==='string' ? entry.role.trim().toLowerCase() : '';
byIndex[index]={
prompt: tags,
// 知らない役割名は空にする。役割の表示と緩急の判定に使うだけなので、
// 勝手に近い役割へ寄せると人物なしコマを数え違える
role: MANGA_PANEL_ROLE_NAMES.indexOf(role)>=0 ? role : ''
};
});
var missing=[];
var results=[];
for (var i=1;i<=expectedCount;i++) {
if (!byIndex[i]) {
missing.push(i);
}
results.push(byIndex[i]||{prompt: '',role: ''});
}
if (missing.length>0) {
throw new Error(i18next.t('llmStoryboardErrorMissing')+' '+missing.join(', '));
}
return results;
}

function callPanelPrompts(target,systemPrompt,userPrompt,expectedCount) {
var messages=target.provider.buildTextMessages(systemPrompt,userPrompt);
return target.queue.add(function () {
return target.provider.chat(messages,{temperature: 0.6,jsonObject: true});
}).then(function (raw) {
return parseStoryboardResponse(raw,expectedCount);
});
}

// 役割の配分が守られていなければ違反内容を添えて1度だけ作り直す。
// 2度目も守られなければ結果は返すが、警告を必ず画面へ返す。黙って通さない。
// 戻り値: {entries:[{prompt,role}], warning:string|null}
async function requestPanelPrompts(systemPrompt,userPrompt,expectedCount,sceneChange) {
var target=requireLLMProvider(AI_ROLES.Text2Prompt);
var entries=await callPanelPrompts(target,systemPrompt,userPrompt,expectedCount);
var problem=findPanelRhythmProblem(entries,sceneChange);
if (problem) {
var retryPrompt=userPrompt+'\n\nYour previous answer was rejected:\n'+problem;
entries=await callPanelPrompts(target,systemPrompt,retryPrompt,expectedCount);
problem=findPanelRhythmProblem(entries,sceneChange);
}
return {entries: entries,warning: problem};
}

// 戻り値: {entries:[{panel,index,prompt,role}], warning:string|null}
async function llmStoryboard(synopsis,rightToLeft) {
var panels=getPanelObjectList();
if (!panels||panels.length===0) {
throw new Error(i18next.t('llmStoryboardErrorNoPanel'));
}
var ordered=sortPanelsInReadingOrder(panels,rightToLeft);
var layout=buildPanelLayoutSummary(ordered);
var userPrompt=[
'Synopsis of this page:',
synopsis,
'',
'Panel layout in reading order ('+(rightToLeft ? 'right to left' : 'left to right')+'):',
JSON.stringify(layout)
].join('\n');
// ネーム窓は1ページ単体。前のページが無いので必ず場面の始まりとして扱う
var result=await requestPanelPrompts(LLM_STORYBOARD_SYSTEM,userPrompt,ordered.length,true);
return {
entries: ordered.map(function (item,i) {
return {panel: item.panel,index: i+1,prompt: result.entries[i].prompt,role: result.entries[i].role};
}),
warning: result.warning
};
}
