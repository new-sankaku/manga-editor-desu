// preset-picker.js - 一覧から1件選ぶためのポップアップ
//
// <select>は閉じている間ずっと中身が見えず、GLFXの15種のように
// 名前だけでは区別しづらいものを選ぶのに向かない。開いた状態で全件を並べ、
// 絞り込みも効くようにする。
//
// 呼び出し側は「元となる要素（<select>等）」を持ったまま値の反映だけを受け取る。
// 一覧をこちらで二重に持つと項目追加時の修正漏れになるため、items は都度渡す。

var PresetPicker=(function () {

var root=null;
var listEl=null;
var titleEl=null;
var searchEl=null;
var state={items: [],currentValue: null,onPick: null};

function build() {
root=document.createElement('div');
root.className='preset-picker-back';
root.innerHTML=
'<div class="preset-picker">'
+'<div class="ppk-head">'
+'<h3 class="ppk-title"></h3>'
+'<div class="ppk-search">'
+'<i class="material-icons">search</i>'
+'<input type="text" class="ppk-search-input">'
+'</div>'
+'<button type="button" class="ppk-close"><i class="material-icons">close</i></button>'
+'</div>'
+'<div class="ppk-list"></div>'
+'<div class="ppk-foot"></div>'
+'</div>';
document.body.appendChild(root);

listEl=root.querySelector('.ppk-list');
titleEl=root.querySelector('.ppk-title');
searchEl=root.querySelector('.ppk-search-input');

// 個々の項目にリスナを付けず、ルート1か所で受ける。
// 暗幕を押したときの終了は外側クリック側（onOutsideMouseDown）で一括して扱う
root.addEventListener('click',function (e) {
if (e.target.closest('.ppk-close')) {
close();
return;
}
var item=e.target.closest('.ppk-item');
if (!item) {
return;
}
var value=item.dataset.value;
var callback=state.onPick;
close();
if (callback) {
callback(value);
}
});

searchEl.addEventListener('input',function () {
render(this.value);
});

document.addEventListener('keydown',function (e) {
if (e.key==='Escape'&&isOpen()) {
close();
}
});
}

function render(query) {
var needle=(query||'').trim().toLowerCase();
listEl.innerHTML='';
var shown=0;

state.items.forEach(function (item) {
var label=item.label||'';
var hint=item.hint||'';
if (needle&&label.toLowerCase().indexOf(needle)<0&&hint.toLowerCase().indexOf(needle)<0) {
return;
}
shown++;
var button=document.createElement('button');
button.type='button';
button.className='ppk-item'+(item.value===state.currentValue ? ' is-current' : '');
button.dataset.value=item.value;

var name=document.createElement('span');
name.className='ppk-item-name';
name.textContent=label;
button.appendChild(name);

if (hint) {
var hintEl=document.createElement('span');
hintEl.className='ppk-item-hint';
hintEl.textContent=hint;
button.appendChild(hintEl);
}

// 名前だけでは区別できないもの（GLFXのDot ScreenとColor Halftone等）が
// あるため、見本画像に効果を掛けて並べる
if (item.img) {
var img=document.createElement('img');
img.className='ppk-item-thumb';
img.src=item.img;
img.alt='';
if (item.imgFilter) {
img.style.filter=item.imgFilter;
}
button.appendChild(img);
}
listEl.appendChild(button);
});

if (shown===0) {
var empty=document.createElement('p');
empty.className='ppk-empty';
empty.textContent=getText('presetPickerNoMatch');
listEl.appendChild(empty);
}
}

function isOpen() {
return!!root&&root.classList.contains('is-open');
}

// ピッカーの外を押したら閉じる。暗幕はパネルの右側しか覆っていないため、
// 暗幕の外（サイドバー側）も拾えるようdocumentで受ける。
// ピッカーはボタンのclickで開くので、clickより前のmousedownで受ければ
// 開いた操作自身で閉じてしまうことはない。
// pointerdownではなくmousedownなのは、pointerdownで暗幕を消すと
// 直後のmousedownが下のキャンバスに届いてしまうため
function onOutsideMouseDown(e) {
if (!isOpen()) {
return;
}
var target=e.target;
if (!target||typeof target.closest!=='function') {
return;
}
if (target.closest('.preset-picker')) {
return;
}
close();
}

function close() {
if (!root) {
return;
}
document.removeEventListener('mousedown',onOutsideMouseDown,true);
root.classList.remove('is-open');
root.style.left='';
state.onPick=null;
}

// 表示中のサイドバーパネル。ピッカーはその右隣に出す
function visiblePanel() {
var panels=document.querySelectorAll('.left_area');
for (var i=0;i<panels.length;i++) {
if (panels[i].offsetParent!==null) {
return panels[i];
}
}
return null;
}

// パネルのすぐ右、キャンバスの上に開く。画面中央のモーダルにすると
// 「どのパネルの操作なのか」が切れてしまう
function place() {
var panel=visiblePanel();
var box=root.querySelector('.preset-picker');
if (!panel) {
root.style.left='0px';
box.style.top='';
box.style.left='';
box.classList.add('is-centered');
return;
}
var rect=panel.getBoundingClientRect();
root.style.left=rect.right+'px';
box.classList.remove('is-centered');
box.style.top=(rect.top+10)+'px';
box.style.left=(rect.right+10)+'px';
box.style.maxHeight=(rect.height-20)+'px';
}

// options: {title, items:[{value,label,hint,img,imgFilter}], currentValue, onPick(value)}
function open(options) {
if (!root) {
build();
}
state.items=options.items||[];
state.currentValue=options.currentValue===undefined ? null : options.currentValue;
state.onPick=options.onPick||null;

titleEl.textContent=options.title||'';
searchEl.placeholder=getText('presetPickerSearch');
searchEl.value='';
root.querySelector('.ppk-foot').textContent=getText('presetPickerFoot');
render('');
root.classList.add('is-open');
place();
// 同じ関数参照なので開き直しても多重登録にはならない
document.addEventListener('mousedown',onOutsideMouseDown,true);
searchEl.focus();
}

// <select>をそのまま一覧に変換する。項目の追加・削除は<select>側だけを直せばよい。
// meta は value をキーにした {hint, img, imgFilter} の追加情報
function openFromSelect(selectElement,title,meta) {
if (!selectElement) {
uiLogger.warn('PresetPicker.openFromSelect: select not found');
return;
}
var extra=meta||{};
var items=[];
Array.prototype.forEach.call(selectElement.options,function (option) {
if (!option.value) {
return;
}
var info=extra[option.value]||{};
items.push({
value: option.value,
label: option.textContent,
hint: info.hint,
img: info.img,
imgFilter: info.imgFilter
});
});
open({
title: title,
items: items,
currentValue: selectElement.value,
onPick: function (value) {
selectElement.value=value;
selectElement.dispatchEvent(new Event('change',{bubbles: true}));
}
});
}

return {open: open,openFromSelect: openFromSelect,close: close,isOpen: isOpen};

})();
