// ストーリー1本から「登場人物とロケーションの設定 → 各ページの流れ → 各コマのプロンプト」を作る。
// コマの並べ替え・レイアウト要約・コマ応答のパース・役割の検証はllm-storyboard-service.jsの
// 関数をそのまま使い、実装を二重に持たない

// ユーザーの入力はページ数に対して短すぎるか長すぎる。短ければ各ページが空になり、
// 長ければ1ページに詰め込みすぎる。配分の前に両方向へ合わせる。
// 文面は llm_doc/manga-page-guideline.md の9・12・13章がそのまま元
const LLM_STORY_FIT_SYSTEM=[
'このストーリーを、指定されたページ数に収まる長さへ書き直してください。',
'足す・縮める・削るのどれを使っても構いません。',
'',
'──────────────────────────────',
'',
'■ 動かさないもの',
'',
'誰が出てくるか、何が起きるか、どう終わるか。この3つはユーザーが決めたことです。',
'長さを合わせるためなら、それ以外は足しても縮めても削っても構いません。',
'',
'■ 短いとき、何を足すか',
'',
'ストーリーが書いていないことのうち、絵にできるものが候補になります。',
'・人物どうしがどういう関係か',
'・どこで起きているか',
'・その人物が何を欲しがっていて、なぜ欲しいか',
'・その前に立ちはだかっているもの',
'・見せ場（この話で一番見せたい場面）',
'・その後どうなったか',
'',
'■ 長いとき、何から削るか',
'',
'よく使われる順:',
'・説明だけの場面（移動、時間経過、回想）',
'・脇役と、その脇役のためにある場面',
'・同じことを2回見せている場面',
'・見せ場から遠い場面',
'見せ場と結末を先に削ると、話の中心が無くなります。',
'',
// 指針9章。起承転結を並び順の型として渡すと4分割するだけになるので、型は複数出す
'■ 構成の型',
'',
'よく使われる型です。どれを使っても、混ぜても構いません。',
'・起承転結 … 人物と日常を見せる／状況が動く／予想された結末が外れる／その後を見せる',
'・三幕 … 状況を置く／障害と向き合う／決着する',
'・見せ場から始める … 一番強い場面を最初に置き、その後で経緯へ戻る',
'・途中から始める … 説明を省いて、既に何かが起きている状態から入る',
'・その後を書かない … 予想が外れたところで終え、残りを読者に委ねる',
'・二段構え … 障害を1つ越えさせ、その後ろにもっと大きいものを置く',
'・二度外す … 予想された結末を外し、そこからさらに外す',
'',
'型に関わらず、次の3つがどこかに在ると読者が付いてきやすい:',
'・誰の話かが分かる',
'・その人物にとっての普通が壊れる',
'・人物と読者が予想した結末が外れる',
'3つ目が無い話は、最初から最後まで同じ調子に見えやすい。',
'',
'■ 1ページ目',
'',
'読者はここで読み続けるかを決めます。よく使われる手:',
'・既に何かが起きている途中から入る',
'・何かを見せずに隠す',
'・後で起きる強い場面を先に置く',
'場所の説明や人物の紹介から始めると、読み進む理由が出るまで遅れます。',
'',
'■ 起伏',
'',
'強い場面を続けて置くと、どちらも普通に見えやすい。落差の付け方:',
'・見せ場の直前を静かな場面にする',
'・直前を短く畳んで、見せ場に紙面を空ける',
'・別の場所の場面を挟む',
'続けて置く構成も選べますが、2つ目を1つ目と違う種類の強さにしないと、読者は同じ場面として読みます。',
'',
'■ 場面の数',
'',
'1場面はだいたい1〜3ページです。ページ数に入る場面数を先に見積もると、後が楽になります。',
'・場面が多すぎると1場面が1ページ未満になり、描く中身が入りません',
'・場面が少なすぎると1場面が4ページ以上に伸び、同じ絵が続きます',
'',
// 指針12章。設定を細かく作るのではなく、1つか2つを強く出す
'■ 人物の中身',
'',
'・欠けているものが1つあると、読者はその人物を見続けます',
'・欲しいものが1つあると、その人物が動く理由になります',
'・設定を10個平均に書くより、1つか2つを強く出したほうが伝わります',
'・その人物がしたことで見せると絵になります。性格を文で説明すると絵になりません',
'',
// 人数と場所の上限は物語の都合ではない。同一人物を保つ手段がタグの一致しかないため
'■ 人数と場所（絵の側の制約）',
'',
'絵は画像生成モデルが描きます。同じ顔・同じ場所を保つ手段はタグの一致だけなので、',
'人物が増えるほど、場所が増えるほど、コマ間で見た目がぶれます。',
'人物3〜4人、場所2〜3箇所に収まっていると安定します。長い話を削るときは、ここから減らすと効きます。',
'',
// 指針12章。AI生成は似た見た目を描き分けられない
'■ 人物の描き分け（絵の側の制約）',
'',
'見た目の近い人物を、画像生成モデルは描き分けられません。区別が付く要素:',
'・髪の長さ',
'・髪の色',
'・服の種類',
'・その人物だけが持っているもの',
'',
'■ 書き方',
'',
'・1場面につき1段落。どこで、誰がいて、何が起きるかを書く',
'・人物がしたことを書く。感じたことや、その人物について真であることは、後の工程で絵にできません',
'・名前は短くはっきり付ける。後の工程がその名前で人物を指します',
'',
'【必ず守ること】',
'',
'・ページやコマに分けない。それは後の工程',
'・元のストーリーと同じ言語で書く',
'',
'【出力】',
'・JSONのみ。形は {"story":"..."}'
].join('\n');

