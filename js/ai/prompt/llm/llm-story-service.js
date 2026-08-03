// ストーリー1本から「登場人物とロケーションの設定 → 各ページの流れ → 各コマのプロンプト」を作る。
// コマの並べ替え・レイアウト要約・コマ応答のパース・役割の検証はllm-storyboard-service.jsの
// 関数をそのまま使い、実装を二重に持たない

// ユーザーの入力はページ数に対して短すぎるか長すぎる。短ければ各ページが空になり、
// 長ければ1ページに詰め込みすぎる。配分の前に両方向へ合わせる。
// 文面は llm_doc/manga-page-guideline.md の9・12・13章がそのまま元
const LLM_STORY_FIT_SYSTEM=[
'Rewrite the story so that it fits the given number of pages. Add, condense and cut as needed.',
'',
'Watch these points:',
'',
'- Do not change what the story already decides: who is in it, what happens, how it ends.',
'  Everything else is yours to add, shorten or drop so that the length comes out right.',
'',
'- When the story is too short for the pages, add what it leaves out: who the characters are and',
'  how they know each other, where it happens, why someone wants what they want, what stands in',
'  their way, the one scene the story is being told for, and how it ends.',
'',
// 指針9章。起承転結を並び順の型として渡すと4分割するだけになるので、仕事の側を渡す
'- Four jobs have to be in there somewhere. They are not four equal parts to line up in order:',
'    show whose story this is, and break what is normal for them',
'    let them move while it is broken, until what is in their way becomes something specific',
'    take the expected outcome away from them and from the reader. This is the scene it is for',
'    show what is different afterwards',
'  A story missing the third one is flat however many pages it runs. Nothing is left when it ends.',
'',
'- The order can be broken, and often should be. Open on the strongest scene and then go back to',
'  how it got there. Skip the setup and come in with something already happening. Stop right after',
'  the turn and leave the aftermath out. Break the obstacle and put a bigger one behind it.',
'  Pull the ground out twice. Pick one if the story is better for it; do not default to the plain',
'  order just because it is the plain order.',
'',
'- Whatever else you do, page one has to catch the reader, because if it loses them the rest is not',
'  read. Something is already happening, or something is being kept from them. Not the setting,',
'  not who everyone is. Save that.',
'',
'- The scene the story is for only lands if something quiet comes before it. Build to it. Two big',
'  moments back to back and neither reads as big.',
'',
'- When the story is too long for the pages, cut in this order: scenes that only explain something',
'  (travel, time passing, flashback), then minor characters and their scenes, then scenes that show',
'  the same thing twice, then the scenes furthest from the one you are telling it for.',
'  Keep that scene and the ending to the last. Cut those and there is no story left.',
'',
// 人数と場所の上限は物語の都合ではない。同一人物を保つ手段がタグの一致しかないため
'- Keep the cast to three or four people and the places to two or three. This is not a preference',
'  about storytelling. The drawing is done by an image model that has only matching tags to hold a',
'  face or a place steady, so every extra character and every extra location is one more thing that',
'  drifts from panel to panel. When cutting a long story, get down to this first.',
'',
'- One scene runs one to three pages. Work out how many scenes the page count holds before you',
'  write. Too many scenes and a scene gets less than a page, which is not enough to draw anything',
'  in. Too few and a scene is stretched over four or more pages and goes slack.',
'',
'- Give the characters plain names, so that the later steps can refer to them.',
'',
// 指針12章。設定を細かく作るのではなく、1つか2つを強く出す
'- A character the reader remembers is missing something and wants something. The lack is what makes',
'  them worth watching; the want is what makes them move. Give each of them one of each, and let the',
'  first thing they do on the page show it rather than telling us about it.',
'  Do not build out a full profile. One or two things stated strongly beat ten stated evenly.',
'',
// 指針12章。AI生成は似た見た目を描き分けられない
'- Make the characters tell apart at a glance: different hair length, different hair colour,',
'  different kind of clothing, and one thing each that nothing else in the story has (glasses, a hat,',
'  a scar, something they always carry). This is not decoration. The drawing is done by an image',
'  model, so two characters with similar hair and similar clothes come back mixed together.',
'',
'- Write one paragraph per scene. Each paragraph says where it is, who is there, and what happens.',
'',
'- Write what someone does, not what they feel or what is simply true of them. Not "he had always',
'  liked her" and not "she was sad", but "he started to speak to her, no words came, and he turned',
'  away". A feeling cannot be drawn. An action can.',
'',
'- Do not break it into pages or panels. That comes later.',
'',
'- Write in the same language as the story.',
'',
'- Return JSON only, shaped exactly as {"story":"..."}.'
].join('\n');

function parseStoryFit(raw) {
const parsed=parseLLMJsonBody(raw);
const story=parsed&&typeof parsed.story==='string' ? parsed.story.trim() : '';
if (!story) {
throw new Error(i18next.t('llmErrorEmptyResponse'));
}
return story;
}

// 戻り値: ページ数に合わせたストーリー本文
async function llmStoryFitToPages(story,pageCount) {
const target=requireLLMProvider(AI_ROLES.Text2Prompt);
const userPrompt=[
'Pages: '+pageCount,
'',
'Story:',
story
].join('\n');
const messages=target.provider.buildTextMessages(LLM_STORY_FIT_SYSTEM,userPrompt);
const raw=await target.queue.add(function () {
return target.provider.chat(messages,{temperature: 0.8,jsonObject: true});
});
return parseStoryFit(raw);
}

