// コマの役割（role）から構図タグを決めて、書き込み側で足す。
//
// なぜLLMに書かせないか: 学習データの偏りを埋めるのが目的なので、毎回同じ強さで
// 入っていないと意味がない。画風タグ（appendMangaStyleSuffix）と同じ理由で決め打つ。
//
// なぜ必要か: Danbooruの件数を見ると cowboy_shot 831,263件に対し wide_shot 23,183件、
// very_wide_shot 2,190件。looking_at_viewer は 4,793,726件で全体の過半数。
// 何も指定しなければ「1人・膝上・正面・カメラ目線」に落ちる。漫画のコマが取らない構図。

const PANEL_COMPOSITION_ROLE_ORDER=['establishing','scenery','insert','full','medium','closeup','impact'];

// 役割ごとの土台。プリセットはこれを上書きして作る
const PANEL_COMPOSITION_BASE={
establishing:{
positive:'(wide shot:1.3), scenery, from above',
negative:'close-up, portrait, upper body, cowboy shot, solo, looking at viewer'
},
scenery:{
positive:'scenery, (wide shot:1.2)',
negative:'close-up, portrait, upper body, cowboy shot, looking at viewer'
},
insert:{
positive:'close-up, cut-in, depth of field',
negative:'full body, wide shot, scenery, looking at viewer'
},
full:{
positive:'full body',
negative:'close-up, portrait, upper body, looking at viewer'
},
medium:{
positive:'upper body, looking at another',
negative:'close-up, wide shot, looking at viewer'
},
closeup:{
positive:'close-up, portrait',
negative:'full body, wide shot, cowboy shot'
},
impact:{
positive:'dutch angle, from below, foreshortening, (emphasis lines:1.2)',
negative:'straight-on, looking at viewer'
}
};

// 作品の傾向。土台からの差分だけ書く。
// 「常に同じ調整が要るわけではない」ので、傾向ごとに寄せる先を変える
const PANEL_COMPOSITION_PRESETS={
none:null,
general:{},
// 青年向け: 引きと間で読ませる。ミドルも膝上まで引く
seinen:{
establishing:{positive:'(wide shot:1.4), (very wide shot:1.2), scenery, from above, atmospheric perspective'},
scenery:{positive:'scenery, (wide shot:1.3), atmospheric perspective'},
full:{positive:'full body, (wide shot:1.2)'},
medium:{positive:'cowboy shot, looking at another',negative:'close-up, portrait, upper body, looking at viewer'},
impact:{positive:'dutch angle, from below, perspective, foreshortening'}
},
// 少年向け: 見せ場を強く。あおりと効果線は件数が少ないので重みで底上げする
shonen:{
medium:{positive:'upper body, looking at another, dutch angle'},
closeup:{positive:'close-up, portrait, (emphasis lines:1.1)'},
impact:{positive:'dutch angle, (from below:1.2), foreshortening, (speed lines:1.3), (emphasis lines:1.3), motion blur'}
},
// 少女漫画: 表情と余白。背景は落として人物を浮かせる
shojo:{
establishing:{positive:'(wide shot:1.2), scenery'},
insert:{positive:'close-up, cut-in, depth of field, blurry background'},
medium:{positive:'upper body, looking at another, blurry background'},
closeup:{positive:'close-up, portrait, blurry background, bokeh'},
impact:{positive:'dutch angle, foreshortening, (emphasis lines:1.2), bokeh'}
},
// 成人向け: 局所の寄りが主。引きは場所を示す最低限に留める
adult:{
establishing:{positive:'(wide shot:1.2), scenery'},
scenery:{positive:'scenery, (wide shot:1.1)'},
insert:{positive:'(close-up:1.3), cut-in, depth of field',negative:'full body, wide shot, scenery'},
medium:{positive:'(close-up:1.1), upper body, looking at another'},
closeup:{positive:'(close-up:1.3), portrait',negative:'full body, wide shot, cowboy shot, scenery'},
impact:{positive:'dutch angle, from below, foreshortening'}
}
};

// 重み記法の付け方が違うだけの同じタグを二重に入れないため、素のタグ名で比べる。
// (wide shot:1.3) → wide shot
function compositionTagKey(tag) {
let key=String(tag||'').trim().toLowerCase();
while (key.length>2&&(key.charAt(0)==='('||key.charAt(0)==='[')) {
const close=key.charAt(0)==='(' ? ')' : ']';
if (key.charAt(key.length-1)!==close) {
break;
}
key=key.slice(1,-1).trim();
}
key=key.replace(/:\s*-?\d+(\.\d+)?$/,'').trim();
return key.replace(/_/g,' ').replace(/\s{2,}/g,' ');
}