function parseStoryFit(raw) {
const parsed=parseLLMJsonBody(raw);
const story=parsed&&typeof parsed.story==='string' ? parsed.story.trim() : '';
if (!story) {
throw new Error(i18next.t('llmErrorEmptyResponse'));
}
return story;
}

// 戻り値: ページ数に合わせたストーリー本文
async function llmStoryFitToPages(story,pageCount) {
const target=requireLLMProvider(AI_ROLES.Text2Prompt);
const userPrompt=[
'ページ数: '+pageCount,
'',
'ストーリー:',
story
].join('\n');
const messages=target.provider.buildTextMessages(LLM_STORY_FIT_SYSTEM,userPrompt);
const raw=await target.queue.add(function () {
return target.provider.chat(messages,{temperature: 0.8,jsonObject: true});
});
return parseStoryFit(raw);
}

// キャラとロケーションを1回の呼び出しでまとめて作る。どちらも同じストーリーから引くため
const LLM_STORY_SHEET_SYSTEM=[
'このストーリーに繰り返し出てくる人物と場所を、Danbooru形式のタグで固定してください。',
'全コマがこれを使い回します。',
'',
'──────────────────────────────',
'',
'■ 何を作るか',
'',
'・繰り返し出てくるものだけ。1場面だけ通り過ぎる人物や、話の中で名前が出るだけの場所は要りません',
'・ストーリーに実際に出てくるものだけ。人物や場所を増やさない',
'',
'■ 人物のタグ',
'',
'見た目だけを書きます。年齢、髪、目、顔立ち、服、体型、装飾品、靴。',
'',
// 指針12章。似た見た目のキャラはAI生成で混ざる。ここで分けておく
'見た目の近い人物を、画像生成モデルは描き分けられません。手掛かりがこのタグしか無いためです。',
'区別が付く要素:',
'・髪の長さ',
'・髪の色',
'・服の種類',
'・その人物だけが持っているもの',
'ストーリーに書かれていなければ、ここで決めてください。',
'',
'■ 場所のタグ',
'',
'場所の種類、そこにあって名指しする価値のあるもの、時間帯、光。',
'',
'【必ず守ること】',
'',
'・人物のタグにポーズ・表情・アングル・背景を入れない。',
'  これらはコマごとに変わるが、キャラ表はその人物が出る全コマへ複写される',
'',
// 2人のコマでキャラ表を2つ並べると1girlが2回入り、solo寄りの偏りと噛み合って破綻する
'・人物のタグに人数タグ（"1girl" "1boy" "solo" "multiple girls" など）を入れない。',
'  2人が写るコマではキャラ表が2つ並ぶので人数タグが2つ入り、絵が壊れる。',
'  何人写るかはコマごとに決まる',
'',
'・場所のタグに人物・ポーズ・アングルを入れない',
'',
'・"name" はストーリー内での呼び方を、ストーリーの言語のまま書く',
'',
'【出力】',
'・JSONのみ。形は',
'  {"characters":[{"name":"...","tags":"tag, tag"}],"locations":[{"name":"...","tags":"tag, tag"}]}',
'・"tags" は小文字のDanbooru形式タグをカンマ区切り'
].join('\n');

