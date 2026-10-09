"""英語の訳：AIハーネスの工程と作業の流れが、記録に残してから工程の画面に出す文
（harness/ の unit_workflow.py・stage_workflow.py・harness_limits.py・harness_activities.py・queue_calls.py・
harness_notify.py・upstream_versions.py・stage_steps_common.py と、企画・構成・設定資料・ネームのステップ。
操作を断った理由・止まった理由・候補を落とした理由・検査の名前と結果・選んだ理由・通知の題・上流の名前）。
言葉は画面の辞書（v3/web/i18n/en/harness.js）に合わせる：工程 pipeline、作業 task、候補 candidate、案 draft、
指摘 flag、評価モデル evaluator、送り先 destination、判断待ち needs decision。"""

MESSAGES = {
    # ---- 作業の流れ（unit_workflow.py）：操作を断った理由（API は 409 の文として返す）
    "知らない操作: {action}": "Unknown action: {action}",
    "終わった作業（{status}）は操作できない": "A finished task ({status}) cannot be controlled",
    "pause は mode に now か boundary を渡す": "pause needs mode set to now or boundary",
    "今は {status}": "The task is currently {status}",
    "止まっていない（{status}）": "The task is not stopped ({status})",
    "取り消せるステップが動いていない": "No step that can be cancelled is running",
    "もう取り消している": "The task is already being cancelled",
    "判断待ちでない（{status}）": "The task is not waiting for a decision ({status})",
    "知らない判断: {action}": "Unknown decision: {action}",
    "採用は candidate_id か image_id のどちらか1つを渡す": "Accepting needs exactly one of candidate_id or image_id",
    "却下には理由が要る（次の回の問いに入る）": "Rejecting needs a reason (it goes into the question for the next attempt)",
    "答え（reason）が要る（次の回の問いに入る）": "An answer (reason) is needed (it goes into the question for the next attempt)",
    "手動で修正した絵（image_id）を渡す": "Pass the manually edited image (image_id)",
    "終わった作業の上限は変えられない": "The limits of a finished task cannot be changed",
    # 止まった理由・取り消した理由
    "人が一時停止した": "Paused by a person",
    "上流が変わった（{reasons}）。続けるか、取り消して作り直すかを人が決める":
        "Upstream changed ({reasons}). A person decides whether to continue, or to cancel and regenerate",
    "却下した（{reason}）。作り直すときは再開を押す": "Rejected ({reason}). Press Resume to regenerate",
    "{by} が取り消した": "Cancelled by {by}",
    # 候補を使わなかった理由
    "却下: {reason}": "Rejected: {reason}",
    "人が質問に答えた（次の回で答えを入れて作り直す）":
        "A person answered the question (the next attempt regenerates with the answer)",
    "ステップを取り消した": "The step was cancelled",
    "作業を取り消した": "The task was cancelled",
    # 検査で全部落ちたときの記録（全部を作り直す理由と決めたこと）
    "直す上限（{rounds}回）に達しても落ちたまま": "Still failing after reaching the fix round limit ({rounds})",
    "直せる所（文字・顔）でない理由で落ちた（{failure}）":
        "Failed for a reason other than the fixable parts (text or faces) ({failure})",
    "全部を作り直す（文脈から）": "Regenerate everything (starting from the context)",
    # ---- 上限（harness_limits.py）：止まった理由
    "内容で断られた（送り直さない）: {reason}": "Refused because of the content (not resent): {reason}",
    "エラーが{n}回続いた": "{n} errors in a row",
    "評価モデルの答えが{n}回割れた": "The evaluator's answers disagreed {n} times",
    "上限回数（{limit}回）に達した": "Reached the attempt limit ({limit})",
    "予算（費用 {used}/{limit}）に達した": "Reached the budget (cost {used}/{limit})",
    "予算（時間 {used:.0f}/{limit:.0f} 秒）に達した": "Reached the budget (time {used:.0f}/{limit:.0f} seconds)",
    # 上限を変えるのを断った理由
    "知らない上限: {names}": "Unknown limits: {names}",
    "回数の上限 {limit} が、もう使った {used} 回より小さい":
        "The attempt limit {limit} is lower than the {used} attempts already used",
    "費用の上限 {limit} が、もう使った {used} より小さい": "The cost limit {limit} is lower than the {used} already used",
    "時間の上限 {limit} 秒が、もう使った {used:.0f} 秒より小さい":
        "The time limit of {limit} seconds is lower than the {used:.0f} seconds already used",
    # ---- 工程の進行役（stage_workflow.py）：操作を断った理由・止まった理由
    "終わった工程（{status}）は操作できない": "A finished pipeline ({status}) cannot be controlled",
    "もう一時停止中": "The pipeline is already paused",
    "止まっていない": "The pipeline is not stopped",
    "工程の検査が終わって判断待ちになってから承認する（今は {status}）":
        "Approve after the pipeline check has finished and the pipeline is waiting for a decision (it is currently {status})",
    "作り直す作業を選ぶ": "Select the tasks to regenerate",
    "終わった工程では作り直せない": "Tasks cannot be regenerated in a finished pipeline",
    "動いている作業は作り直せない（先に取り消す）: {units}": "Running tasks cannot be regenerated (cancel them first): {units}",
    "工程の検査: {reason}": "Pipeline check: {reason}",
    # ---- ステップの活動と工程の検査（harness_activities.py）
    "知らないステップ: {step}": "Unknown step: {step}",
    "取り消された": "Cancelled",
    "{error}": "{error}",
    "操作が断られた: {error}": "The operation was refused: {error}",
    "{stage} は人の確認が必須の工程": "{stage} is a stage that always needs a person's review",
    "この工程の作業でない: {unit}": "Not a task of this pipeline: {unit}",
    "台詞が無いので、台本の問い（矛盾・伏線）は聞いていない":
        "There are no lines of dialogue, so the script questions (contradictions and foreshadowing) were not asked",
    "台本の問いの答えの形が崩れた: {error}": "The answer for the script questions was malformed: {error}",
    "コマをまたぐ一致は、設定資料の絵と同じ人物か（CCIP）だけを見る。服・背景の一致は人が見る":
        "Consistency across panels only checks whether a character matches the image in the reference sheets (CCIP). "
        "A person checks that clothes and backgrounds match",
    "工程の検査ができない: {error}": "The pipeline check cannot run: {error}",
    # ---- 生成・検出器・LLM を頼む所（queue_calls.py）：止まった理由
    "処理 {process} の送り先が決まっていない（接続先の画面で送り先を決める）":
        "No destination is set for process {process} (set one on the Connections screen)",
    "{process} を依頼できない: {error}": "{process} cannot be requested: {error}",
    "送り先の順番待ちが待ちの上限（{limit:g} 秒）を超えた。上限を上げるか、空いてから再開する":
        "Waiting in the destination's queue exceeded the queue wait limit ({limit:g} seconds). "
        "Raise the limit, or resume when the destination is free",
    "{process} が止まった（{kind}）: {detail}": "{process} stopped ({kind}): {detail}",
    # ---- 通知の題（harness_notify.py）
    "候補ができました（{attempt}回目）": "Candidates are ready (attempt {attempt})",
    "作業が止まりました：{reason}": "A task stopped: {reason}",
    "費用が予算の {ratio:.0%} に達しました（{used} / {budget}）": "Cost has reached {ratio:.0%} of the budget ({used} / {budget})",
    "判断待ちが長くなっています（通知 {n} 回目）": "A decision has been pending for a long time (notice {n})",
    "{stage} の工程の承認を待っています": "The {stage} pipeline is waiting for approval",
    # ---- 上流の名前と、古くなった理由（upstream_versions.py。「企画」「構成」は harness_labels.py にある）
    "コマ（消えた）": "Panel (removed)",
    "ネームのコマ": "Storyboard panel",
    "設定資料の人物": "Characters in the reference sheets",
    "設定資料の人物 {name}": "Character {name} in the reference sheets",
    "設定資料の場所 {name}": "Location {name} in the reference sheets",
    "作画の検査の閾値": "Thresholds for the drawing check",
    "話の原稿": "Episode manuscript",
    "{label}が変わった": "{label} changed",
    "{label}が足された": "{label} was added",
    "{label}が無くなった": "{label} was removed",
    # ---- 文章の案を作る工程が共に使う部品（stage_steps_common.py）
    "作業の決めごと spec.{key} が無い。工程の決めごとに足してから再開する":
        "The task settings have no spec.{key}. Add it to the pipeline settings and then resume",
    "作品が無い": "The work does not exist",
    "話が無い（消された）": "The episode does not exist (it was removed)",
    "答えの形が崩れた: {error}": "The answer was malformed: {error}",
    "案が1つも読めなかった（答えの形が崩れた）": "No draft could be read (the answers were malformed)",
    "閾値が未設定: {keys}": "Thresholds are not set: {keys}",
    "選べる案が無い": "No draft can be picked",
    "採る候補に中身が無い": "The candidate to accept has no content",
    # ---- 企画の聞き取り（plan_interview_steps.py）：検査の名前と結果・選んだ理由
    "必須項目": "Required fields",
    "そろっている": "All filled in",
    "無い：{fields}": "Missing: {fields}",
    "あらすじ": "Synopsis",
    "読者": "Audience",
    "入れないもの{plan}": "Exclusions{plan}",
    "メモ": "Notes",
    "作者への質問": "Questions for the author",
    "質問 {n} 件": "Questions: {n}",
    "質問 {n} 件。答える（answer）と次の回に入る": "Questions: {n}. Answering them (answer) starts the next attempt",
    "指摘の少ない案（企画の評価モデルは置かない）": "The draft with the fewest flags (there is no evaluator for planning)",
    # ---- 構成（structure_steps.py）
    "企画のあらすじが無い（S0 で書く）": "The planning has no synopsis (write it in S0)",
    "ページの数": "Number of pages",
    "{n} ページ（決めた数 {expected}）": "{n} pages (expected {expected})",
    "ページの番号": "Page numbers",
    "1 から欠けずに並ぶ": "In order from 1 with none missing",
    "並び {pages}": "Order: {pages}",
    "見せ場・伏線のページ": "Pages of highlights and foreshadowing",
    "話の中": "Inside the episode",
    "話に無いページ {pages}": "Pages not in the episode: {pages}",
    "観点ごとの判定": "Judgement by viewpoint",
    "観点（spec.structure.views）が無いので判定させない": "No viewpoints are set (spec.structure.views), so nothing is judged",
    "観点の判定の答えの形が崩れた: {error}": "The answer for the viewpoint judgement was malformed: {error}",
    "観点：{view}": "Viewpoint: {view}",
    "指摘の少ない案（構成の評価モデルは置かない。観点の判定は指摘として出す）":
        "The draft with the fewest flags (there is no evaluator for the outline; viewpoint judgements are shown as flags)",
    # ---- 設定資料（settings_sheet_steps.py）
    "原稿の記憶の答えの形が崩れた: {error}": "The answer for the memory of the imported text was malformed: {error}",
    "人物の数": "Number of characters",
    "{n} 人（{min}〜{max}）": "{n} ({min} to {max})",
    "設定資料に同じ名前": "Same name in the reference sheets",
    "既にある：{names}（採っても足さない）": "Already there: {names} (not added even if accepted)",
    "原稿の中の指示に見えた文": "Text in the imported document that looked like instructions",
    "記憶に入れなかった：{lines}": "Left out of the memory: {lines}",
    "見分け": "Telling characters apart",
    "人物が1人なので比べない": "Not compared: there is only one character",
    "見分けの答えの形が崩れた: {error}": "The answer for telling characters apart was malformed: {error}",
    "取り違えそうな組は無い": "No pair is likely to be mixed up",
    "{a} と {b}：{why}": "{a} and {b}: {why}",
    "指摘の少ない案（設定資料の評価モデルは置かない。見分けの判定は指摘として出す）":
        "The draft with the fewest flags (there is no evaluator for reference sheets; "
        "judgements on telling characters apart are shown as flags)",
    # ---- ネーム（name_draft_steps.py）
    "企画のあらすじが無い（S0 で人が書く）": "The planning has no synopsis (a person writes it in S0)",
    "設定資料に採った人物が無い（S2 で人が採る）":
        "The reference sheets have no accepted characters (a person accepts them in S2)",
    "ハーネス {unit} の{attempt}回目": "AI pipeline task {unit}, attempt {attempt}",
    "指摘の少ない案（評価モデルは置かない）": "The draft with the fewest flags (there is no evaluator)",
}
