// ネーム（あらすじ）からページ内の全コマ分のプロンプトを一括生成する。
// タグを直接書かせず「そのコマが何をするコマか（役割）」を先に宣言させる。
// 「どのコマにも人物が描かれていてページに緩急がない」状態を避けるため

// 「伝えたいこと → 役割 → フレームに入れるもの」の対応表。
// 役割をラベル（バストアップ等）で定義すると「upper bodyと書けばそうなる」という
// 誤解を招くので、フレームに何が入るかで書く。
// 文面は llm_doc/manga-page-guideline.md の4・16章がそのまま元
const MANGA_PANEL_ROLES=[
'  見せたいもの                役割           フレームに入るもの',
'  どこにいるか                establishing   その場所。フレームに収まらない大きさのもの。人はいないか、点になるほど小さい',
'  空気・時間の経過            scenery        その場所を人なしで、動きなしで',
'  誰がどこにどう立っているか  full           1人以上を頭から靴まで、立っている床ごと',
'  誰が何をしているか          medium         腰から上と手。足と床はフレームの外',
'  誰が何を感じているか        closeup        顔。目と口。肩から下は入らない',
'  物が何であるか              insert         ディテール1つだけ。物、手、目',
'  そのページで一番の瞬間      impact         傾いたか煽った視点。背景は落としてよい'
].join('\n');

// 表情・視線・仕草はここに挙げたタグだけを使わせる（閉じた語彙）。
// 全部Danbooruで件数を確認した実在タグ。件数は渡さない。
// 素の感情ラベル（smile / angry / sad / surprised / crying / laughing）は入れない
const MANGA_EXPRESSION_TAGS=[
'  眉    v-shaped eyebrows, raised eyebrow',
'  目    closed eyes, half-closed eyes, narrowed eyes, wide-eyed, parted lips, tears, tearing up',
'  口    closed mouth, open mouth, frown, clenched teeth, wavy mouth, pout, light smile,',
'        grin, smirk',
'  顔    expressionless, serious, glaring, annoyed, scowl, nervous, embarrassed, blush,',
'        shaded face',
'  視線  looking at another, looking to the side, looking down, looking up, looking away,',
'        averting eyes, looking back, profile, from behind, looking at viewer, eye contact',
'  手    clenched hand, clenched hands, own hands together, hand on own chest, hand on own face,',
'        hand on own hip, hands in pockets, covering face',
'  体    leaning forward, crossed arms, head tilt, turning head, trembling',
'  状態  sweat, sweatdrop'
].join('\n');

const MANGA_PANEL_ROLE_NAMES=['establishing','scenery','insert','full','medium','closeup','impact'];

// 人物を出さないコマの役割。この3つだけが「間」を作れる
const MANGA_EMPTY_ROLES=['establishing','scenery','insert'];

// これ以上のコマ数で全コマに人物が居たら、間が無いページとして作り直させる。
// 3コマ以下は1つの場面を割っただけのこともあるので数えない
const MANGA_MIN_PANELS_NEEDING_BREATH=4;

