// preset-panel.js - ペン／トーン／画像テキストの「今のプリセット」カード
//
// パネル幅は200px（狭い画面で140px）しかなく、一覧と設定を同じ縦列に並べると
// 一覧が場所を取って設定が画面外へ押し出される。一覧は選ぶときだけ
// PresetPickerで広く開き、パネルには今のプリセットだけを置く。
//
// カードの更新は各マネージャが元から持っている「activeボタンを付け外しする1か所」
// （switchPencilType / switchMangaTone / switchText2Ui）からだけ呼ぶ。
// 切り替え経路ごとに書き足すと更新漏れになる。

var PRESET_PANELS={
pen: {
cardId: "penPresetCurrent",
titleKey: "penPickerTitle",
current: function () {return nowPencil;},
pick: function (value) {switchPencilType(value);},
items: [
{value: "Marker",labelKey: "Marker",hintKey: "penDescMarker",img: "03_images/preset/brush/Marker.webp"},
{value: "Ink",labelKey: "ink",hintKey: "penDescInk",img: "03_images/preset/brush/Ink.webp"},
{value: "Crayon",labelKey: "crayon",hintKey: "penDescCrayon",img: "03_images/preset/brush/Crayon.webp"},
{value: "Pencil",labelKey: "Pencil",hintKey: "penDescPencil",img: "03_images/preset/brush/Pencil.webp"},
{value: "OutlinePen",labelKey: "OutlinePen",hintKey: "penDescOutlinePen",img: "03_images/preset/brush/OutlinePen.webp"},
{value: "Circle",labelKey: "Circle",hintKey: "penDescCircle",img: "03_images/preset/brush/Circle.webp"},
{value: "Mosaic",labelKey: "Mosaic",hintKey: "penDescMosaic",img: "03_images/preset/brush/Mosaic1.webp"},
{value: "Eraser",labelKey: "Eraser",hintKey: "penDescEraser",img: "03_images/preset/brush/Eraser.webp"}
]
},
tone: {
cardId: "tonePresetCurrent",
titleKey: "tonePickerTitle",
current: function () {return nowTone;},
pick: function (value) {switchMangaTone(value);},
items: [
{value: "Tone",labelKey: "Tone",hintKey: "toneDescTone",img: "03_images/preset/tone/Tone.webp"},
{value: "ToneNoise",labelKey: "ToneNoise",hintKey: "toneDescToneNoise",img: "03_images/preset/tone/ToneNoise.webp"},
{value: "ToneSnow",labelKey: "ToneSnow",hintKey: "toneDescToneSnow",img: "03_images/preset/tone/ToneSnow.webp"},
{value: "SpeedLine",labelKey: "SpeedLine",hintKey: "toneDescSpeedLine",img: "03_images/preset/tone/SpeedLine.webp"},
{value: "FocusingLine",labelKey: "FocusingLine",hintKey: "toneDescFocusingLine",img: "03_images/preset/tone/FocusingLine.webp"}
]
},
text2: {
cardId: "imageTextPresetCurrent",
titleKey: "imageTextPickerTitle",
current: function () {return nowText2;},
pick: function (value) {switchText2(value);},
items: [
{value: "shadow",labelKey: "shadow",hintKey: "imageTextDescShadow",img: "03_images/preset/text/t2_shadow.webp"},
{value: "wild",labelKey: "wild",hintKey: "imageTextDescWild",img: "03_images/preset/text/t2_wild.webp"},
{value: "scratch",labelKey: "scratch",hintKey: "imageTextDescScratch",img: "03_images/preset/text/t2_scratch.webp"},
{value: "broken",labelKey: "broken",hintKey: "imageTextDescBroken",img: "03_images/preset/text/t2_broken.webp"},
{value: "cloud",labelKey: "cloud",hintKey: "imageTextDescCloud",img: "03_images/preset/text/t2_cloud.webp"},
{value: "layered",labelKey: "layered",hintKey: "imageTextDescLayered",img: "03_images/preset/text/t2_layered.webp"},
{value: "mesh",labelKey: "mesh",hintKey: "imageTextDescMesh",img: "03_images/preset/text/t2_mesh.webp"},
{value: "thrill",labelKey: "thrill",hintKey: "imageTextDescThrill",img: "03_images/preset/text/t2_thrill.webp"},
{value: "zebra",labelKey: "zebra",hintKey: "imageTextDescZebra",img: "03_images/preset/text/t2_zebra.webp"}
]
}
};

function presetPanelFindItem(kind,value) {
var conf=PRESET_PANELS[kind];
var found=null;
conf.items.forEach(function (item) {
if (item.value===value) {
found=item;
}
});
return found;
}

// 選んだプリセットをカードに映し、使用中であることを示す。
// 名前は data-i18n を付け替えて入れるので、言語切替時の updateContent() が拾える
function presetPanelSetActive(kind,value) {
var conf=PRESET_PANELS[kind];
var card=$(conf.cardId);
if (!card) {
uiLogger.error("preset card not found: "+conf.cardId);
return;
}
var item=presetPanelFindItem(kind,value);
if (!item) {
uiLogger.error("unknown preset: "+kind+" / "+value);
return;
}
var name=card.querySelector(".preset-current-name");
name.dataset.i18n=item.labelKey;
name.textContent=getText(item.labelKey);
var thumb=card.querySelector(".preset-current-thumb");
thumb.src=item.img;
thumb.hidden=false;
card.classList.add("is-active");
}

// 使用中の表示だけを落とす。どれを選んでいたかは残す
function presetPanelClearActive(kind) {
var card=$(PRESET_PANELS[kind].cardId);
if (!card) {
return;
}
card.classList.remove("is-active");
}

// 翻訳は開く直前に引く。言語切替後も開き直せば新しい言語で出る
function presetPanelOpenPicker(kind) {
var conf=PRESET_PANELS[kind];
if (!conf) {
uiLogger.error("unknown preset panel: "+kind);
return;
}
var items=conf.items.map(function (item) {
return {
value: item.value,
label: getText(item.labelKey),
hint: getText(item.hintKey),
img: item.img
};
});
PresetPicker.open({
title: getText(conf.titleKey),
items: items,
currentValue: conf.current(),
onPick: conf.pick
});
}

EventDelegator.register('openPresetPicker',function (el) {
presetPanelOpenPicker(el.dataset.presetKind);
});
