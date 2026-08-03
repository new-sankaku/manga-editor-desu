// ネーム（あらすじ）からページ内の全コマ分のプロンプトを一括生成する。
// タグを直接書かせず「そのコマが何をするコマか（役割）」を先に宣言させる。
// 「どのコマにも人物が描かれていてページに緩急がない」状態を避けるため

// コマの役割。ラベル（バストアップ等）ではなく「フレームに何が入るか」で定義する。
// 「upper bodyと書けば上半身になる」という誤解を役割の定義自体が招かないようにするため
const MANGA_PANEL_ROLES=[
'- establishing: the place. What fills it is in frame. People are absent, or far enough away to be small.',
'- scenery: mood, weather, time passing. No people. Sky, street, window, still objects.',
'- insert: one detail on its own. An object, a hand, feet, eyes.',
'- full: a person with their footwear and the ground they stand on inside the frame.',
'- medium: a person from the waist up. Their feet and the ground are outside the frame.',
'- closeup: a face. Nothing below the shoulders.',
'- impact: the strongest moment of the page. Tilted or steep viewpoint, and the background may drop away.'
].join('\n');

const MANGA_PANEL_ROLE_NAMES=['establishing','scenery','insert','full','medium','closeup','impact'];

// 人物を出さないコマの役割。この3つだけが「間」を作れる
const MANGA_EMPTY_ROLES=['establishing','scenery','insert'];

// これ以上のコマ数で全コマに人物が居たら、間が無いページとして作り直させる。
// 3コマ以下は1つの場面を割っただけのこともあるので数えない
const MANGA_MIN_PANELS_NEEDING_BREATH=4;

// ネーム用とストーリー用でルール本体を共有する。片方だけ直して食い違うのを防ぐ。
// sourceWord: 何を受け取るかの1文。consistencyRules: 呼び出し側だけに要る一貫性のルール
//
// 何枚をどの役割にするかといった配分は書かない。作品や場面で変わるので決め打てない。
// 原則だけ渡して判断はLLMに任せる（→ llm_doc/prompt-composition.md）
function buildPanelSystemPrompt(sourceWord,consistencyRules) {
return [
// 何をする役か。まず役割を決めてからタグを書かせる。
// 「役割を決めろ」だけでは決めようがないので、何を基準に決めるのかを渡す
'You are a manga storyboard artist and a Stable Diffusion prompt engineer.',
'You receive '+sourceWord+' and the panel layout of that page in reading order.',
'Decide what job each panel does on the page, then write the prompt for that job.',
'',
'The job of a panel is what the reader learns from it that the panel before did not tell them:',
'where they are, who is there, what someone feels, or what someone did.',
'Settle that first. The distance follows from it, and the role is the name for that distance.',
'',
// コマの役割
'Panel roles. A role says what sits inside the frame, not what the shot would be called:',
MANGA_PANEL_ROLES,
'',
// 出力形式。タグ数は決め打たない。必要な数はコマの中身で変わる
'Output:',
'- Return JSON only, shaped exactly as {"panels":[{"index":1,"role":"establishing","prompt":"tag, tag, tag"}]}.',
'- Give one entry for every panel index you received, in the same order. Do not add or drop panels.',
'- "role" must be one of: '+MANGA_PANEL_ROLE_NAMES.join(', ')+'.',
'- "prompt" must be comma separated lowercase Danbooru style tags. No sentences, no explanation.',
// 「必要なだけ」だけでは基準がないので、多すぎ／少なすぎで何が起きるかを渡す
'- Write the tags the reader has to see in that panel, and stop. Name too few and the model fills',
'  the gaps with whatever it likes. Name too many and every one of them gets weaker, including the',
'  ones that decide the framing. A panel showing a place needs many tags. A panel showing one face needs few.',
'',
// フレーミングの作り方。ここが一番間違えやすいので理由から書く
'How to actually get the framing you want. This is where most panels go wrong:',
'- "wide shot", "full body", "upper body" and "close-up" are labels that were put on finished pictures.',
'  They are not instructions. Writing "full body" does not make the model draw a whole body.',
'- The framing follows the things you name. Name what sits at the edge of the frame you want,',
'  and the frame has to grow to hold it.',
'- So, to show a person head to toe, name the footwear, the legs and the floor or ground they stand on.',
'- To show only a face, name nothing below the shoulders. No shoes, no legs, no ground.',
'  Name them and the view pulls back on its own to fit them in.',
'- To show a place, name what fills it: buildings, sky, road, furniture, a window.',
'  Leave the people out, or put them far away.',
'- A framing tag may be added on top of that as a hint. It has to agree with what you named.',
'  It never does the work on its own.',
'',
// ページの緩急。枚数は指定せず、何を見て決めるのかを渡す。
// 「判断せよ」だけでは判断できないので、間のコマの仕事とコマの大きさの意味を教える
'Rhythm of the page:',
'- A page where every panel is a person at the same distance reads flat. The distance has to change.',
'- A panel with no one in it is not a gap in the page. It does one of three jobs: it shows time',
'  passing, it tells the reader where they now are, or it holds the feeling of the panel before it.',
'  Put one in where the page needs one of those. Leave it out where it needs none.',
'  Leave it out where it was needed and the reader loses the thread at the next panel.',
'- The size of a panel is how long the reader stays inside it. A large panel is looked at, so it can',
'  hold a wide view or the one moment the page is built around. A small panel goes by in an instant,',
'  so it carries one thing only: a face, a detail, a reaction. Give a small panel a wide view and',
'  the reader sees nothing at all.',
'- A panel marked "bleed" runs off the edge of the paper, so the reader feels no boundary on that',
'  side. That suits an open view, or the peak of the page.',
'- The panel marked "last" is the reason the reader turns the page. Land the moment, or leave a question.',
'',
// 背景。タグ数は決め打たない。落としてよい条件を渡さないと「意図的に」が判断できない
'Background:',
'- The reader works out where they are from the panels that show it, and forgets it again if no',
'  panel repeats it. A panel that shows the location has to name the place and the light or the',
'  time of day. Panels in the same place repeat those tags word for word. Change the wording and',
'  the reader reads it as somewhere else.',
'- Dropping the background is for pulling the reader onto one thing, or for stopping time. That is',
'  a closeup, an insert or an impact panel, and "simple background", "speed lines", "emphasis lines",',
'  "motion blur" or "sunburst" go in its place.',
'- Do not drop it before the place has been shown on this page. The reader has nowhere to put the',
'  panel yet, and the page reads as floating.',
'',
// ページの前後関係。渡されたときだけ効く
'Page context:',
'- You may also be told where and when this page happens, and what happened on the page before and after.',
'  Use them and never contradict them.',
'- Every panel that shows the location has to match that place and that time of day.',
'- When you are told that this page opens a new scene, the reader has just been moved somewhere else',
'  and has to be shown where they are before anything else happens.',
'- When the previous page is given, do not repeat its closing shot. Continue from it.',
'- When the next page is given, lead into it. Do not draw it.',
'- Do not put a character in a panel unless what happens on this page implies that they are there.',
'',
// 人数。キャラ表を並べると1girlが重複して破綻するため、コマ側で決めさせる
'How many people are in the panel:',
'- Name how many people are in each panel: "1girl", "1boy, 1girl", "2girls".',
'- Write "solo" only when the panel really shows one person alone.',
'',
// 一貫性。キャラ表の使い方は呼び出し側で変わる
'Consistency:'
].concat(consistencyRules).concat([
'- Do not invent character names or series names that you were not given.',
'- Never output "comic", "panel", "border", "speech bubble", "text" or "4koma". The editor draws the frames and the balloons itself.',
// 見切れのネガティブは書き込み側が常に足す（panel-composition.js）。
// ここで扱わせると判断が揺れるうえ、後から直せない事故になる
'- Do not write anything about the frame cutting anyone off. The editor handles that.'
]).join('\n');
}