// ネーム用とストーリー用でルール本体を共有する。片方だけ直して食い違うのを防ぐ。
// consistencyRules: 呼び出し側だけに要る一貫性のルール
//
// 書き方の決まり:
// - 判断の余地があるものは「こうしろ」と書かず、選べる手を並べる。
//   決め打ちで書くと毎回同じ出力になる
// - 判断の余地がないもの（出力形式・モデルの挙動・アプリの制約）だけ断定する
// - 比喩・言い換え・反語を使わない
function buildPanelSystemPrompt(consistencyRules) {
return [
'このページの全コマ分の、画像生成用プロンプトを書いてください。',
'',
'進め方の目安です。ページによって前後して構いません。',
'  1. このページで読者が新しく知ることを書き出す',
'  2. 前のページから場所が変わったか見る',
'  3. 各コマに何を担当させるか決める',
'  4. 距離を決める',
'  5. アングルを決める',
'  6. タグに落とす',
'',
'──────────────────────────────',
'',
'■ ページに何をどう配るか',
'',
'・1コマに1つの内容だと読みやすい。2つ入れると両方読み飛ばされやすい',
'・書き出した内容がコマ数より多いとき',
'    重要でないものを落とす / 近い2つを1コマにまとめる / 次ページの担当にせず削る',
'・少ないとき',
'    1つを複数コマに割る（手が伸びる → 掴まれる） / 人物のいないコマを挟む /',
'    1コマを引きにして状況を足す',
'',
'■ 場所が変わったとき',
'',
'前のページと場所が違う場合、読者は前の場所のつもりでページをめくります。',
'よく使われる手:',
'・1コマ目で場所を見せる（一番確実）',
'・その場所にある物の寄りから入り、次のコマで引く',
'・人物の後ろに場所の特徴を大きく入れて、場所と人物を同時に見せる',
'場所が変わっていないなら、見せ直さなくて構いません。',
'',
'■ 距離の選び方',
'',
'読者に何を見せたいかで距離が決まります。',
MANGA_PANEL_ROLES,
'',
'・見せたいものが変わったところで距離を変えると、変化が読者に伝わりやすい',
'・同じ距離が3コマ以上続くときは、本当に同じものを見せているか一度確かめる',
'・人物のいないコマは、場所・時間経過・直前の余韻のどれかを担うと効きます。',
'  どれも担っていないと、ただの空きコマになりやすい',
'',
'■ アングル',
'',
'・目線の高さ … 中立。特に理由がないとき',
'・煽り（下から）… 対象が大きく見える。圧力をかける側／見上げている人物の視点',
'・俯瞰（上から）… 対象が小さく見え、周囲が読める。場所の説明／人物を1人にする',
'・傾き … 不安定。衝撃・アクション',
'傾きを1ページで何度も使うと、どれも不安定に見えなくなります。',
'',
'■ 渡されたコマ配置の使い方',
'',
'コマの大きさと形は既に決まっています。それに合う内容を割り当てると読みやすくなります。',
'・大きいコマ … 引きの絵／そのページで一番重要な瞬間',
'・小さいコマ … 顔／ディテール1つ。引きの絵はそのサイズでは読めません',
'・横長 … 引きの絵／並んだ人物',
'・縦長 … 立っている人物を頭から爪先まで',
'・"bleed" … 絵が紙の端を越えて続く。開けた絵／一番重要なコマ。',
'  他のコマが枠に収まっている間だけ強く見えます',
'・"last" … 読者はここでページをめくるか決めます。よく使われる手:',
'    動作の途中で切る／表情で切る／答えの前で切る／問いかけで切る',
'  説明で終わると、めくる理由が無くなりやすい',
'',
'■ 背景',
'',
'・場所を見せるコマ（establishing / scenery / full / medium）',
'    場所が分かるタグ2つ以上と、光か時間帯を1つ入れると場所が伝わります',
'・寄り・インサート … 背景を落としてよい',
'・そのページでまだ場所を見せていないうちに落とすと、読者は場面がどこか分からないまま進みます',
'・同じ場所のコマは、同じ場所タグを一字一句そのまま繰り返す。',
'  言い回しを変えると別の場所として描かれます',
'・落とした背景の代わりに置くもの（例）:',
'    孤立させたいなら空白／速さを運ぶなら動き／衝撃なら放射する線',
'  全コマで同じものを使うと、ページが単調になります',
'',
'■ 人物がどこを見るか',
'',
'人物が見ている方向が、読者をページの中で動かします。',
'・2人が会話しているコマ … 互いを見せると視線が2人の間を往復します',
'・次のコマへ運びたい … 人物を背けるか、横へ向ける',
'・読者と目が合うコマは、そこで視線が止まります。止めたいコマで使うと効きます。',
'  最後のコマ／一番重要なコマ／読者に向けたセリフ。',
'  それ以外のコマで使うと、ページの流れが切れやすい',
'',
'■ セリフの場所を残す',
'',
'吹き出しはエディタが後から絵の上に描きます。顔でフレームを埋めると置く場所が無くなります。',
'余白を作る方法は次の2つです。それ以外の書き方では空きません。',
'・距離を1段引く。セリフが1〜2行を超えるコマは closeup にしない。',
'  人物が小さいほどフレームに余りが出ます',
'・人物の頭より上にあるものを名指しする。フレームがそれを含めるために上へ伸びます。',
'  何があるかは場所によります',
'"space" "empty space" "room for text" と書いても空きません。',
'セリフの無いコマはフレーム全部を使えます。引きの絵と重要なコマはそこに置けます。',
'セリフが多いコマは絵を単純にする（背景を落とす／動きを止める）と、どちらも読まれます。',
'',
'■ 感情',
'',
'"angry" "sad" "happy" "surprised" "smiling" は、かすかな状態から極端な状態までを',
'ひとつの語で覆っているため、書くと極端な側が出ます。使わずに、',
'顔が何をしているかを名指ししてください。',
'',
'漫画では、手・肩・汗・顔の影のほうが顔より多くの感情を運ぶことがよくあります。',
'表情より先に仕草を決めると、抑えた芝居になりやすい。',
'',
'感情を抑えているコマでは、口が閉じていると書いてください。書かないと口が開きます。',
'同じ表情が2コマ続くと、変化が読者に伝わりません。',
'',
'──────────────────────────────',
'',
'【必ず守ること】',
'',
'・表情・視線・仕草は、次のタグだけを使う',
MANGA_EXPRESSION_TAGS,
'  それ以外（場所・服・動作・物）は通常のDanbooru語彙から自由に選ぶ',
'',
'・"wide shot" "full body" "upper body" "close-up" は出来上がった絵に付いたラベルで、',
'  書いてもその距離にはならない。距離はどれを名指しするかで決まる',
'    頭から靴まで … 靴、脚、立っている床を名指しする',
'    腰から上     … 腰から上の服、手。靴も床も名指ししない',
'    顔           … 目、口、髪、表情。肩から下は名指ししない',
'    その場所     … その場所にあってフレームに収まらない大きさのもの',
'  欲しいフレームの外にあるものを名指しすると、それを含めるために視点が引きます。',
'  フレーミングタグを補助として足すのは構いませんが、名指しした内容と矛盾しないこと',
'',
'・指定しないとモデルは「1人・胸から膝・正面・カメラ目線」を出します。',
'  視線の方向を書いて外してください',
'',
'・各コマにいる人数を数え、そのコマの人数タグでプロンプトを始める。',
'  そのコマで数える。前のコマから引き継がない。1人だけのときにだけ "solo"',
'',
'・"comic" "panel" "border" "speech bubble" "text" "4koma" は出さない。',
'  枠と吹き出しはエディタが描きます。擬音もエディタがテキストで足すので、',
'  画像に文字を求めないでください',
'',
'・フレームが人物を切ることについて書かない。エディタが扱います',
'',
'・上の表情タグ一覧を除き、この指示に出てくるタグや語は「どういう種類か」を示す例です。',
'  このコマ・この場所・この人物に要るものを選んでください。',
'  答える前に見渡して、キャラでも場所でもないタグが大半のコマに出ていたら、',
'  この指示から写したものなので外してください',
'',
'・タグの数は、読者がそのコマで見る必要があるものを書いて止める。',
'  少なすぎるとモデルが勝手に埋め、多すぎると1つ1つが弱くなって距離も決まらなくなります。',
'  場所を見せるコマは多く、顔1つのコマは少なくなります',
'',
'■ 人物と場所を同じに保つ'
].concat(consistencyRules).concat([
'・与えられていないキャラ名・作品名を作らない',
'',
'【出力】',
'・JSONのみ。形は {"panels":[{"index":1,"role":"<役割名>","prompt":"<タグ>"}]}',
'・受け取ったコマindexすべてに1件ずつ、同じ順で。増やさない・落とさない',
'・"role" は次のどれか: '+MANGA_PANEL_ROLE_NAMES.join(', '),
'・"prompt" は小文字のDanbooru形式タグをカンマ区切り。文章も説明も入れない'
]).join('\n');
}