// キャラとロケーションを1回の呼び出しでまとめて作る。どちらも同じストーリーから引くため
const LLM_STORY_SHEET_SYSTEM=[
'Fix the recurring characters and the recurring places of this story as Danbooru style tags,',
'so that every panel can reuse them.',
'',
'Watch these points:',
'',
'- A sheet is for something that comes back. Someone who passes through one scene and is never seen',
'  again does not need one, and neither does a place the story only mentions.',
'',
'- Only what actually appears in the story. Do not invent extra characters or places.',
'',
'- Character tags are appearance and nothing else: age, hair, eyes, face, clothing, body type,',
'  accessories, shoes.',
'',
// 指針12章。似た見た目のキャラはAI生成で混ざる。ここで分けておく
'- Two characters must not read the same. Across the cast, vary hair length, hair colour and the kind',
'  of clothing, and give each one a tag nobody else has: glasses, a hat, a hair ornament, a scar,',
'  something they carry. The image model has nothing but these tags to tell them apart, so two',
'  characters tagged alike come back as the same face. If the story does not say, decide it here.',
'',
'- Do not put pose, expression, camera angle or background in character tags. Those change from',
'  panel to panel, and a sheet is copied into every panel that character appears in.',
'',
// 2人のコマでキャラ表を2つ並べると1girlが2回入り、solo寄りの偏りと噛み合って破綻する
'- Do not put a count tag in character tags: no "1girl", "1boy", "solo", "multiple girls".',
'  Two characters in one panel would then carry two count tags and the picture breaks.',
'  How many people are in a panel is decided panel by panel.',
'',
'- Location tags are the kind of place, the things in it worth naming, the time of day and the light.',
'  No people, no pose, no camera angle.',
'',
'- "name" is however the story refers to it, in the language of the story.',
'',
'- Return JSON only, shaped exactly as',
'  {"characters":[{"name":"...","tags":"tag, tag"}],"locations":[{"name":"...","tags":"tag, tag"}]}.',
'  All tags are comma separated lowercase Danbooru style tags.'
].join('\n');

// 起承転結を型として渡すと必ず4分割してくる。手順と判断の材料だけ渡す。
// 文面は llm_doc/manga-page-guideline.md の11・14章がそのまま元
const LLM_STORY_PAGEPLAN_SYSTEM=[
'Spread this story over the pages you are given, and write what happens on each one.',
'',
'Work in this order:',
'1. Decide the one scene the story is being told for.',
'2. Decide which page that scene lands on. Two thirds to three quarters of the way through, unless',
'   the story opens on it and works back to how it got there.',
'3. Spread what leads up to it over the pages before.',
'4. Spread what follows over the pages after.',
'',
'Watch these points:',
'',
'- Pages are weight. A scene given three pages reads as important; the same scene in half a page',
'  reads as something passed on the way. Spend them accordingly:',
'    a scene that only explains something (travel, time passing)  one page or less, or cut it',
'    a scene where the story moves                                one or two pages',
'    the scene the story is being told for                        two or three pages',
'',
'- Page 1 has to give the reader a reason to keep going before it gives them anything to understand.',
'  Open in the middle of something happening, or with something withheld. Not on the setting.',
'  Page 1 also has to carry one image strong enough to be worth a large panel. If the story does',
'  not offer one at the start, move one there and go back to how it got there afterwards.',
'',
'- The last page answers what page 1 raised, or answers it in a way the reader did not expect.',
'',
// 指針9章。溜めと落差。これが無いと全ページ同じ密度になる
'- Put something quiet on the page before the one the story is for. A big moment with nothing',
'  before it does not read as big. Two of them back to back and neither does.',
'',
'- The reader reacts to change, not to level. Loud then empty, crowded then alone, talking then',
'  silent, far then close. A run of pages at one pitch stops registering whatever happens in them.',
'',
'- A page with many panels carries several beats. A page with few panels carries one moment.',
'  A page with many panels also has less room in each of them, so keep what happens on it simple.',
'',
// 指針11章。読者は絵より先にセリフを読む
'- The reader reads the words before they look at the picture. A page carrying a lot of talk cannot',
'  also carry the big view; a page carrying the big view has to be quiet. Decide which one each',
'  page is doing.',
'',
'- Keep "location" and "time" worded exactly the same while the story stays in one place, and change',
'  the wording only when the story actually moves. The next step reads those two strings to decide',
'  which pages open on the place, so a reworded string reads as a new place.',
'',
'- Do not break it down panel by panel. That comes later.',
'',
'- Return JSON only, shaped exactly as',
'  {"pages":[{"page":1,"summary":"...","location":"...","time":"..."}]}.',
'  One entry for every page number you received; do not add or drop pages.',
'  "summary" is 1 to 3 sentences naming the characters who are present. "location" is a short noun',
'  phrase, "time" a short word. All three in the language of the story.'
].join('\n');

const LLM_STORY_PANEL_SYSTEM=buildPanelSystemPrompt(
[
// キャラ表をそのまま全部コピーさせると、顔だけのコマにも靴が入って勝手に引いた絵になる。
// フレームに入る範囲だけ使わせる（→ llm_doc/prompt-composition.md）
'- From the character sheet take only what is inside that panel\'s frame. Face and hair every time,'
+' so the reader knows it is the same person. Clothing when the body is in frame. Shoes only when'
+' the feet are in frame. Naming a part that sits outside the frame drags the view back out to it.',
'- Copy the location sheet tags word for word into every panel that happens in that place.'
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
