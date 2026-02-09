# 014: index.htmlの分割

## 規模: L (大)

## 概要
2,246行のモノリシックな`index.html`をコンポーネント単位に分割し、
保守性と開発効率を向上させる。

## 該当箇所
- `index.html`

## 現状の問題
- ナビバー、サイドバー、モーダル、設定パネルなど全UIが1ファイルに集中
- ファイル内の検索と編集が困難
- 複数人での並行開発時にコンフリクトが頻発しやすい
- セクション間の依存関係が不明確

## 修正内容
### HTMLテンプレートの分割
```
html/
  components/
    navbar.html
    sidebar-panel.html
    sidebar-speech-bubble.html
    sidebar-text.html
    sidebar-effect.html
    sidebar-tone.html
    sidebar-pen.html
    sidebar-rough.html
    controls.html
    layer-panel.html
    bottom-bar.html
    modals/
      shortcut-modal.html
      settings-modal.html
      ai-settings-modal.html
```

### 読み込み方式
- ビルド時に`index.html`を生成する方式
- または`fetch`+`insertAdjacentHTML`で動的読み込み

### 段階的移行
1. まずモーダル類（最も独立性が高い）を分離
2. サイドバーの各タブを分離
3. ナビバーとコントロールパネルを分離
4. ブートスクリーンとスクリプトタグの整理

## 影響範囲
- UI全般
- i18nextの翻訳キー適用タイミング
- イベントリスナーのバインドタイミング