const LLM_STORYBOARD_SYSTEM=buildPanelSystemPrompt(
['・同じ人物だと読者が分かるよう、そのキャラが出るたびに顔と髪のタグを繰り返す。'
+'服はその部分がフレームに入るときだけ入れる']
);

function sortPanelsInReadingOrder(panels,rightToLeft) {
var items=panels.map(function (panel) {
return {panel: panel,rect: panel.getBoundingRect()};
});
items.sort(function (a,b) {
return a.rect.top-b.rect.top;
});
var rows=[];
items.forEach(function (item) {
var centerY=item.rect.top+item.rect.height/2;
var row=null;
for (var i=0;i<rows.length;i++) {
if (centerY>=rows[i].top&&centerY<=rows[i].bottom) {
row=rows[i];
break;
}
}
if (!row) {
row={top: item.rect.top,bottom: item.rect.top+item.rect.height,items: []};
rows.push(row);
}
row.items.push(item);
});
var ordered=[];
rows.forEach(function (row) {
row.items.sort(function (a,b) {
return rightToLeft ? b.rect.left-a.rect.left : a.rect.left-b.rect.left;
});
ordered=ordered.concat(row.items);
});
return ordered;
}

function buildPanelLayoutSummary(ordered) {
var canvasWidth=canvas.getWidth();
var canvasHeight=canvas.getHeight();
// 紙面の1%以内に寄っていれば断ち切り扱い。枠線の太さ分だけ内側にあることがある
var edge=Math.max(canvasWidth,canvasHeight)*0.01;
var totalArea=0;
ordered.forEach(function (item) {
totalArea+=item.rect.width*item.rect.height;
});
return ordered.map(function (item,i) {
var area=item.rect.width*item.rect.height;
var ratio=item.rect.width/item.rect.height;
var shape='square';
if (ratio>1.3) shape='landscape';
else if (ratio<0.77) shape='portrait';
return {
index: i+1,
shape: shape,
widthPercent: Math.round(item.rect.width/canvasWidth*100),
heightPercent: Math.round(item.rect.height/canvasHeight*100),
areaSharePercent: totalArea>0 ? Math.round(area/totalArea*100) : 0,
// 断ち切りコマ。紙の外へ抜けるので引きの絵や見せ場に向く
bleed: item.rect.left<=edge
||item.rect.top<=edge
||item.rect.left+item.rect.width>=canvasWidth-edge
||item.rect.top+item.rect.height>=canvasHeight-edge,
first: i===0,
last: i===ordered.length-1
};
});
}

