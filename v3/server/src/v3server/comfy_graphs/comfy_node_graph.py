"""ComfyUI の API 形式（`/prompt` に送る辞書）のノードを足していく小さな道具。

試作では手順ごとにノードの番号を手で書き、5か所で同じ組み方が重複していた。
ここでは番号を道具が振り、つなぎ先が存在するかを足すときに確かめる。
送るのは `service_senders/` の役目で、ここは辞書を組むだけ。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NodeOutput:
    """あるノードの何番目の出力か。入力に渡すと API 形式の `[ノードの番号, 出力の番号]` になる。"""

    node_id: str
    index: int

    def as_link(self) -> list[Any]:
        return [self.node_id, self.index]


@dataclass(frozen=True)
class Node:
    """足したノードの印。`node[0]` で 0 番目の出力を指す。"""

    node_id: str
    class_type: str

    def __getitem__(self, index: int) -> NodeOutput:
        return NodeOutput(self.node_id, index)


class ComfyNodeGraph:
    """ノードを足し、入力をつなぎ替え、最後に `/prompt` 用の辞書を出す。"""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._next_id = 1

    def add(self, class_type: str, **inputs: Any) -> Node:
        """ノードを足す。入力に NodeOutput を渡すとつなぎになる。まだ無いノードへのつなぎは例外。"""
        node_id = str(self._next_id)
        self._next_id += 1
        return self._put(node_id, class_type, inputs)

    def add_named(self, node_id: str, class_type: str, **inputs: Any) -> Node:
        """番号の代わりに名前を付けてノードを足す。送り手が絵を上げて入れる LoadImage に使う
        （名前で入れ先を指すので、入力名の一致で別のノードを書き換えることが起きない。ai-verification.md 1.1 の原因A）。"""
        if node_id in self._nodes or node_id.isdigit():
            raise KeyError(f'ノードの名前 {node_id} は使えない（重なっているか、数字だけ）')
        return self._put(node_id, class_type, inputs)

    def _put(self, node_id: str, class_type: str, inputs: dict[str, Any]) -> Node:
        self._nodes[node_id] = {
            'class_type': class_type,
            'inputs': {name: self._to_value(value) for name, value in inputs.items()},
        }
        return Node(node_id, class_type)

    def connect(self, node: Node, input_name: str, value: Any) -> None:
        """既にあるノードの入力を差し替える（制御を間に挟むときなど）。"""
        inputs = self._node(node)['inputs']
        if input_name not in inputs:
            raise KeyError(f'{node.class_type}（{node.node_id}）に入力 {input_name} がありません')
        inputs[input_name] = self._to_value(value)

    def input_link(self, node: Node, input_name: str) -> NodeOutput:
        """入力に今つながっている出力を返す。つなぎでない入力は例外。"""
        value = self._node(node)['inputs'][input_name]
        if not (isinstance(value, list) and len(value) == 2):
            raise ValueError(f'{node.class_type}（{node.node_id}）の {input_name} はつなぎではありません')
        return NodeOutput(value[0], value[1])

    def nodes_of_type(self, class_type: str) -> list[Node]:
        return [Node(i, n['class_type']) for i, n in self._nodes.items() if n['class_type'] == class_type]

    def to_prompt(self) -> dict[str, dict[str, Any]]:
        """`/prompt` の `prompt` に入れる辞書。写しを返すので、後から道具を触っても変わらない。"""
        return copy.deepcopy(self._nodes)

    def _node(self, node: Node) -> dict[str, Any]:
        if node.node_id not in self._nodes:
            raise KeyError(f'ノード {node.node_id} はこの手順にありません')
        return self._nodes[node.node_id]

    def _to_value(self, value: Any) -> Any:
        if isinstance(value, Node):
            raise TypeError('ノードそのものではなく、node[0] のように出力の番号を付けて渡してください')
        if isinstance(value, NodeOutput):
            if value.node_id not in self._nodes:
                raise KeyError(f'つなぎ先のノード {value.node_id} がこの手順にありません')
            return value.as_link()
        return value
