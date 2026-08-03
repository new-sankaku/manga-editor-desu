// ストーリー1本から「登場人物とロケーションの設定 → 各ページの流れ → 各コマのプロンプト」を作る。
// コマの並べ替え・レイアウト要約・コマ応答のパース・役割の検証はllm-storyboard-service.jsの
// 関数をそのまま使い、実装を二重に持たない

// ユーザーが書くストーリーは短い。1行のこともある。そのままページへ配ると
// 1ページに1文も割り当たらず、各ページが空になる。先にページ数に見合う量まで膨らませる。
// 文面は llm_doc/manga-page-guideline.md の9章がそのまま元
const LLM_STORY_EXPAND_SYSTEM=[
'You receive a short premise for a manga and the number of pages it has to fill.',
'Write it out as a story long enough to fill those pages.',
'Rules:',
'- Return JSON only, shaped exactly as {"story":"..."}.',
'- Write in the same language as the premise.',
'- Keep everything the premise already says. You are filling in what it leaves out, not replacing it.',
'- Add only what the story needs: who the characters are and how they know each other, where it',
'  happens, why someone wants what they want, what stands in their way, the one scene the story is',
'  being told for, and how it ends.',
'- Give the characters plain names, so that the later steps can refer to them.',
// 人数と場所の上限は物語の都合ではない。同一人物を保つ手段がタグの一致しかないため
'- Keep the cast to three or four people, and the places to two or three. This is not a preference',
'  about storytelling. The drawing is done by an image model that has only matching tags to hold a',
'  face or a place steady, so every extra character and every extra location is one more thing that',
'  will drift from panel to panel.',
'- One scene runs one to three pages. Work out how many scenes the page count can hold before you',
'  write. Too many scenes and a scene gets less than a page, which is not enough to draw anything in.',
'  Too few and a scene is stretched over four or more pages and goes slack.',
'- Write one paragraph per scene. Each paragraph says where it is, who is there, and what happens.',
'- Write what happens, not what is true. Not "he had always liked her", but "he started to speak to',
'  her, no words came, and he turned away".',
'- Do not break it into pages or panels here. That comes later.'
].join('\n');

function parseStoryExpand(raw) {
const parsed=parseLLMJsonBody(raw);
const story=parsed&&typeof parsed.story==='string' ? parsed.story.trim() : '';
if (!story) {
throw new Error(i18next.t('llmErrorEmptyResponse'));
}
return story;
}

// 戻り値: 膨らませたストーリー本文
async function llmStoryExpand(story,pageCount) {
const target=requireLLMProvider(AI_ROLES.Text2Prompt);
const userPrompt=[
'Pages to fill: '+pageCount,
'',
'Premise:',
story
].join('\n');
const messages=target.provider.buildTextMessages(LLM_STORY_EXPAND_SYSTEM,userPrompt);
const raw=await target.queue.add(function () {
return target.provider.chat(messages,{temperature: 0.8,jsonObject: true});
});
return parseStoryExpand(raw);
}

// キャラとロケーションを1回の呼び出しでまとめて作る。どちらも同じストーリーから引くため
const LLM_STORY_SHEET_SYSTEM=[
// 肩書きを名乗らせても後続のルールが全部を決めるので情報が増えない。
// 出力の語彙（Danbooru形式）と何のために作るのかだけ言う
'You receive the synopsis of a manga story.',
'Fix the recurring characters and the recurring places as Danbooru style tags, so that every panel can reuse them.',
'Rules:',
'- Return JSON only, shaped exactly as {"characters":[{"name":"...","tags":"tag, tag"}],"locations":[{"name":"...","tags":"tag, tag"}]}.',
'- "name" is how the synopsis refers to it. Keep the language of the synopsis.',
'- All "tags" are comma separated lowercase Danbooru style tags.',
'- Character tags cover appearance only: age, hair, eyes, face, clothing, body type, accessories, shoes.',
'- Do not put pose, expression, camera angle or background in character tags. Those change from panel to panel.',
// 2人のコマでキャラ表を2つ並べると1girlが2回入り、solo寄りの偏りと噛み合って破綻する
'- Do not put a count tag such as "1girl", "1boy", "solo" or "multiple girls" in character tags. How many people are in a panel is decided panel by panel.',
'- Location tags cover the kind of place, its notable objects, the time of day and the light.',
'- Do not put people, pose or camera angle in location tags.',
// 「最大6」は根拠がないうえ、7人目を黙って落とす。どのキャラが消えたかは画面に出ない。
// 上限ではなく「作る対象は何か」を言う
'- Only characters and places that actually appear in the synopsis. Do not invent extra ones.',
'- A sheet is for something that comes back. Someone who passes through one scene and is never',
'  seen again does not need one, and neither does a place the story only mentions.'
].join('\n');