function promptHasTag(prompt,tag) {
return prompt.toLowerCase().split(',').some(function (part) {
return part.trim()===tag;
});
}

// 役割の配分を見て、守られていない点を文にして返す。ページの緩急そのものなので
// 足りないまま黙って通さない。sceneChange: このページが新しい場面で始まるか
function findPanelRhythmProblem(entries,sceneChange) {
var problems=[];
// 何枚を人物なしにするかは指定しない。LLMが判断する。
// ここで見るのは「1枚も無い」という壊れ方だけ。LLMは放っておくと全コマを
// 人物のバストアップで埋めるので、その一点だけ拾う
if (entries.length>=MANGA_MIN_PANELS_NEEDING_BREATH) {
var empty=entries.filter(function (entry) {
return MANGA_EMPTY_ROLES.indexOf(entry.role)>=0&&promptHasTag(entry.prompt,'no humans');
}).length;
if (empty===0) {
problems.push('このページは'+entries.length+'コマ全部に人物が入っています。'
+'人物のいないコマが1枚も無いと、読者に息を継ぐところがありません。'
+'establishing / scenery / insert のどれかで、プロンプトに "no humans" が入るコマを'
+'少なくとも1つ作ってください。何枚要るかは内容次第です。');
}
}
// 場面転換の直後に場所が見えないと、読者はどこの話か分からないまま次のコマへ進む
if (sceneChange&&entries.length>0&&entries[0].role!=='establishing') {
problems.push('このページは新しい場面から始まります。読者は前のページの場所のつもりで'
+'めくってくるので、他のことが起きる前に現在地を見せる必要があります。'
+'1コマ目が "'+(entries[0].role||'unknown')+'" になっています。establishing にしてください。');
}
return problems.length>0 ? problems.join('\n') : null;
}

