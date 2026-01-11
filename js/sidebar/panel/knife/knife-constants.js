/**
 * knife-constants.js
 * ナイフツールで使用する定数定義
 */

const KNIFE_CONSTANTS={
// 分割方向の定数
DIRECTION: {
HORIZONTAL: 1,
VERTICAL: 2,
ERROR:-1
},

// アスペクト比の制限（これを超えると不自然な形状とみなす）
ASPECT_RATIO: {
MIN: 0.27,
MAX: 3.45
},

// ナイフ補助角度（水平/垂直へのスナップ角度）
KNIFE_ASSIST_ANGLE: 3,

// 分割線関連
SPLIT_LINE: {
POINT_DISTANCE: 50,// 分割線の点計算距離
EXTEND_LENGTH: 10,// 延長ピクセル数
TOLERANCE: 5             // 分割点の許容誤差
},

// 幾何計算
GEOMETRY: {
THRESHOLD_RATIO: 0.1,// 境界ボックスの閾値比率
MIN_LENGTH: 0.001,// 最小線分長
SEGMENT_TOLERANCE: 0.1   // 線分上の点判定許容値
},

// アニメーション
ANIMATION: {
DASH_OFFSET_MAX: 18,
DASH_SPEED: 0.5
},

// 線のスタイル
LINE_STYLE: {
STROKE_COLOR: '#ff6b6b',
STROKE_WIDTH: 3,
DASH_ARRAY: [12,6],
SHADOW: {
color: 'rgba(255,107,107,0.6)',
blur: 8,
offsetX: 0,
offsetY: 0
}
}
};