const LLM_STORY_PAGEPLAN_SYSTEM=[
'You are a manga editor breaking a story down into pages.',
'You receive the whole story and the list of pages with how many panels each page has.',
'Write what happens on each page so that the story fits exactly into the given pages.',
'Rules:',
'- Return JSON only, shaped exactly as {"pages":[{"page":1,"summary":"...","location":"...","time":"..."}]}.',
'- Give one entry for every page number you received. Do not add or drop pages.',
'- "summary" is 1 to 3 sentences in the same language as the story. Name the characters who are present.',
'- "location" is the place this page happens in, as a short noun phrase in the same language as the story.',
'- "time" is the time of day, as a short word in the same language as the story.',
'- Reuse the exact same "location" and "time" wording whenever the story stays in the same place, and change it only when the story really moves. The artist decides where to draw the establishing shots from this.',
// 起承転結を型として渡すと必ず4分割してくる。何を見て配分を決めるかだけを渡す
'How to spread the story over the pages:',
'- The reader needs a reason to keep going before they are given an explanation. Open on something',
'  happening, or on something withheld. Background the reader has not asked for yet can wait.',
'- Weight is pages. A beat you give three pages to reads as important. The same beat in half a page',
'  reads as a passing detail. Spend the pages on what the story is actually about, and move fast',
'  through what only has to be true.',
'- Somewhere the story has to turn: the thing the reader expected stops being what happens. Decide',
'  where that page is. Put it too near the end and there is no room left for the reader to feel it.',
'- The last page is what the reader is left holding. It answers the question the first page raised,',
'  or answers it in a way they did not see coming.',
'- A page is what the reader takes in at once, and the page break is a pause. Keep one beat on one',
'  page unless the pause itself does something for you.',
'- A page with many panels carries several beats. A page with few panels carries one big moment.',
'- Do not write it panel by panel here. That comes in a later step.'
].join('\n');

const LLM_STORY_PANEL_SYSTEM=buildPanelSystemPrompt(
'what happens on one manga page',
[
// キャラ表をそのまま全部コピーさせると、顔だけのコマにも靴が入って勝手に引いた絵になる。
// フレームに入る範囲だけ使わせる（→ llm_doc/prompt-composition.md）
'- When a character sheet is given, take from it only what is inside that panel\'s frame.'
+' Face and hair every time, so the same person stays recognisable. Clothing when the body is in frame.'
+' Footwear only when the feet are in frame. Naming a part that is outside the frame drags the view back to it.',
'- When a location sheet is given, copy those place tags word for word into every panel that happens in that place, so the reader stays in one location.'
]
);

function parseLLMJsonBody(raw) {
const body=raw.replace(/```[a-z]*\n?/gi, '').replace(/```/g,'').trim();
try {
return JSON.parse(body);
} catch (e) {
throw new Error(i18next.t('llmStoryboardErrorNotJson'));
}
}

// 画面には1行1件の素のテキストで見せる。編集してそのまま渡せるようにするため
function sheetEntriesToText(list) {
if (!Array.isArray(list)) {
return '';
}
const lines=[];
list.forEach(function (entry) {
if (!entry||typeof entry.tags!=='string') {
return;
}
const tags=normalizeTagOutput(entry.tags);
if (!tags) {
return;
}
const name=typeof entry.name==='string' ? entry.name.trim() : '';
lines.push(name ? name+': '+tags : tags);
});
return lines.join('\n');
}

function parseStorySheets(raw) {
const parsed=parseLLMJsonBody(raw);
if (!parsed) {
throw new Error(i18next.t('llmStoryboardErrorNotJson'));
}
const characters=sheetEntriesToText(parsed.characters);
const locations=sheetEntriesToText(parsed.locations);
if (!characters&&!locations) {
throw new Error(i18next.t('llmErrorEmptyResponse'));
}
return {characters: characters,locations: locations};
}

// 戻り値: {characters:string, locations:string}
async function llmStorySheets(story) {
const target=requireLLMProvider(AI_ROLES.Text2Prompt);
const messages=target.provider.buildTextMessages(LLM_STORY_SHEET_SYSTEM,'Story:\n'+story);
const raw=await target.queue.add(function () {
return target.provider.chat(messages,{temperature: 0.4,jsonObject: true});
});
return parseStorySheets(raw);
}