function parseStoryboardResponse(raw,expectedCount) {
var body=raw.replace(/```[a-z]*\n?/gi, '').replace(/```/g,'').trim();
var parsed;
try {
parsed=JSON.parse(body);
} catch (e) {
throw new Error(i18next.t('llmStoryboardErrorNotJson'));
}
if (!parsed||!Array.isArray(parsed.panels)) {
throw new Error(i18next.t('llmStoryboardErrorNotJson'));
}
var byIndex={};
parsed.panels.forEach(function (entry) {
if (!entry) return;
var index=parseInt(entry.index,10);
if (!index||index<1||index>expectedCount) return;
if (typeof entry.prompt!=='string') return;
var tags=normalizeTagOutput(entry.prompt);
if (!tags) return;
var role=typeof entry.role==='string' ? entry.role.trim().toLowerCase() : '';
byIndex[index]={
prompt: tags,
// 知らない役割名は空にする。役割の表示と緩急の判定に使うだけなので、
// 勝手に近い役割へ寄せると人物なしコマを数え違える
role: MANGA_PANEL_ROLE_NAMES.indexOf(role)>=0 ? role : ''
};
});
var missing=[];
var results=[];
for (var i=1;i<=expectedCount;i++) {
if (!byIndex[i]) {
missing.push(i);
}
results.push(byIndex[i]||{prompt: '',role: ''});
}
if (missing.length>0) {
throw new Error(i18next.t('llmStoryboardErrorMissing')+' '+missing.join(', '));
}
return results;
}

function callPanelPrompts(target,systemPrompt,userPrompt,expectedCount) {
var messages=target.provider.buildTextMessages(systemPrompt,userPrompt);
return target.queue.add(function () {
return target.provider.chat(messages,{temperature: 0.6,jsonObject: true});
}).then(function (raw) {
return parseStoryboardResponse(raw,expectedCount);
});
}

// 役割の配分が守られていなければ違反内容を添えて1度だけ作り直す。
// 2度目も守られなければ結果は返すが、警告を必ず画面へ返す。黙って通さない。
// 戻り値: {entries:[{prompt,role}], warning:string|null}
async function requestPanelPrompts(systemPrompt,userPrompt,expectedCount,sceneChange) {
var target=requireLLMProvider(AI_ROLES.Text2Prompt);
var entries=await callPanelPrompts(target,systemPrompt,userPrompt,expectedCount);
var problem=findPanelRhythmProblem(entries,sceneChange);
if (problem) {
var retryPrompt=userPrompt+'\n\n前の回答は次の理由で受け付けられませんでした:\n'+problem;
entries=await callPanelPrompts(target,systemPrompt,retryPrompt,expectedCount);
problem=findPanelRhythmProblem(entries,sceneChange);
}
return {entries: entries,warning: problem};
}

// 戻り値: {entries:[{panel,index,prompt,role}], warning:string|null}
async function llmStoryboard(synopsis,rightToLeft) {
var panels=getPanelObjectList();
if (!panels||panels.length===0) {
throw new Error(i18next.t('llmStoryboardErrorNoPanel'));
}
var ordered=sortPanelsInReadingOrder(panels,rightToLeft);
var layout=buildPanelLayoutSummary(ordered);
// 作品傾向。どのコマを寄りにして、どのコマを引きにするかはこれを読んでLLMが決める
var tone=mangaToneGuidance();
var userPrompt=(tone ? ['どんな漫画か:',tone,''] : []).concat([
'このページのあらすじ:',
synopsis,
'',
'コマ配置（読み順は'+(rightToLeft ? '右から左' : '左から右')+'）:',
JSON.stringify(layout)
]).join('\n');
// ネーム窓は1ページ単体。前のページが無いので必ず場面の始まりとして扱う
var result=await requestPanelPrompts(LLM_STORYBOARD_SYSTEM,userPrompt,ordered.length,true);
return {
entries: ordered.map(function (item,i) {
return {panel: item.panel,index: i+1,prompt: result.entries[i].prompt,role: result.entries[i].role};
}),
warning: result.warning
};
}