function compositionSplit(text) {
return String(text||'').split(',').map(function (part) {
return part.trim();
}).filter(function (part) {
return part;
});
}

// 既に入っているタグは足さない。exclude に入っているタグも足さない
// （ポジティブに書かれているタグをネガティブへ入れると打ち消し合うため）
function compositionMissingTags(current,extra,exclude) {
const seen={};
compositionSplit(current).forEach(function (part) {
const key=compositionTagKey(part);
if (key) seen[key]=true;
});
compositionSplit(exclude).forEach(function (part) {
const key=compositionTagKey(part);
if (key) seen[key]=true;
});
const add=[];
compositionSplit(extra).forEach(function (tag) {
const key=compositionTagKey(tag);
if (!key||seen[key]) {
return;
}
seen[key]=true;
add.push(tag);
});
return add;
}

function compositionJoin(current,add) {
const base=String(current||'').trim().replace(/,+$/,'').trim();
if (add.length===0) {
return base;
}
const joined=add.join(', ');
return base ? base+', '+joined : joined;
}

// 前回この仕組みが足したタグだけを外す。ユーザーが手で書いたタグには触らない。
// 役割が変わって作り直したときに、前の役割のタグが残り続けるのを防ぐ
function compositionStrip(text,added) {
if (!added) {
return String(text||'').trim().replace(/,+$/,'').trim();
}
const drop={};
compositionSplit(added).forEach(function (part) {
const key=compositionTagKey(part);
if (key) drop[key]=true;
});
return compositionSplit(text).filter(function (part) {
return!drop[compositionTagKey(part)];
}).join(', ');
}

// プリセットを役割ごとの表に展開する。none は空
function panelCompositionPreset(name) {
const diff=PANEL_COMPOSITION_PRESETS[name];
if (!diff) {
return {};
}
const table={};
PANEL_COMPOSITION_ROLE_ORDER.forEach(function (role) {
const base=PANEL_COMPOSITION_BASE[role];
const over=diff[role]||{};
table[role]={
positive: typeof over.positive==='string' ? over.positive : base.positive,
negative: typeof over.negative==='string' ? over.negative : base.negative
};
});
return table;
}

// 詳細編集の欄に出す文面。1行1役割
function panelCompositionToText(table,field) {
return PANEL_COMPOSITION_ROLE_ORDER.filter(function (role) {
return table[role]&&table[role][field];
}).map(function (role) {
return role+': '+table[role][field];
}).join('\n');
}

// 戻り値: {map:{role:tags}, unknown:[表記]}
// 知らない役割名は黙って捨てずに返す。捨てると効いていないことに気付けない
function parsePanelCompositionText(text) {
const map={};
const unknown=[];
String(text||'').split('\n').forEach(function (line) {
const raw=line.trim();
if (!raw||raw.charAt(0)==='#') {
return;
}
const sep=raw.indexOf(':');
if (sep<0) {
unknown.push(raw);
return;
}
const role=raw.slice(0,sep).trim().toLowerCase();
const tags=raw.slice(sep+1).trim();
if (PANEL_COMPOSITION_ROLE_ORDER.indexOf(role)<0) {
unknown.push(raw.slice(0,sep).trim());
return;
}
if (!tags) {
return;
}
map[role]=map[role] ? map[role]+', '+tags : tags;
});
return {map: map,unknown: unknown};
}

// 画面で編集された表を読む。欄が真実であり、プリセットは欄を書き換えるだけ。
// 何が足されるかは常に画面に出ている状態にする
function panelCompositionTable() {
return {
positive: parsePanelCompositionText($('storyCompositionTags').value),
negative: parsePanelCompositionText($('storyCompositionNegative').value)
};
}

// 役割に対して足すタグ。役割が空（LLMが知らない名前を返した）なら何も足さない
function panelCompositionForRole(role) {
if (!role) {
return {positive: '',negative: ''};
}
const table=panelCompositionTable();
return {
positive: table.positive.map[role]||'',
negative: table.negative.map[role]||''
};
}

