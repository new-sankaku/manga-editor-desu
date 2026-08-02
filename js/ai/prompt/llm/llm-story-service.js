// ストーリー1本から「登場人物とロケーションの設定 → 各ページの流れ → 各コマのプロンプト」を作る。
// コマの並べ替え・レイアウト要約・コマ応答のパース・役割の検証はllm-storyboard-service.jsの
// 関数をそのまま使い、実装を二重に持たない

// キャラとロケーションを1回の呼び出しでまとめて作る。どちらも同じストーリーから引くため
const LLM_STORY_SHEET_SYSTEM=[
'You are a character designer and an art director for anime and manga style Stable Diffusion image generation.',
'You receive the synopsis of a manga story.',
'Fix the recurring characters and the recurring places as Danbooru style tags, so that every panel can reuse them.',
'Rules:',
'- Return JSON only, shaped exactly as {"characters":[{"name":"...","tags":"tag, tag"}],"locations":[{"name":"...","tags":"tag, tag"}]}.',
'- "name" is how the synopsis refers to it. Keep the language of the synopsis.',
'- All "tags" are comma separated lowercase Danbooru style tags.',
'- Character tags cover appearance only: sex, age, hair, eyes, clothing, body type, accessories. 6 to 15 tags each.',
'- Do not put pose, expression, camera angle or background in character tags. Those change from panel to panel.',
'- Location tags cover the kind of place, its notable objects, the time of day and the light. 5 to 12 tags each.',
'- Do not put people, pose or camera angle in location tags.',
'- Only characters and places that actually appear in the synopsis. Do not invent extra ones.',
'- At most 6 characters and at most 6 places.'
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
'- Pace the story so that it opens on the first page and resolves on the last page.',
'- A page with many panels carries several beats. A page with few panels carries one big moment.',
'- Do not write it panel by panel here. That comes in a later step.'
].join('\n');

const LLM_STORY_PANEL_SYSTEM=buildPanelSystemPrompt(
'what happens on one manga page',
[
'- When a character sheet is given, copy those appearance tags verbatim into every panel where the character appears, so the same person stays recognisable.',
'- When a location sheet is given, copy those place tags verbatim into every panel that happens in that place, so the reader stays in one location.'
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
if (context.characterSheet) {
lines.push('Character sheet (copy these appearance tags verbatim):');
lines.push(context.characterSheet);
lines.push('');
}
if (context.locationSheet) {
lines.push('Location sheet (copy these place tags verbatim):');
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
