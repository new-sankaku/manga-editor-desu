// SSE を fetch で読む（EventSource は X-V3-User を付けられない）。切れたら呼び手に知らせ、呼び手が snapshot を取り直して
// last_event_id の続きからつなぎ直す（harness.js の connect）。
// 形は https://html.spec.whatwg.org/multipage/server-sent-events.html の「event stream の解釈」に合わせる（id・event・data・retry）。

export async function readStream(url, headers, { onEvent, onOpen, signal }) {
  const r = await fetch(url, { headers: { ...headers, Accept: "text/event-stream" }, signal });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  onOpen();
  const reader = r.body.pipeThrough(new TextDecoderStream()).getReader();
  // サーバーは何も無くても15秒ごとに生存の知らせを送る（live_stream.py）。35秒何も来なければ切れたとみなす
  let watchdog;
  const arm = () => { clearTimeout(watchdog); watchdog = setTimeout(() => reader.cancel("無音"), 35000); };
  arm();
  try {
    return await pump(reader, onEvent, arm);
  } finally { clearTimeout(watchdog); }
}

async function pump(reader, onEvent, arm) {
  let buf = "";
  let ev = { id: null, event: "message", data: [] };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;  // 送り手が閉じた（か無音で切った）。呼び手は切断として扱う
    arm();
    buf += value;
    let nl;
    while ((nl = buf.search(/\r\n|\r|\n/)) >= 0) {
      const line = buf.slice(0, nl);
      buf = buf.slice(nl + (buf[nl] === "\r" && buf[nl + 1] === "\n" ? 2 : 1));
      if (line === "") {
        if (ev.data.length) onEvent({ id: ev.id, event: ev.event, data: JSON.parse(ev.data.join("\n")) });
        ev = { id: null, event: "message", data: [] };
        continue;
      }
      if (line.startsWith(":")) continue;  // 生存の知らせ
      const i = line.indexOf(":");
      const field = i < 0 ? line : line.slice(0, i);
      const val = i < 0 ? "" : line.slice(i + 1).replace(/^ /, "");
      if (field === "id") ev.id = val;
      else if (field === "event") ev.event = val;
      else if (field === "data") ev.data.push(val);
    }
  }
}