// 詳細編集の欄に書かれた知らない役割名。生成前に画面へ出す
function panelCompositionUnknownRoles() {
const table=panelCompositionTable();
const seen={};
const list=[];
table.positive.unknown.concat(table.negative.unknown).forEach(function (name) {
if (!name||seen[name]) {
return;
}
seen[name]=true;
list.push(name);
});
return list;
}

// プレビューに併記する読み取り専用の1〜2行。実際に足されるものだけを出す。
// 既にプロンプトへ入っているタグは足されないので、ここにも出さない
function buildPanelCompositionNote(panel,role,prompt) {
const composition=panelCompositionForRole(role);
if (!composition.positive&&!composition.negative) {
return '';
}
const added=panel.text2img_composition||{positive: '',negative: ''};
const merged=appendMangaStyleSuffix(compositionStrip(prompt,added.positive));
const addPositive=compositionMissingTags(merged,composition.positive,'');
const finalPositive=compositionJoin(merged,addPositive);
const currentNegative=compositionStrip(panel.text2img_negative,added.negative);
const addNegative=compositionMissingTags(currentNegative,composition.negative,finalPositive);
const lines=[];
if (addPositive.length>0) {
lines.push(i18next.t('storyCompositionAdd')+' '+addPositive.join(', '));
}
if (addNegative.length>0) {
lines.push(i18next.t('storyCompositionDrop')+' '+addNegative.join(', '));
}
return lines.join('\n');
}

// SDXLの学習解像度。これ以外の比率で描かせると構図が破綻する。
// 極端な帯コマは端のバケットに寄せて生成し、コマ側で切り出す
const PANEL_SDXL_BUCKETS=[
{width: 640,height: 1536},
{width: 768,height: 1344},
{width: 832,height: 1216},
{width: 896,height: 1152},
{width: 1024,height: 1024},
{width: 1152,height: 896},
{width: 1216,height: 832},
{width: 1344,height: 768},
{width: 1536,height: 640}
];

function pickPanelSDXLBucket(width,height) {
if (!(width>0)||!(height>0)) {
return null;
}
const target=Math.log(width/height);
let best=PANEL_SDXL_BUCKETS[0];
let bestDiff=Infinity;
PANEL_SDXL_BUCKETS.forEach(function (bucket) {
const diff=Math.abs(Math.log(bucket.width/bucket.height)-target);
if (diff<bestDiff) {
bestDiff=diff;
best=bucket;
}
});
return best;
}

// プリセットを欄へ書き出す。欄が真実なので、選び直したら見えている文面も入れ替える。
// 設定の自動保存はinputイベントを見ているので、代入だけでは保存されない
function panelCompositionFillFromPreset() {
const table=panelCompositionPreset($('storyComposition').value);
[['storyCompositionTags','positive'],['storyCompositionNegative','negative']].forEach(function (pair) {
const el=$(pair[0]);
el.value=panelCompositionToText(table,pair[1]);
el.dispatchEvent(new Event('input',{bubbles: true}));
});
panelCompositionValidate();
}

// 知らない役割名を書いても黙って無視すると、効いていないことに気付けない
function panelCompositionValidate() {
const unknown=panelCompositionUnknownRoles();
llmStorySetStatus(unknown.length>0
? i18next.t('storyCompositionUnknown')+' '+unknown.join(', ')
: '');
}

document.addEventListener('DOMContentLoaded',function () {
const tags=$('storyCompositionTags');
const negative=$('storyCompositionNegative');
// 設定の復元より後に動く。保存された文面があればそれを残し、
// 初回だけプリセットを流し込む
if (!tags.value.trim()&&!negative.value.trim()) {
panelCompositionFillFromPreset();
}
$('storyComposition').addEventListener('change',panelCompositionFillFromPreset);
tags.addEventListener('input',panelCompositionValidate);
negative.addEventListener('input',panelCompositionValidate);
EventDelegator.register('llmStoryCompositionReset',panelCompositionFillFromPreset);
});

function panelCompositionSizeEnabled() {
return $('storyPanelSizeFromShape').checked;
}

// コマの形から生成解像度を決める。横長コマに引きの絵を割り当てても、
// 正方形で生成して嵌めると上下が切られて結局バストアップに見えるため
function panelCompositionApplySize(panel) {
if (!panelCompositionSizeEnabled()) {
return;
}
const rect=panel.getBoundingRect();
const bucket=pickPanelSDXLBucket(rect.width,rect.height);
if (!bucket) {
return;
}
panel.text2img_width=bucket.width;
panel.text2img_height=bucket.height;
}
