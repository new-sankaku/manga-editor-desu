## 基本ルール
- 常に敬語を使う
- サブエージェントはOpus/Sonnet使用（Haiku禁止）
- `file://`プロトコルで動作必須
- UI変更は既存表示・既存文言と調和させる
- fallback禁止（ユーザー誤認防止）
- フォールバック目的のハードコーディングは基本は禁止
- UIはフレキシブル対応を行い固定幅は使わない
- 機能修正時は関連する`llm_doc/`も更新する
- ユーザーから修正ポイントの確認を求められた場合は見落としの可能性が高い。指摘内容を`llm_doc/review-checklist.md`に反映し回数をインクリメントする
- 検証していない仕組みを設計の根拠にしない。「〜だから効く」と書く前に確認する。確認できないなら「未検証」と明記する
- LLMプロンプトに具体的なタグ・単語を例示しない。全出力に入る（→`llm_doc/prompt-composition.md`）
- バグの温床になるコードは避けてください。全てのコードを修正してプロパティを変更するのではなく、Eventトリガーの1か所に修正を入れるなど修正漏れ、テスト対象の拡大を防いでください。

## ドキュメント
- `llm_doc/project-structure.md` - ファイルの場所が分からないとき。ディレクトリ構成、グローバル変数、script読み込み順
- `llm_doc/ui-patterns.md` - UI部品の追加・修正時。EventDelegator、Toast、モーダル、CSS変数、i18n、永続化の使い方
- `llm_doc/ai-system.md` - AI画像生成の修正時。プロバイダ構成、TaskQueue、ロール割り当て、ComfyUIワークフロー
- `llm_doc/manga-page-guideline.md` - 漫画のページを作る指針。LLMプロンプトはここから作る（これが正）
- `llm_doc/prompt-composition.md` - コマのプロンプトを作る処理を触るとき。漫画の構図と画像生成AIの差、効くタグと効かないタグ、見切れ対策
- `llm_doc/layer-structure.md` - レイヤーやキャンバスオブジェクトの操作時。GUID連携、リンク機構、AIタスク進捗管理
- `llm_doc/coding-rules.md` - コードを書く前に確認。命名規則、ログ出力、npm run format の挙動
- `llm_doc/history-and-data.md` - Undo/Redo周りや画像保存の修正時。履歴スタック操作、data:URL制約
- `llm_doc/translation.md` - UI文言を追加するとき。i18nextのキー書式と8言語の記載例
- `llm_doc/chrome.md` - Chrome拡張連携の修正時。通信制約と接続手順
- `llm_doc/review-checklist.md` - コード修正後の見落とし防止。頻出問題と確認回数


## 除外フォルダ
検索・読み込み対象外:
`json_js`, `test`, `third`, `01_build`, `02_images_svg`, `03_images`, `99_doc`, `font`
