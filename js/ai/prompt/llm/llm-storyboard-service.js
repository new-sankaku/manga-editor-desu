// ネーム（あらすじ）からページ内の全コマ分のプロンプトを一括生成する。
// タグを直接書かせず「そのコマが何をするコマか（役割）」を先に宣言させる。
// 「どのコマにも人物が描かれていてページに緩急がない」状態を避けるため

// 「伝えたいこと → 役割 → フレームに入れるもの」の対応表。
// 役割をラベル（バストアップ等）で定義すると「upper bodyと書けばそうなる」という
// 誤解を招くので、フレームに何が入るかで書く。
// 文面は llm_doc/manga-page-guideline.md の4章と11章がそのまま元
const MANGA_PANEL_ROLES=[
'  telling the reader        role           what is inside the frame',
'  where they are            establishing   the place. things too big to fit the frame. no one, or people small enough to be dots',
'  the mood, or time passing scenery        the place with no one in it, held still',
'  who is where, how they stand  full       one or more people head to shoes, and the floor they stand on',
'  what someone is doing     medium         waist up, and the hands. the feet and the floor are outside the frame',
'  what someone feels        closeup        the face. eyes and mouth. nothing below the shoulders',
'  what something is         insert         one detail alone. an object, a hand, an eye',
'  the moment the page is built on  impact  the strongest beat. tilted or steep viewpoint, and the background may drop'
].join('\n');

const MANGA_PANEL_ROLE_NAMES=['establishing','scenery','insert','full','medium','closeup','impact'];

// 人物を出さないコマの役割。この3つだけが「間」を作れる
const MANGA_EMPTY_ROLES=['establishing','scenery','insert'];

// これ以上のコマ数で全コマに人物が居たら、間が無いページとして作り直させる。
// 3コマ以下は1つの場面を割っただけのこともあるので数えない
const MANGA_MIN_PANELS_NEEDING_BREATH=4;