// 起承転結を型として渡すと必ず4分割してくる。手順と判断の材料だけ渡す。
// 文面は llm_doc/manga-page-guideline.md の11・14章がそのまま元
const LLM_STORY_PAGEPLAN_SYSTEM=[
'このストーリーを渡されたページ数へ配り、各ページで何が起きるかを書いてください。',
'',
'進め方の目安です。話によって前後して構いません。',
'  1. 見せ場（この話で一番見せたい場面）を決める',
'  2. それを何ページ目に置くか決める',
'  3. そこへ至るまでを前のページへ配る',
'  4. その後を残りのページへ配る',
'',
'──────────────────────────────',
'',
'■ 見せ場をどこに置くか',
'',
'・後ろ寄り（全体の2/3〜3/4あたり）… 溜めてから出す',
'・1ページ目 … 先に見せてから、そこへ至った経緯へ戻る',
'・最終ページ … 外したところで終え、その後を書かない',
'',
'■ ページ数が場面の重さを決める',
'',
'・説明だけの場面（移動、時間経過）… 1ページ以下。削れるなら削る',
'・話が動く場面 … 1〜2ページ',
'・見せ場 … 2〜3ページ',
'',
'■ 1ページ目',
'',
'読者は理解するより先に、読み続けるかを決めます。よく使われる手:',
'・既に何かが起きている途中から入る',
'・何かを見せずに隠す',
'・大ゴマ1つ分になる絵を先に置いて、後で経緯へ戻る',
'場所の説明や人物の紹介から始めると、読み進む理由が出るまで遅れます。',
'',
'■ 最終ページ',
'',
'・1ページ目が投げた問いに答える',
'・答えるが、読者が予想したのとは違う形で答える',
'・答えずに終え、読者に委ねる',
'',
// 指針9章。溜めと落差。これが無いと全ページ同じ密度になる
'■ ページ間の起伏',
'',
'同じ調子のページが続くと、読者は読み流します。差の付け方:',
'・騒がしいページ ↔ 何も起きないページ',
'・人が多いページ ↔ 1人のページ',
'・喋るページ ↔ 黙るページ',
'・引きのページ ↔ 寄りのページ',
'見せ場の直前を静かなページにすると、落差が出ます。強いページを続けると、どちらも普通に見えやすい。',
'',
'■ コマ数と中身',
'',
'各ページのコマ数は既に決まっています。それに合う中身を割り当てると読みやすくなります。',
'・コマが多いページ … 出来事をいくつも運べる。1コマが小さいので、中身は単純なほうが読める',
'・コマが少ないページ … 1つの瞬間に紙面を使える',
'',
// 指針11章。読者は絵より先にセリフを読む
'■ セリフと絵の量',
'',
'読者は絵より先に文字を読みます。',
'セリフの多いページで引きの絵も見せようとすると、どちらも読まれません。',
'そのページが何を運ぶかを決めてください。',
'',
'【必ず守ること】',
'',
'・"location" と "time" は、同じ場所が続く間はまったく同じ文字列にする。',
'  場所が変わったときだけ変える。次の工程はこの2つの文字列の一致で場面転換を判定するので、',
'  言い回しを変えただけで別の場所として扱われる',
'',
'・コマ単位に分けない。それは次の工程',
'',
'【出力】',
'・JSONのみ。形は {"pages":[{"page":1,"summary":"...","location":"...","time":"..."}]}',
'・受け取ったページ番号すべてに1件ずつ。増やさない・落とさない',
'・"summary" は1〜3文。そのページに居る人物の名前を入れる',
'・"location" は短い名詞句、"time" は短い語',
'・"summary" "location" "time" はストーリーと同じ言語で書く'
].join('\n');

