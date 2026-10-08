// 進み具合を読みに行く間（ミリ秒）。画面の試験だけが、localStorage の v3.test.poll_ms で短くする（V3画面の一覧.md 4章）。
// 試験の外では入れない値なので、入っていなければ画面ごとに決めた間を使う。入っているときは画面の端に出して隠さない。
const KEY = "v3.test.poll_ms";

export function pollMs(normalMs) {
  let v = null;
  try { v = localStorage.getItem(KEY); } catch { v = null; /* 読めない環境では試験の設定も無い */ }
  if (v === null) return normalMs;
  const ms = Number(v);
  if (!(ms > 0)) throw new Error(`${KEY} は正の数にしてください（今：${v}）`);
  if (!document.getElementById("v3-test-poll")) {
    const tag = document.createElement("div");
    tag.id = "v3-test-poll";
    tag.className = "meta";
    tag.textContent = `試験の設定：進み具合を ${ms}ms ごとに読む（${KEY}）`;
    tag.style.cssText = "position:fixed;left:4px;bottom:4px;pointer-events:none;z-index:9999";
    document.body.appendChild(tag);
  }
  return ms;
}