// ネーム用とストーリー用でルール本体を共有する。片方だけ直して食い違うのを防ぐ。
// consistencyRules: 呼び出し側だけに要る一貫性のルール
//
// 「あなたは〜を受け取る」のような言い直しは書かない。ユーザーメッセージに
// 同じものが入っており、情報が増えないため。命令から始めて、気を付ける点を並べる
function buildPanelSystemPrompt(consistencyRules) {
return [
'Write the prompt for every panel on this page.',
'',
'Work in this order:',
'1. List what the reader learns on this page. One line each.',
'2. Check whether the place changed from the page before.',
'3. Give each panel one item from that list.',
'4. Decide the distance for each panel.',
'5. Decide the angle for each panel.',
'6. Write the tags.',
'',
'Watch these points:',
'',
'Splitting the page up:',
'- One panel carries one thing. Put two in and the reader misses both.',
'- More items than panels: drop the least important. Do not push them onto the next page,',
'  the next page has its own.',
'- Fewer items than panels: do not invent more. Split one item across panels instead',
'  (a hand reaching, then the wrist caught).',
'',
'Where the reader is:',
'- If the place changed from the page before, the first panel shows the place. The reader turns',
'  the page still holding the old place in their head. Start on a person and they read it as the',
'  same room.',
'- If the place did not change, do not show it again.',
'',
'Distance:',
MANGA_PANEL_ROLES,
'- Change the distance when what you are telling the reader changes. Not panel by panel.',
'- If the same distance runs three panels or more, check that those panels really are telling the',
'  same thing. If they are not, the reader will not see the difference.',
'- A panel with no one in it is only for three things: the place changed, time passed, or it holds',
'  the panel before it. If it does none of those it is a hole in the page, not a beat.',
'',
'Angle:',
'- Eye level unless there is a reason.',
'- From below: the subject reads larger and stronger. Use it for whoever is pressing, or for the',
'  view of someone looking up.',
'- From above: the subject reads smaller and the situation reads instead. Use it to explain the',
'  place, or to leave someone alone in it.',
'- Tilted: unsteady. Shock, or action.',
'- Tilt at most one panel on the page. Do it more and none of them read as unsteady.',
'',
'Using the panel layout you were given:',
'- Large, or marked "bleed": the place, or the one panel the page is built on.',
'- Small: a face or one detail. Never the place. Shrunk down there is nothing to see.',
'- Landscape: the place, or people side by side.',
'- Portrait: a standing figure head to toe.',
'- Marked "last": this is the reason the reader turns the page. Cut mid action, or on a face, or',
'  before the answer. Do not end the page on an explanation.',
'',
'Background:',
'- Establishing, scenery, full and medium panels: two tags that say where this is, and one for the',
'  light or the time of day.',
'- Closeup and insert: the background may be dropped.',
'- Do not drop it before this page has shown the place. The reader has nowhere to put the panel yet.',
'- Panels in the same place repeat the same place tags word for word. Different wording reads as a',
'  different place.',
'- What replaces a dropped background depends on why you dropped it: emptiness to isolate, streaks',
'  to carry speed, radiating lines to hit. Reaching for the same one every time makes the page',
'  look mechanical.',
'',
// 指針11章。フレーミングタグが効かないことと、その代わりに何を書くか
'Getting the distance you decided on. This is where most panels go wrong:',
'- "wide shot", "full body", "upper body", "close-up" are labels that were put on finished pictures.',
'  They are not instructions. Writing "full body" does not make the model draw a whole body.',
'- What sets the distance is which things you name:',
'    head to shoes  -> name the shoes, the legs, and the floor they stand on',
'    waist up       -> the clothes above the waist, the hands. not the shoes, not the floor',
'    the face       -> eyes, mouth, hair, expression. nothing below the shoulders',
'    the place      -> things in that place too big to fit inside a frame. people out, or far away',
'- Name something that sits outside the frame you want and the view pulls back to fit it in.',
'  A face panel with shoes in it comes back as a whole body.',
'- A framing tag may be added on top as a hint. It has to agree with what you named. On its own it',
'  does nothing.',
'',
'What the model does when you do not say:',
'- It falls back on one person, chest to knee, facing front, looking at the camera. A manga panel',
'  rarely does any of that. Say where the eyes are going when it matters.',
'- Count the people in each panel and open the prompt with the count tags for that panel. Count them',
'  in that panel; do not carry the count over from the panel before. Write "solo" only when one',
'  person really is alone.',
'',
'Tags:',
'- Write what the reader has to see in that panel, and stop. Too few and the model fills the gaps',
'  with whatever it likes. Too many and every one of them gets weaker, including the ones that set',
'  the distance. A panel showing a place needs many. A panel showing one face needs few.',
'- Every tag named in these instructions is an example of a kind of tag, never a tag to reach for.',
'  A tag goes into a panel because that panel needs it and for no other reason.',
'- Before you answer, look down your panels. If a tag that is not a character or a place appears in',
'  most of them, you copied it out of these instructions instead of reading the page. Take it out.',
'- Never output "comic", "panel", "border", "speech bubble", "text" or "4koma". The editor draws the',
'  frames and the balloons itself.',
'- Do not write anything about the frame cutting anyone off. The editor handles that.',
'',
'Keeping people and places the same:'
].concat(consistencyRules).concat([
'- Do not invent character names or series names that you were not given.',
'',
'Output:',
'- Return JSON only, shaped exactly as {"panels":[{"index":1,"role":"<role name>","prompt":"<tags>"}]}.',
'- Give one entry for every panel index you received, in the same order. Do not add or drop panels.',
'- "role" must be one of: '+MANGA_PANEL_ROLE_NAMES.join(', ')+'.',
'- "prompt" must be comma separated lowercase Danbooru style tags. No sentences, no explanation.'
]).join('\n');
}

const LLM_STORYBOARD_SYSTEM=buildPanelSystemPrompt(
['- Repeat a character\'s face and hair tags every time they appear, so the reader knows it is the'
+' same person. Their clothes go in only when that part of them is inside the frame.']
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
