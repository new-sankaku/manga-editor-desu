"""Clef-flash を、重みを手元に全部置かずに CPU で動かすための読み込み。

この環境はディスクの空きが約3GB、メモリが15GB（ほかの試作の常駐も含む）で、BF16 の重み約19GB をダウンロードして置けない。
そこで重みは Hugging Face から範囲指定で取り、次の3つに分ける。
- 常駐：画像の部品（約0.9GB）と、選んだ文章の層（1層約0.44GB）。読み込み時に1回取ってメモリに置く
- 都度取得：残りの文章の層。順伝播のたびに、その層の直前に取り（次の層を裏で先に取る）、使い終わったら捨てる
- 行だけ：単語の埋め込み表と出力の埋め込み表（各約2GB）。使う入力の語の行だけを取って置く。
  出力の埋め込み表は同梱の判定部（JointSchemaHead）が選択肢の語の行を引くのにしか使わない
同梱の joint_schema_model.py は中身を読んで、通信やファイルの書き込みが無いことを確かめたうえで import する（sys.path の最後に足す）。
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import math
import queue
import struct
import sys
import threading
import time
from pathlib import Path

import psutil
import requests
import torch

REPO = 'https://huggingface.co/Cloudflare/clef-flash/resolve/main/'
DTYPES = {'BF16': torch.bfloat16, 'F32': torch.float32, 'F16': torch.float16, 'I64': torch.int64}
LAYER = 'model.language_model.layers.'


class RemoteShards:
    """safetensors の各ファイルの見出しだけを取り、テンソルを範囲指定で取る。"""

    def __init__(self, local: Path, parts: int = 4):
        self.local = local
        self.parts = parts
        self.where = {}  # 名前 -> (ファイル, 開始, 終了, dtype, shape)
        self.bytes_fetched = 0
        self.fetch_seconds = 0.0
        self._lock = threading.Lock()
        index = json.loads((local / 'model.safetensors.index.json').read_text())
        for shard in sorted(set(index['weight_map'].values())):
            head = self._get(shard, 0, 7)
            n = struct.unpack('<Q', head)[0]
            meta = json.loads(self._get(shard, 8, 8 + n - 1))
            base = 8 + n
            for name, v in meta.items():
                if name == '__metadata__':
                    continue
                s, e = v['data_offsets']
                self.where[name] = (shard, base + s, base + e, DTYPES[v['dtype']], tuple(v['shape']))

    def _get(self, shard, start, end, out=None, tries=4):
        for i in range(tries):
            try:
                r = requests.get(REPO + shard, headers={'Range': f'bytes={start}-{end}'}, stream=True, timeout=120)
                r.raise_for_status()
                if out is None:
                    data = r.content
                    if len(data) != end - start + 1:
                        raise IOError('short read')
                    return data
                pos = 0
                for chunk in r.iter_content(1 << 22):
                    out[pos:pos + len(chunk)] = chunk
                    pos += len(chunk)
                if pos != len(out):
                    raise IOError(f'short read {pos}/{len(out)}')
                return None
            except Exception:
                if i == tries - 1:
                    raise
                time.sleep(2 * (i + 1))

    def fetch(self, names):
        """名前の組をまとめて取り、{名前: テンソル} を返す。同じファイルで続いている所は1回の範囲で取る。"""
        t0 = time.time()
        out = {}
        by_shard = {}
        for n in names:
            by_shard.setdefault(self.where[n][0], []).append(n)
        for shard, ns in by_shard.items():
            ns.sort(key=lambda n: self.where[n][1])
            lo, hi = self.where[ns[0]][1], max(self.where[n][2] for n in ns)
            need = sum(self.where[n][2] - self.where[n][1] for n in ns)
            if hi - lo > need * 1.05 + (1 << 20):
                raise RuntimeError(f'not contiguous: {shard} {ns[0]}')
            buf = bytearray(hi - lo)
            step = math.ceil(len(buf) / self.parts)
            mv = memoryview(buf)
            with cf.ThreadPoolExecutor(self.parts) as ex:
                futs = [ex.submit(self._get, shard, lo + a, lo + min(a + step, len(buf)) - 1, mv[a:min(a + step, len(buf))])
                        for a in range(0, len(buf), step)]
                for f in futs:
                    f.result()
            whole = torch.frombuffer(buf, dtype=torch.uint8)
            for n in ns:
                _, s, e, dt, shape = self.where[n]
                out[n] = whole[s - lo:e - lo].view(dt).reshape(shape)
            with self._lock:
                self.bytes_fetched += len(buf)
        with self._lock:
            self.fetch_seconds += time.time() - t0
        return out

    def fetch_rows(self, name, ids, chunk_rows=8192):
        """2次元の表から、指定した行だけを取る（表を先頭から流して必要な行だけ残す）。"""
        shard, s, e, dt, shape = self.where[name]
        rows, width = shape
        row_bytes = (e - s) // rows
        ids = sorted(set(int(i) for i in ids))
        table = torch.empty((len(ids), width), dtype=dt)
        pos = {i: k for k, i in enumerate(ids)}
        blocks = sorted(set(i // chunk_rows for i in ids))
        t0 = time.time()

        def one(b):
            a = b * chunk_rows
            z = min(rows, a + chunk_rows)
            buf = bytearray((z - a) * row_bytes)
            self._get(shard, s + a * row_bytes, s + z * row_bytes - 1, memoryview(buf))
            t = torch.frombuffer(buf, dtype=torch.uint8).view(dt).reshape(z - a, width)
            with torch.inference_mode():  # 呼び出し側が inference_mode でも、そうでなくても書き込めるように
                for i in ids:
                    if a <= i < z:
                        table[pos[i]] = t[i - a]
            return len(buf)

        with cf.ThreadPoolExecutor(self.parts) as ex:
            got = sum(ex.map(one, blocks))
        with self._lock:
            self.bytes_fetched += got
            self.fetch_seconds += time.time() - t0
        return ids, table


class SparseRows(torch.nn.Module):
    """語の番号から、取ってある行を引く。取っていない語が来たら止める。"""

    def __init__(self, vocab, ids, table):
        super().__init__()
        m = torch.full((vocab,), -1, dtype=torch.long)
        m[torch.tensor(ids)] = torch.arange(len(ids))
        self.register_buffer('map', m, persistent=False)
        self.table = table

    def __getitem__(self, token_ids):
        return self.forward(token_ids)

    def forward(self, token_ids):
        k = self.map[token_ids]
        if (k < 0).any():
            raise KeyError('token row not fetched: ' + str(token_ids[k < 0][:5].tolist()))
        return self.table[k]


class MemPeak:
    def __init__(self):
        self.proc = psutil.Process()
        self.peak = 0
        self._stop = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while not self._stop.is_set():
            self.peak = max(self.peak, self.proc.memory_info().rss)
            time.sleep(0.2)

    def gb(self):
        return round(self.peak / 1e9, 2)


class ClefStream:
    def __init__(self, local: Path, resident_layers, threads=4):
        torch.set_num_threads(threads)
        if str(local) not in sys.path:
            sys.path.append(str(local))  # 同梱の joint_schema_model.py だけをここから読む
        import joint_schema_model as jsm
        from safetensors.torch import load_file
        from transformers import AutoConfig, AutoProcessor, Qwen3_5ForConditionalGeneration
        from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5TextRotaryEmbedding, Qwen3_5VisionRotaryEmbedding

        self.jsm = jsm
        self.mem = MemPeak()
        t0 = time.time()
        self.cfg = AutoConfig.from_pretrained(local)
        self.processor = AutoProcessor.from_pretrained(local)
        self.tok = self.processor.tokenizer
        with torch.device('meta'):
            m = Qwen3_5ForConditionalGeneration._from_config(self.cfg, dtype=torch.bfloat16)
        m.config.use_cache = False
        vis_head = self.cfg.vision_config.hidden_size // self.cfg.vision_config.num_heads
        m.model.visual.rotary_pos_emb = Qwen3_5VisionRotaryEmbedding(vis_head // 2)
        m.model.language_model.rotary_emb = Qwen3_5TextRotaryEmbedding(config=self.cfg.text_config)
        self.model = m.eval()
        self.remote = RemoteShards(local)
        self.n_layers = self.cfg.text_config.num_hidden_layers
        self.resident = sorted(set(resident_layers))
        self.streamed = [i for i in range(self.n_layers) if i not in self.resident]
        # 常駐：層以外（埋め込み表2つを除く）と、常駐の層
        names = [n for n in self.remote.where if not n.startswith(LAYER)
                 and n not in ('lm_head.weight', 'model.language_model.embed_tokens.weight')]
        for i in self.resident:
            names += self.layer_names(i)
        self._assign(self.remote.fetch(names))
        self.head = jsm.JointSchemaHead(**json.loads((local / 'joint_head_config.json').read_text()))
        self.head.load_state_dict(load_file(local / 'joint_head.safetensors'), strict=True)
        self.head = self.head.to(dtype=torch.bfloat16).eval()
        for i in self.streamed:
            layer = self.model.model.language_model.layers[i]
            layer.register_forward_pre_hook(self._pre(i))
            layer.register_forward_hook(self._post(i))
        self.row_ids = set()
        self.embed = None
        self.out_rows = None
        self.load_seconds = time.time() - t0
        self._q = None

    def layer_names(self, i):
        p = f'{LAYER}{i}.'
        return [n for n in self.remote.where if n.startswith(p)]

    def _assign(self, tensors):
        for name, t in tensors.items():
            mod_name, _, pname = name.rpartition('.')
            mod = self.model.get_submodule(mod_name)
            want = mod._parameters[pname]
            if tuple(want.shape) != tuple(t.shape):
                raise ValueError(f'shape {name} {tuple(want.shape)} != {tuple(t.shape)}')
            # 本来の読み込み（dtype=bfloat16）と同じく、モデルの型にそろえる
            mod._parameters[pname] = torch.nn.Parameter(t if t.dtype == want.dtype else t.to(want.dtype), requires_grad=False)

    def _drop(self, i):
        layer = self.model.model.language_model.layers[i]
        for mod in layer.modules():
            for pname, p in list(mod._parameters.items()):
                if p is not None:
                    mod._parameters[pname] = torch.nn.Parameter(torch.empty(p.shape, dtype=p.dtype, device='meta'), requires_grad=False)

    def _pre(self, i):
        def hook(module, args):
            j, tensors = self._q.get()
            if isinstance(tensors, Exception):
                raise tensors
            assert j == i, (j, i)
            self._assign(tensors)
        return hook

    def _post(self, i):
        def hook(module, args, output):
            self._drop(i)
        return hook

    def _start_prefetch(self):
        self._q = queue.Queue(maxsize=1)  # 使用中1層＋待ち1層＋取得中1層まで

        def run():
            for i in self.streamed:
                try:
                    self._q.put((i, self.remote.fetch(self.layer_names(i))))
                except Exception as e:  # noqa: BLE001 呼び出し側でそのまま投げ直す
                    self._q.put((i, e))
                    return
        threading.Thread(target=run, daemon=True).start()

    def need_rows(self, encoded_records):
        ids = set()
        for r in encoded_records:
            ids.update(r.input_ids)
        ids.add(self.tok.pad_token_id)
        if ids <= self.row_ids:
            return
        self.row_ids |= ids
        vocab = self.cfg.text_config.vocab_size
        ids_e, t_e = self.remote.fetch_rows('model.language_model.embed_tokens.weight', self.row_ids)
        self.embed = SparseRows(vocab, ids_e, t_e)
        self.model.model.language_model.embed_tokens = self.embed
        ids_o, t_o = self.remote.fetch_rows('lm_head.weight', self.row_ids)
        self.out_rows = SparseRows(vocab, ids_o, t_o)

    def encode(self, record, **kw):
        return self.jsm.encode_record(self.tok, record, processor=self.processor, **kw)

    @torch.inference_mode()
    def forward(self, encoded_records):
        """ClefModel.forward と同じ手順。出力の埋め込み表の代わりに、取ってある行を渡す。"""
        self.need_rows(encoded_records)
        batch = self.jsm.collate_records(list(encoded_records), self.tok.pad_token_id, torch.device('cpu'))
        media = batch.get('media') or {}
        text_model = self.model.model
        if not media:
            text_model = text_model.language_model
        self._start_prefetch()
        t0 = time.time()
        f0 = self.remote.fetch_seconds
        out = text_model(input_ids=batch['input_ids'], attention_mask=batch['attention_mask'], use_cache=False, return_dict=True, **media)
        logits = self.head(out.last_hidden_state, batch['input_ids'], batch['attention_mask'], batch['records'], self.out_rows)
        res = []
        for rec, lg in zip(encoded_records, logits):
            res.append({q.question_id: dict(zip(q.option_ids, [float(x) for x in l.float()]))
                        for q, l in zip(rec.questions, lg)})
        info = {'seconds': round(time.time() - t0, 1), 'fetch_seconds_in_pass': round(self.remote.fetch_seconds - f0, 1),
                'tokens': [len(r.input_ids) for r in encoded_records]}
        return res, info


def softmax(d):
    m = max(d.values())
    e = {k: math.exp(v - m) for k, v in d.items()}
    s = sum(e.values())
    return {k: v / s for k, v in e.items()}
