// ネーム（あらすじ）からページ内の全コマ分のプロンプトを一括生成する。
// タグを直接書かせず「そのコマが何をするコマか（役割）」を先に宣言させる。
// 「どのコマにも人物が描かれていてページに緩急がない」状態を避けるため

// 「伝えたいこと → 役割 → フレームに入れるもの」の対応表。
// 役割をラベル（バストアップ等）で定義すると「upper bodyと書けばそうなる」という
// 誤解を招くので、フレームに何が入るかで書く。
// 文面は llm_doc/manga-page-guideline.md の4・16章がそのまま元
const MANGA_PANEL_ROLES=[
'  showing the reader        role           what is inside the frame',
'  where they are            establishing   the place. things too large to fit the frame. no people, or people small enough to be dots',
'  the mood, or time passing scenery        the place with no people in it, without motion',
'  who is where, how they stand  full       one or more people head to shoes, and the floor they stand on',
'  what someone is doing     medium         waist up, and the hands. the feet and the floor are outside the frame',
'  what someone feels        closeup        the face. eyes and mouth. nothing below the shoulders',
'  what an object is         insert         one detail alone. an object, a hand, an eye',
'  the most important moment impact         tilted or steep viewpoint. the background may be dropped'
].join('\n');

// 表情・視線・仕草はここに挙げたタグだけを使わせる（閉じた語彙）。
// 全部Danbooruで件数を確認した実在タグ。件数は渡さない。
// 渡すと「件数は何を意味するか」の説明が要るうえ、効き目の強さと取り違える。
// 素の感情ラベル（smile / angry / sad / surprised / crying / laughing）は入れない。
// 指す絵の幅が広く、モデルが中心として学んだのがイラスト規模の表情のため
// （→ llm_doc/manga-page-guideline.md 13章）
const MANGA_EXPRESSION_TAGS=[
'  brow    v-shaped eyebrows, raised eyebrow',
'  eyes    closed eyes, half-closed eyes, narrowed eyes, wide-eyed, parted lips, tears, tearing up',
'  mouth   closed mouth, open mouth, frown, clenched teeth, wavy mouth, pout, light smile,',
'          grin, smirk',
'  face    expressionless, serious, glaring, annoyed, scowl, nervous, embarrassed, blush,',
'          shaded face',
'  gaze    looking at another, looking to the side, looking down, looking up, looking away,',
'          averting eyes, looking back, profile, from behind, looking at viewer, eye contact',
'  hands   clenched hand, clenched hands, own hands together, hand on own chest, hand on own face,',
'          hand on own hip, hands in pockets, covering face',
'  body    leaning forward, crossed arms, head tilt, turning head, trembling',
'  state   sweat, sweatdrop'
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
// 書き方の決まり: 命令か事実の断定だけを書く。比喩・言い換え・反語を使わない。
// 理由を書くときは「守らないと何が起きるか」を事実として書く
function buildPanelSystemPrompt(consistencyRules) {
return [
'Write the prompt for every panel on this page.',
'',
'Work in this order:',
'1. List what the reader learns on this page. One line each.',
'2. Check whether the place changed from the page before.',
'3. Assign one item from that list to each panel.',
'4. Decide the distance for each panel.',
'5. Decide the angle for each panel.',
'6. Write the tags.',
'',
'Watch these points:',
'',
'Splitting the page up:',
'- Put one item in one panel. With two items in one panel the reader registers neither.',
'- More items than panels: drop the least important. Do not move them to the next page.',
'- Fewer items than panels: split one item across two panels. Do not add items.',
'',
'Where the reader is:',
'- If the place changed from the page before, show the place in the first panel. Without it the',
'  reader assumes the scene is still in the previous location.',
'- If the place did not change, do not show it again.',
'',
'Distance:',
MANGA_PANEL_ROLES,
'- Change the distance when the kind of item you are showing changes, not on every panel.',
'- If the same distance runs three panels or more, check that those panels show the same kind of',
'  item. If they do not, change the distance.',
'- Use a panel with no people in it only for one of three purposes: the place changed, time passed,',
'  or the previous panel needs to be held. For any other reason, do not use one.',
'',
'Angle:',
'- Use eye level unless there is a reason not to.',
'- From below: the subject appears larger. Use for the character applying pressure, or for the',
'  viewpoint of a character looking up.',
'- From above: the subject appears smaller and the surroundings become readable. Use to show the',
'  place, or to show a character alone in it.',
'- Tilted: unstable. Use for shock or action.',
'- Tilt one panel per page at most.',
'',
'Using the panel layout you were given:',
'- Large: the place, or the most important panel on the page.',
'- Marked "bleed": the picture extends past the edge of the paper. Use for an open view or for the',
'  most important panel. This only works while the other panels stay inside their frames.',
'- Small: a face or one detail. Do not put a wide view in a small panel. It is unreadable at that size.',
'- Landscape: the place, or people side by side.',
'- Portrait: a standing figure head to toe.',
'- Marked "last": the reader decides at this panel whether to turn the page. Cut mid action, or on',
'  a face, or before the answer. Do not end the page on an explanation.',
'',
'Background:',
'- establishing, scenery, full and medium panels: two tags naming the place, and one for the light',
'  or the time of day.',
'- closeup and insert panels: the background may be dropped.',
'- Do not drop it before the place has been shown on this page. The reader does not yet know where',
'  the scene is.',
'- Panels in the same place repeat the same place tags word for word. Different wording is read as',
'  a different place.',
'- What replaces a dropped background depends on the reason for dropping it: emptiness to isolate,',
'  motion to carry speed, radiating lines for impact. Do not use the same one on every panel.',
'',
// 指針10章。視線でコマをつなぐ。左右の向きはDanbooruにタグが無いので指定しない
'Where the characters look:',
'- The direction the characters look moves the reader through the page. Direct it at what comes next.',
'- Two characters talking: have them look at each other.',
'- To carry the reader on to the next panel: turn the character away, or to the side.',
'- Eye contact with the reader stops the movement. Use it only where the reader should stop: the',
'  last panel, the most important panel, or a line addressed to the reader. On every other panel,',
'  direct the gaze at something in the scene.',
'',
// 指針11章（セリフとコマ）。吹き出しはアプリが後から乗せるので、絵で潰さない
'Leaving room for the words:',
'- The balloons are added by the editor on top of the picture. A face filling the frame leaves no',
'  room for them.',
'- Two things make room, and nothing else does:',
'    reduce the distance by one step. A panel with more than a line or two of speech is not a',
'      closeup. Use waist up at the closest, and further out as the amount of speech increases.',
'    name something above the character\'s head. The frame extends upward to include it. What that',
'      is depends on the location.',
'- Do not write "space", "empty space" or "room for text". The frame only extends to include',
'  something you named.',
'- A panel with no speech can use the whole frame. Put the wide views and the important panels there.',
'- The more speech a panel carries, the simpler the picture: drop the background, remove motion.',
'',
// 指針13章。素の感情ラベルは使わせず、閉じた語彙から顔と仕草を書かせる
'Feelings:',
'- Do not name an emotion. "angry", "sad", "happy", "surprised" and "smiling" each cover everything',
'  from faint to extreme, and the result is always at the extreme end.',
'- Name what the face is doing. Decide the gesture before the expression: in a manga the hands,',
'  the shoulders, the sweat and the shadow show more of a feeling than the face does.',
'- State that the mouth is closed on any panel where the feeling is held in. Otherwise it opens.',
'- Do not use the same expression on two panels in a row.',
'',
'For expression, gaze and body language, use these tags and no others:',
MANGA_EXPRESSION_TAGS,
'Everything else in a panel - the place, the clothes, the action, the objects - is ordinary',
'Danbooru vocabulary with no list.',
'',
'Sound effects are added by the editor as text. Do not ask the image for lettering.',
'',
// 指針16章。フレーミングタグが効かないことと、その代わりに何を書くか
'Getting the distance you decided on:',
'- "wide shot", "full body", "upper body" and "close-up" are labels applied to finished pictures.',
'  They are not instructions. Writing "full body" does not produce a whole body.',
'- The distance is set by which things you name:',
'    head to shoes  -> name the shoes, the legs, and the floor they stand on',
'    waist up       -> the clothes above the waist, the hands. not the shoes, not the floor',
'    the face       -> eyes, mouth, hair, expression. nothing below the shoulders',
'    the place      -> things in that place too large to fit inside a frame. people out, or far away',
'- Naming something outside the frame you want makes the view pull back to include it. A face panel',
'  with shoes named in it comes back as a whole body.',
'- A framing tag may be added on top as a hint. It must agree with what you named. On its own it',
'  does nothing.',
'',
'What the model produces when you do not specify:',
'- One person, chest to knee, facing front, looking at the camera. State the gaze direction to',
'  avoid this.',
'- Count the people in each panel and open the prompt with the count tags for that panel. Count',
'  them in that panel. Do not carry the count over from the panel before. Write "solo" only when',
'  one person is alone in it.',
'',
'Tags:',
'- Write the tags the reader has to see in that panel, then stop. With too few the model fills the',
'  gaps on its own. With too many each tag gets weaker, including the ones that set the distance.',
'  A panel showing a place needs many. A panel showing one face needs few.',
'- Anything named in these instructions other than the expression list above is an example of a',
'  kind of thing, not a tag to use. Pick the tag this panel needs, in this place, for these people.',
'- Before you answer, check your panels. If a tag that is not a character or a place appears in',
'  most of them, it was copied from these instructions. Remove it.',
'- Never output "comic", "panel", "border", "speech bubble", "text" or "4koma". The editor draws',
'  the frames and the balloons.',
'- Do not write anything about the frame cutting a character off. The editor handles that.',
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