const LLM_STORY_PANEL_SYSTEM=buildPanelSystemPrompt(
[
// キャラ表をそのまま全部コピーさせると、顔だけのコマにも靴が入って勝手に引いた絵になる。
// フレームに入る範囲だけ使わせる（→ llm_doc/prompt-composition.md）
'・キャラ表からは、そのコマのフレームに入る範囲だけを取る。'
+'顔と髪は毎回入れる（同じ人物だと読者が分かるため）。服は体が入るときだけ、靴は足が入るときだけ。'
+'フレームの外にあるものを名指しすると、それを含めるために視点が引く',
'・同じ場所のコマには、ロケ表のタグを一字一句そのまま入れる'
]
);

function parseLLMJsonBody(raw) {
const body=raw.replace(/```[a-z]*\n?/gi, '').replace(/```/g,'').trim();
try {
return JSON.parse(body);
} catch (e) {
throw new Error(i18next.t('llmStoryboardErrorNotJson'));
}
}

// 画面には1行1件の素のテキストで見せる。編集してそのまま渡せるようにするため
function sheetEntriesToText(list) {
if (!Array.isArray(list)) {
return '';
}
const lines=[];
list.forEach(function (entry) {
if (!entry||typeof entry.tags!=='string') {
return;
}
const tags=normalizeTagOutput(entry.tags);
if (!tags) {
return;
}
const name=typeof entry.name==='string' ? entry.name.trim() : '';
lines.push(name ? name+': '+tags : tags);
});
return lines.join('\n');
}

function parseStorySheets(raw) {
const parsed=parseLLMJsonBody(raw);
if (!parsed) {
throw new Error(i18next.t('llmStoryboardErrorNotJson'));
}
const characters=sheetEntriesToText(parsed.characters);
const locations=sheetEntriesToText(parsed.locations);
if (!characters&&!locations) {
throw new Error(i18next.t('llmErrorEmptyResponse'));
}
return {characters: characters,locations: locations};
}

// 戻り値: {characters:string, locations:string}
async function llmStorySheets(story) {
const target=requireLLMProvider(AI_ROLES.Text2Prompt);
const messages=target.provider.buildTextMessages(LLM_STORY_SHEET_SYSTEM,'ストーリー:\n'+story);
const raw=await target.queue.add(function () {
return target.provider.chat(messages,{temperature: 0.4,jsonObject: true});
});
return parseStorySheets(raw);
}

// 場所と時間はまとめて1行にする。画面ではこの1行を直接編集させ、
// 場面転換の判定もこの文字列の一致で行う。判定がユーザーの手直しに追随するため
function joinPlace(location,time) {
const parts=[location,time].map(function (part) {
return typeof part==='string' ? part.trim() : '';
}).filter(function (part) {
return part;
});
return parts.join(' / ');
}

