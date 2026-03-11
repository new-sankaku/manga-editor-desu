# サードパーティ ライセンス一覧

本プロジェクトは **GNU General Public License v3 (GPLv3)** のもとで公開されています。

以下は、本プロジェクトで使用しているサードパーティライブラリおよびフォントのライセンス情報です。

---

## 同梱ライブラリ（`third/` ディレクトリ）

| ライブラリ | バージョン | ライセンス | URL |
|---|---|---|---|
| Fabric.js | 5.3.0 | MIT | <http://fabricjs.com/> |
| Pixi.js | 8.3.4 | MIT | <https://pixijs.com/> |
| Advanced Blend Modes (PixiJS) | 8.3.4 | MIT | <https://pixijs.com/> |
| interact.js | - | MIT | <https://interactjs.io/> |
| glfx.js | - | MIT | <https://evanw.github.io/glfx.js/> |
| i18next | - | MIT | <https://www.i18next.com/> |
| Intro.js | 7.2.0 | AGPL v3 | <https://introjs.com/> |
| JSTS | - | EDL v1.0 / EPL v1.0 (デュアル) | <https://github.com/bjornharrtell/jsts> |
| JSZip | 3.7.1 | MIT or GPLv3 (デュアル) | <https://stuk.github.io/jszip/> |
| Crypto-JS | - | MIT | <https://github.com/brix/crypto-js> |
| Lodash | 4.17.21 | MIT | <https://lodash.com/> |
| Hotkeys.js | 3.13.7 | MIT | <https://jaywcjlove.github.io/hotkeys-js> |
| Tippy.js | - | MIT | <https://atomiks.github.io/tippyjs/> |
| Popper.js | 2.11.8 | MIT | <https://popper.js.org/> |
| Bootstrap | 5.2.3 | MIT | <https://getbootstrap.com/> |
| Font Awesome | 6.0.0-beta3 | アイコン: CC BY 4.0 / フォント: SIL OFL 1.1 / コード: MIT | <https://fontawesome.com/> |
| LocalForage | 1.10.0 | Apache License 2.0 | <https://localforage.github.io/localForage> |
| Browser Image Compression | 2.0.2 | MIT | <https://github.com/Donaldcwl/browser-image-compression> |
| LZ4.js | - | MIT | <https://github.com/nicox/lz4js> |
| Google Analytics | - | Google 利用規約 | <https://analytics.google.com/> |

## CDN 読み込みライブラリ

| ライブラリ | バージョン | ライセンス | URL |
|---|---|---|---|
| Three.js | r128 | MIT | <https://threejs.org/> |
| Tagify | 4.31.3 | MIT | <https://github.com/yairEO/tagify> |
| Stacktrace.js | - | MIT | <https://www.stacktracejs.com/> |
| Masonry | 4.2.2 | MIT | <https://masonry.desandro.com/> |
| Chart.js | - | MIT | <https://www.chartjs.org/> |
| WordCloud2 | - | MIT | <https://github.com/timdream/wordcloud2.js> |
| JSColor | 2.4.5 | GPLv3 | <https://jscolor.com/> |
| Flag Icons CSS | 4.1.3 | MIT | <https://github.com/lipis/flag-icons> |

## 同梱フォント（`font/` ディレクトリ）

### SIL Open Font License 1.1

| フォント | URL |
|---|---|
| Bangers | <https://fonts.google.com/specimen/Bangers> |
| DotGothic16 | <https://fonts.google.com/specimen/DotGothic16> |
| Kalam | <https://fonts.google.com/specimen/Kalam> |
| Klee One | <https://fonts.google.com/specimen/Klee+One> |
| Rampart One | <https://fonts.google.com/specimen/Rampart+One> |
| Stick | <https://fonts.google.com/specimen/Stick> |
| Train One | <https://fonts.google.com/specimen/Train+One> |
| Chalk-JP | <https://font.cutegirl.jp/chalk-font-free.html> |
| どきどきファンタジア | <https://www.flopdesign.com/> (Zen Maru Gothic 派生) |

### 851フォントシリーズ（独自ライセンス）

商用・非商用利用可。改変・再配布可。フォント単体販売は禁止。

| フォント | URL |
|---|---|
| 851チカラヅヨク (カナA) | <https://pm85122.onamae.jp/851ch-dz.html> |
| 851チカラヅヨク (カナB) | <https://pm85122.onamae.jp/851ch-dz.html> |
| 851チカラヨワク | <https://pm85122.onamae.jp/851ch-yw.html> |
| 851テガキカクット | <https://pm85122.onamae.jp/851H_kktt.html> |
| 851MkPOP | <https://pm85122.onamae.jp/851mkpop.html> |

利用規約: <https://pm85122.onamae.jp/851fontTerm.html>

### おひさまフォント（独自ライセンス・フリーウェア）

- 商用・非商用利用可
- **改変不可**
- **再配布には作者への事前連絡が必要**
- フォント単体販売禁止
- 著作権: ふい (hui)
- URL: <http://hp.vector.co.jp/authors/VA039499/>

## Google Fonts（CDN 読み込み）

全て **SIL Open Font License 1.1** で提供。

Klee One / M PLUS 1p / Noto Sans JP / Zen Maru Gothic / Noto Sans SC / ZCOOL KuaiLe / ZCOOL XiaoWei / Do Hyeon / East Sea Dokdo / IBM Plex Sans KR / Noto Sans KR / Architects Daughter / Bangers / Bungee Shade / Comic Neue / Creepster / Permanent Marker / Rubik Mono One / DotGothic16

## 開発用依存（package.json）

| ライブラリ | バージョン | ライセンス |
|---|---|---|
| ESLint | ^8.57.0 | MIT |
| @eslint/js | ^8.57.0 | MIT |

---

## 注意が必要なライブラリ

| ライブラリ | ライセンス | 注意事項 |
|---|---|---|
| **Intro.js** | AGPL v3 | 商用利用時は[商用ライセンス](https://introjs.com/checkout)の購入が必要。AGPLはソース公開義務あり |
| **JSColor** | GPLv3 | 商用利用時は[商用ライセンス](https://jscolor.com/download/)の購入が必要 |
| **Font Awesome** | CC BY 4.0 (アイコン部分) | アイコン使用時に帰属表示が必要 |
| **JSTS** | EDL v1.0 / EPL v1.0 | Eclipse系ライセンス。特許条項あり |
| **おひさまフォント** | 独自 (フリーウェア) | 再配布には作者への事前連絡が必要。改変不可 |