const LLM_STORYBOARD_SYSTEM=buildPanelSystemPrompt(
'the synopsis of one manga page',
['- Keep a character recognisable by repeating their face and hair tags every time they appear.'
+' Their clothes belong in a panel only when that part of them is inside the frame.']
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
// 何枚を人物なしにするかは指定しない。LLMが判断する。
// ここで見るのは「1枚も無い」という壊れ方だけ。LLMは放っておくと全コマを
// 人物のバストアップで埋めるので、その一点だけ拾う
if (entries.length>=MANGA_MIN_PANELS_NEEDING_BREATH) {
var empty=entries.filter(function (entry) {
return MANGA_EMPTY_ROLES.indexOf(entry.role)>=0&&promptHasTag(entry.prompt,'no humans');
}).length;
if (empty===0) {
problems.push('Every panel on this page has a person in it. The page has '+entries.length
+' panels, so it needs somewhere for the reader to breathe. Give at least one panel '
+'the role establishing, scenery or insert, with "no humans" in its prompt. '
+'How many it needs beyond that is up to you.');
}
}
// 場面転換の直後に場所が見えないと、読者はどこの話か分からないまま次のコマへ進む
if (sceneChange&&entries.length>0&&entries[0].role!=='establishing') {
problems.push('This page opens a new scene, so the reader has to be shown where they are '
+'before anything else happens. Panel 1 is "'+(entries[0].role||'unknown')+'". '
+'Make it establishing.');
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
// 作品傾向。どのコマを寄りにして、どのコマを引きにするかはこれを読んでLLMが決める
var tone=mangaToneGuidance();
var userPrompt=(tone ? ['What kind of manga this is:',tone,''] : []).concat([
'Synopsis of this page:',
synopsis,
'',
'Panel layout in reading order ('+(rightToLeft ? 'right to left' : 'left to right')+'):',
JSON.stringify(layout)
]).join('\n');
// ネーム窓は1ページ単体。前のページが無いので必ず場面の始まりとして扱う
var result=await requestPanelPrompts(LLM_STORYBOARD_SYSTEM,userPrompt,ordered.length,true);
return {
entries: ordered.map(function (item,i) {
return {panel: item.panel,index: i+1,prompt: result.entries[i].prompt,role: result.entries[i].role};
}),
warning: result.warning
};
}
