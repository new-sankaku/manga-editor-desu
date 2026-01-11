/**
 * knife-state.js
 * ナイフツールの状態管理
 */

const knifeState={
// 現在のナイフ対象オブジェクト
currentObject: null,

// 現在の分割線
currentLine: null,

// ナイフ開始座標
startX: 0,
startY: 0,

// アニメーション関連
animationId: null,
dashOffset: 0,

// ナイフ補助角度（UI設定値を保持）
assistAngle: KNIFE_CONSTANTS.KNIFE_ASSIST_ANGLE,

/**
     * 状態をリセット
     */
reset: function() {
this.currentObject=null;
this.currentLine=null;
this.startX=0;
this.startY=0;
this.animationId=null;
this.dashOffset=0;
},

/**
     * 開始位置を設定
     */
setStartPosition: function(x,y) {
this.startX=x;
this.startY=y;
}
};

// 後方互換性のためのグローバル変数（getter/setter経由）
var knifeAssistAngle=KNIFE_CONSTANTS.KNIFE_ASSIST_ANGLE;
var currentKnifeObject=null;
var currentKnifeLine=null;
var startKnifeX=0;
var startKnifeY=0;
var knifeLineAnimationId=null;
var knifeLineDashOffset=0;

// 方向定数（後方互換性）
var isHorizontalInt=KNIFE_CONSTANTS.DIRECTION.HORIZONTAL;
var isVerticalInt=KNIFE_CONSTANTS.DIRECTION.VERTICAL;
var isErrorInt=KNIFE_CONSTANTS.DIRECTION.ERROR;