// 欠けたページを黙って埋めない。どのページが返らなかったかを挙げてエラーにする。
// 戻り値: [{page,summary,place}]
function parseStoryPagePlan(raw,pageNumbers) {
const parsed=parseLLMJsonBody(raw);
if (!parsed||!Array.isArray(parsed.pages)) {
throw new Error(i18next.t('llmStoryboardErrorNotJson'));
}
const byPage={};
parsed.pages.forEach(function (entry) {
if (!entry||typeof entry.summary!=='string') {
return;
}
const page=parseInt(entry.page,10);
if (!page) {
return;
}
const summary=entry.summary.trim();
if (!summary) {
return;
}
byPage[page]={page: page,summary: summary,place: joinPlace(entry.location,entry.time)};
});
const missing=[];
const results=pageNumbers.map(function (page) {
if (!byPage[page]) {
missing.push(page);
return null;
}
return byPage[page];
});
if (missing.length>0) {
throw new Error(i18next.t('storyErrorMissingPage')+' '+missing.join(', '));
}
return results;
}

// pageInfos: [{page,panelCount}]
async function llmStoryPagePlan(story,pageInfos) {
const target=requireLLMProvider(AI_ROLES.Text2Prompt);
const layout=pageInfos.map(function (info) {
return {page: info.page,panelCount: info.panelCount};
});
const userPrompt=[
'ストーリー:',
story,
'',
'ページと、各ページのコマ数:',
JSON.stringify(layout)
].join('\n');
const messages=target.provider.buildTextMessages(LLM_STORY_PAGEPLAN_SYSTEM,userPrompt);
const raw=await target.queue.add(function () {
return target.provider.chat(messages,{temperature: 0.6,jsonObject: true});
});
return parseStoryPagePlan(raw,pageInfos.map(function (info) {
return info.page;
}));
}

// context: {pageSummary,place,sceneChange,prevSummary,prevPlace,nextSummary,
//           pageIndex,pageCount,characterSheet,locationSheet,layout,rightToLeft}
// 戻り値: {entries:[{prompt,role}], warning:string|null}
async function llmStoryPanelPrompts(context) {
const lines=[];
// 作品傾向。どのコマを寄りにして、どのコマを引きにするかはこれを読んでLLMが決める
const tone=mangaToneGuidance();
if (tone) {
lines.push('どんな漫画か:');
lines.push(tone);
lines.push('');
}
if (context.characterSheet) {
// 「そのまま全部」と書くとシステムプロンプト側の「フレームに入る範囲だけ取れ」と食い違い、
// 顔だけのコマにも靴が入る
lines.push('キャラ表。そのコマのフレームに入る範囲だけ使ってください:');
lines.push(context.characterSheet);
lines.push('');
}
if (context.locationSheet) {
lines.push('ロケ表。この場所を写すコマには一字一句そのまま入れてください:');
lines.push(context.locationSheet);
lines.push('');
}
if (context.pageCount>1) {
lines.push('これは全'+context.pageCount+'ページ中の'+context.pageIndex+'ページ目です。');
}
if (context.place) {
lines.push('このページの場所と時間: '+context.place);
}
if (context.sceneChange) {
lines.push('このページから新しい場面が始まります。');
}
lines.push('このページで起きること:');
lines.push(context.pageSummary);
if (context.prevSummary) {
lines.push('');
lines.push('前のページで起きたこと'+(context.prevPlace ? '（'+context.prevPlace+'）' : '')+':');
lines.push(context.prevSummary);
}
if (context.nextSummary) {
lines.push('');
lines.push('次のページで起きること。ここへ繋げるだけで、描かないでください:');
lines.push(context.nextSummary);
}
lines.push('');
lines.push('コマ配置（読み順は'+(context.rightToLeft ? '右から左' : '左から右')+'）:');
lines.push(JSON.stringify(context.layout));
return requestPanelPrompts(LLM_STORY_PANEL_SYSTEM,lines.join('\n'),context.layout.length,context.sceneChange);
}
