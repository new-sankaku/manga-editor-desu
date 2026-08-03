// コマの構図まわり。ここが持つのは3つだけ。
//
// 1. 作品傾向をLLMへ渡す文面（MANGA_TONE_PRESETS）
//    どのコマを寄りにして、どのコマを引きにするかは**LLMに判断させる**。
//    役割ごとにタグを決め打つ表は持たない。フレーミングタグは効きが弱く、
//    表で入れても補助にしかならないため（→ llm_doc/prompt-composition.md）
// 2. 見切れのネガティブ（MANGA_FRAME_NEGATIVE_DEFAULT）
//    これだけは判断の余地がないので固定で入れる。見切れは後から直せない
// 3. コマの形からSDXLの学習解像度を選ぶ（PANEL_SDXL_BUCKETS）

// 作品傾向。タグではなく、LLMに読ませる指示文。
// 「常に同じ調整が要るわけではない」ので、寄りと引きのどちらへ寄せるかだけを伝える
// 「こう描け」ではなく「読者が何を求めて読んでいるか」を書く。
// 距離を決めるのはLLMなので、決めるための材料の側を渡す
const MANGA_TONE_PRESETS={
none: '',
general:
'Nothing pulls this page in one direction. Set the distance by what the reader still has to learn: '
+'where they are, then who is there, then what that person feels. '
+'A page where every panel sits at the same distance has no variation for the reader to follow.',
seinen:
'This work follows the conventions of seinen manga. The reader is following the situation as much '
+'as the person, so show where events are happening and how the characters are placed inside it. '
+'Keep the surroundings in view. Use tight close-ups only on the panels that require them.',
shonen:
'This work follows the conventions of shonen manga. The page builds towards one moment. Keep '
+'everything before it moving. Put the tilt, the low viewpoint and the motion on that one panel, '
+'and give it the space on the page.',
shojo:
'This work follows the conventions of shojo manga. The reader is following what a character feels, '
+'so the face carries the information and the background does not. Use small details in place of '
+'what is not said aloud.',
adult:
'This work focuses on the characters themselves. The reader\'s attention is on the bodies, so the '
+'place only has to be established once and can then be left out. Close and partial views carry '
+'the page. Use a wide view to tell the reader the scene has moved.'
};

// 見切れ。腕や足が枠で切れた絵は後から直しようがないので常にネガティブへ入れる。
// 意図して切りたいときは、生成後にコマの枠へ接するよう画像側を動かす。
// Danbooruに実在する表記だけを使う（hand out of frame は0件なので入れない）
const MANGA_FRAME_NEGATIVE_DEFAULT='out of frame, cropped, cropped legs, cropped torso, '
+'cropped arms, cropped shoulders, head out of frame, feet out of frame, '
+'foot out of frame, knees out of frame';

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

// 画面の欄が真実。プリセットは欄を書き換えるだけで、何をLLMへ渡すかは常に見えている
function mangaToneGuidance() {
return $('storyToneGuidance').value.trim();
}

function mangaFrameNegative() {
return $('storyFrameNegative').value.trim();
}

// 見切れのネガティブを足す。手書きのネガティブは消さない。
// ポジティブに書かれているタグは打ち消し合うので入れない
function panelApplyFrameNegative(panel) {
const add=compositionMissingTags(panel.text2img_negative,mangaFrameNegative(),panel.text2img_prompt);
panel.text2img_negative=compositionJoin(panel.text2img_negative,add);
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

function panelCompositionSizeEnabled() {
return $('storyPanelSizeFromShape').checked;
}

// コマの形から生成解像度を決める。横長コマに引きの絵を頼んでも、
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

// プリセットを欄へ書き出す。設定の自動保存はinputイベントを見ているので、
// 代入だけでは保存されない
function mangaToneFillFromPreset() {
const el=$('storyToneGuidance');
el.value=MANGA_TONE_PRESETS[$('storyComposition').value]||'';
el.dispatchEvent(new Event('input',{bubbles: true}));
}

function mangaFrameNegativeReset() {
const el=$('storyFrameNegative');
el.value=MANGA_FRAME_NEGATIVE_DEFAULT;
el.dispatchEvent(new Event('input',{bubbles: true}));
}

document.addEventListener('DOMContentLoaded',function () {
// 設定の復元より後に動く。保存された文面があればそれを残し、初回だけ流し込む
if (!$('storyToneGuidance').value.trim()) {
mangaToneFillFromPreset();
}
if (!$('storyFrameNegative').value.trim()) {
mangaFrameNegativeReset();
}
$('storyComposition').addEventListener('change',mangaToneFillFromPreset);
EventDelegator.register('llmStoryToneReset',mangaToneFillFromPreset);
EventDelegator.register('llmStoryFrameNegativeReset',mangaFrameNegativeReset);
});