// 場所と時間はまとめて1行にする。画面ではこの1行を直接編集させ、
// 場面転換の判定もこの文字列の一致で行う。判定がユーザーの手直しに追随するため
function joinPlace(location,time) {
const parts=[location,time].map(function (part) {
return typeof part==='string' ? part.trim() : '';
}).filter(function (part) {
return part;
});
return parts.join(' / ');
}

// 欠けたページを黙って埋めない。どのページが返らなかったかを挙げてエラーにする。
// 戻り値: [{page,summary,place}]
function parseStoryPagePlan(raw,pageNumbers) {
const parsed=parseLLMJsonBody(raw);
if (!parsed||!Array.isArray(parsed.pages)) {
throw new Error(i18next.t('llmStoryboardErrorNotJson'));
}
const byPage={};
parsed.pages.forEach(function (entry) {
if (!entry||typeof entry.summary!=='string') {
return;
}
const page=parseInt(entry.page,10);
if (!page) {
return;
}
const summary=entry.summary.trim();
if (!summary) {
return;
}
byPage[page]={page: page,summary: summary,place: joinPlace(entry.location,entry.time)};
});
const missing=[];
const results=pageNumbers.map(function (page) {
if (!byPage[page]) {
missing.push(page);
return null;
}
return byPage[page];
});
if (missing.length>0) {
throw new Error(i18next.t('storyErrorMissingPage')+' '+missing.join(', '));
}
return results;
}

// pageInfos: [{page,panelCount}]
async function llmStoryPagePlan(story,pageInfos) {
const target=requireLLMProvider(AI_ROLES.Text2Prompt);
const layout=pageInfos.map(function (info) {
return {page: info.page,panelCount: info.panelCount};
});
const userPrompt=[
'Story:',
story,
'',
'Pages and how many panels each page has:',
JSON.stringify(layout)
].join('\n');
const messages=target.provider.buildTextMessages(LLM_STORY_PAGEPLAN_SYSTEM,userPrompt);
const raw=await target.queue.add(function () {
return target.provider.chat(messages,{temperature: 0.6,jsonObject: true});
});
return parseStoryPagePlan(raw,pageInfos.map(function (info) {
return info.page;
}));
}

// context: {pageSummary,place,sceneChange,prevSummary,prevPlace,nextSummary,
//           pageIndex,pageCount,characterSheet,locationSheet,layout,rightToLeft}
// 戻り値: {entries:[{prompt,role}], warning:string|null}
async function llmStoryPanelPrompts(context) {
const lines=[];
// 作品傾向。どのコマを寄りにして、どのコマを引きにするかはこれを読んでLLMが決める
const tone=mangaToneGuidance();
if (tone) {
lines.push('What kind of manga this is:');
lines.push(tone);
lines.push('');
}
if (context.characterSheet) {
// 「verbatim」と書くとシステムプロンプト側の「フレームに入る範囲だけ取れ」と食い違い、
// 顔だけのコマにも靴が入る
lines.push('Character sheet. Use the parts of it that are inside the panel frame:');
lines.push(context.characterSheet);
lines.push('');
}
if (context.locationSheet) {
lines.push('Location sheet. Copy these word for word into every panel that shows this place:');
lines.push(context.locationSheet);
lines.push('');
}
if (context.pageCount>1) {
lines.push('This is page '+context.pageIndex+' of '+context.pageCount+'.');
}
if (context.place) {
lines.push('Where and when this page happens: '+context.place);
}
if (context.sceneChange) {
lines.push('This page opens a new scene.');
}
lines.push('What happens on this page:');
lines.push(context.pageSummary);
if (context.prevSummary) {
lines.push('');
lines.push('What happened on the previous page'+(context.prevPlace ? ' ('+context.prevPlace+')' : '')+':');
lines.push(context.prevSummary);
}
if (context.nextSummary) {
lines.push('');
lines.push('What happens on the next page. Lead into it, do not draw it:');
lines.push(context.nextSummary);
}
lines.push('');
lines.push('Panel layout in reading order ('+(context.rightToLeft ? 'right to left' : 'left to right')+'):');
lines.push(JSON.stringify(context.layout));
return requestPanelPrompts(LLM_STORY_PANEL_SYSTEM,lines.join('\n'),context.layout.length,context.sceneChange);
}
