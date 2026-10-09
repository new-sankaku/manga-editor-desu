"""英語の訳：操作（operations/ の ai_involvement.py から operation_submit_and_undo.py まで）。"""

MESSAGES = {
    # ai_involvement.py
    "企画（S0）": "Planning (S0)",
    "構成（S1）": "Outline (S1)",
    "設定資料（S2）": "Reference sheets (S2)",
    "ネームの中身（S3。場面・人物・セリフ）": "Storyboard content (S3: scenes, characters, dialogue)",
    "コマ割り（S3。枠・読む順・段の割り）": "Panel layout (S3: frames, reading order, tier split)",
    "作画（S4。コマの絵・レイヤー・絵の置き方）": "Drawing (S4: panel art, layers, art placement)",
    "仕上げ（S5。文字の置き場・書体と飾り・しっぽ・フキダシの形・トーン・図形・絵の仕上げ）":
        "Finishing (S5: text placement, fonts and decoration, balloon tails, balloon shapes, screentones, shapes, "
        "art finishing)",
    "翻訳（元の言語のほかの言語の文字）": "Translation (text in languages other than the original)",
    "知らない作業: {task}": "Unknown task: {task}",
    "作品が選んだ": "chosen for this work",
    "設計の既定": "design default",
    "{task} のAIの関与は {mode}（{how}）。AIの {action} は許されていない":
        "AI involvement for {task} is {mode} ({how}); the AI is not allowed to {action}",
    # annotation_operations.py
    "範囲は3つ以上の点で囲む": "An area needs at least 3 points",
    "コマとページが合わない": "The panel does not belong to the page",
    "変える項目がない": "Nothing to change",
    "{field} は空にできない": "{field} cannot be empty",
    "すでに残してある": "Already recorded",
    # book_structure_operations.py
    "同じページが2回ある": "The same page appears twice",
    "話の削除していないページを全部、1回ずつ渡す": "Pass every non-deleted page of the episode exactly once",
    "番号の数がページの数と違う": "The number of page numbers differs from the number of pages",
    "番号の順が、渡したページの順と合わない": "The order of the numbers does not match the order of the pages passed",
    "見開きの組が崩れる。先に見開きを解く: {reasons}": "This would break a spread; split the spread first: {reasons}",
    "見開きの2ページは同じ話にある": "Both pages of a spread must be in the same episode",
    "見開きにできない: {reasons}": "Cannot make a spread: {reasons}",
    "解いた見開きは変えられない": "A split spread cannot be changed",
    "adjustments は空にできない（外すときは []）": "adjustments cannot be empty (use [] to remove them)",
    "{head}; {tail}": "{head}; {tail}",
    # current_app_import_operations.py
    "作品のページの寸法（page_spec）を先に決める。コマと文字の位置を mm に直すのに使う":
        "Set the work's page size (page_spec) first; it is needed to convert panel and text positions to mm",
    "持ち込んだ絵（image_origin=imported）には利用の条件（usage_terms）が要る":
        "Imported art (image_origin=imported) needs usage terms (usage_terms)",
    # episode_plan_operations.py
    "cast_entry_ids は重ならない id の並び（無くすときは []）": "cast_entry_ids must be a list of unique IDs (use [] to clear)",
    "設定資料 {id} は削除されているか、採っていない案":
        "Reference sheet {id} is deleted or is a proposal that has not been accepted",
    "話の生成の中身が正しくない: {reason}": "The episode's generation settings are invalid: {reason}",
    "前の話から引き継ぐのは人だけ": "Only a person can carry over from the previous episode",
    "引き継ぐ前の話が無い（最初の話か、前の話が削除されている）":
        "There is no previous episode to carry over from (this is the first episode, or the previous one is deleted)",
    "同じ話からは引き継げない": "Cannot carry over from the same episode",
    "前の話に構成（出る人物・話の生成の中身）が無い": "The previous episode has no outline (cast and generation settings)",
    "削除した伏線は set_removed で戻してから変える": "Restore the deleted foreshadowing with set_removed before changing it",
    # held_change_operations.py
    "判断待ちを決めるのは人だけ": "Only a person can resolve an item that needs a decision",
    "field_change は accept か reject で決める": "A field_change is resolved with accept or reject",
    "決めていない判断待ちは戻せない": "An unresolved item cannot be reopened",
    "判断待ちは {status}。決められるのは open だけ": "This item is {status}; only open items can be resolved",
    "{kind} で選べる手は {choices}": "The choices for {kind} are {choices}",
    "どのコマに置くか（params.panel_id）が要る": "The target panel (params.panel_id) is required",
    "このレイヤー（紙・グループなど）は書き出しで作った物で、削除する物が無い。keep で閉じる":
        "This layer (paper, group, etc.) was created by the export, so there is nothing to delete; close it with keep",
    # human_hand_guard.py
    "{table}:{id} は人が「動かさない」にしている。先に人が外す":
        "{table}:{id} is locked by a person; a person must unlock it first",
    "手動編集の印を変えられるのは人だけ": "Only a person can change manual-edit marks",
    # image_candidate_operations.py
    "却下した絵は採れない（先に却下を外す）": "A rejected image cannot be accepted (undo the rejection first)",
    "レイヤー {layer} はコマ {panel} の物ではない": "Layer {layer} does not belong to panel {panel}",
    "もうこの絵になっている": "This image is already in use here",
    "ページに付いていない絵は、候補として却下できない":
        "An image that is not attached to a page cannot be rejected as a candidate",
    "すでにその状態": "Already in that state",
    "コマ {panel} で使っている絵は却下できない": "An image used in panel {panel} cannot be rejected",
    # image_file_operations.py
    "{actor} は origin={origin} の絵を登録できない": "{actor} cannot register an image with origin={origin}",
    "生成した絵には依頼（job_id）が要る": "A generated image needs its job (job_id)",
    "持ち込んだ絵には元（source_note）と利用の条件（usage_terms）を書く":
        "Imported art needs a source (source_note) and usage terms (usage_terms)",
    "手動で修正した絵には元のバージョン（based_on_image_id）が要る":
        "A manually edited image needs its base version (based_on_image_id)",
    "入口（image_intake.py）を通っていない絵は登録できない":
        "An image that has not passed intake (image_intake.py) cannot be registered",
    "入口の判定で止めた絵は登録できない": "An image blocked at intake cannot be registered",
    "範囲が絵（{width}x{height}）の外に出ている": "The area extends outside the image ({width}x{height})",
    "手動編集の範囲を変えられるのは人だけ": "Only a person can change manually edited areas",
    # image_placement_carry.py
    "今の切り抜きが新しいバージョンの外にある。置き場を引き継げない":
        "The current crop lies outside the new version, so the placement cannot be carried over",
    "コマに枠も置き場も無いので、絵をどこに置くか決められない":
        "The panel has neither a frame nor a placement, so there is no way to decide where to put the image",
    # material_and_plan_operations.py
    "設定資料の値が正しくない: {reason}": "The reference sheet values are invalid: {reason}",
    "exclusions は空にできない（無くすときは []）": "exclusions cannot be empty (use [] to remove them)",
    "案を採るのは人だけ": "Only a person can accept a proposal",
    "構成の形が合わない: {loc} {msg}": "The outline has the wrong shape: {loc} {msg}",
    # name_draft_conversion.py
    "page:{id} は見開きかどうか（layout.spread）がまだ決まっていない":
        "Whether page:{id} is a spread (layout.spread) is not set yet",
    "作品の page_spec と first_page_is_left がまだ決まっていない": "The work's page_spec and first_page_is_left are not set yet",
    # name_proposal_operations.py
    "{actor} は made_by={made_by} の案を出せない": "{actor} cannot submit a draft with made_by={made_by}",
    "元の文書を持てるのは取り込んだ案だけ": "Only an imported draft can have a source document",
    "同じページ番号が2つある": "The same page number appears twice",
    "採用した案は、採用を取り消してから変える": "Undo the acceptance before changing an accepted draft",
    "案は {status}。未決の案だけ採用できる": "This draft is {status}; only pending drafts can be accepted",
    "採用していない案は戻せない": "A draft that has not been accepted cannot be reverted",
    # operation_submit_and_undo.py
    "{target_kind}:{target_id} は {holder_kind}:{holder_id} がロック中（{reason}）":
        "{target_kind}:{target_id} is locked by {holder_kind}:{holder_id} ({reason})",
    "{op} はAIが出せない操作": "{op} cannot be submitted by the AI",
    "{user} に {object} の {relation} が無い": "{user} does not have {relation} on {object}",
    "すでに取り消している": "Already undone",
    "この出来事には変えた項目の記録が無い（記録を始める前の出来事）。後の変更とぶつかるかを確かめられないので取り消さない":
        "This event has no record of changed fields (it predates the recording), so it is not undone because "
        "conflicts with later changes cannot be checked",
    "{op} は権限の組を書くので、ほかの操作とまとめて確定できない":
        "{op} writes permission tuples, so it cannot be committed together with other operations",
    "{op} は取り消せない": "{op} cannot be undone",
    "{seq}番 {op}（{actor_kind}:{actor_id}）": "#{seq} {op} ({actor_kind}:{actor_id})",
    "{head}・{tail}": "{head}, {tail}",
    "記録の無い変更": "an unrecorded change",
    "{table}:{id} の {field} を後で {by} が変えている": "{field} of {table}:{id} was later changed by {by}",
    "{head}／{tail}": "{head} / {tail}",
    "取り消すと後の変更を上書きするので取り消さない。{conflicts}":
        "Not undone because it would overwrite later changes. {conflicts}",
}
