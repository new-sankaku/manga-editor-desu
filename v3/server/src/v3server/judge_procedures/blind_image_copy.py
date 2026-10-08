"""評価役に見せる画像の、名前を伏せた写し（試作 p19・p32・p33）。

ファイル名に狙い（感情・段・候補の番号など）が入ったまま見せると、名前から答えが読めて判定が甘くなる
（p19 で、名前のまま 92/96 が一致し、伏せると 84/96）。評価役には必ずこの写しを見せる。
写しの名前は、元の場所と salt から作る。並べる順も写しの名前の順にして、並びから答えが読めないようにする。
"""
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BlindCopies:
    """元の画像と、名前を伏せた写しの対応。"""

    # 元の場所（渡されたままの文字列）→ 写しの場所
    blind_path_by_original: dict[str, Path]

    def blind_name(self, original: str) -> str:
        return self.blind_path_by_original[original].name

    def original_of(self, blind_name: str) -> str:
        for original, path in self.blind_path_by_original.items():
            if path.name == blind_name:
                return original
        raise KeyError(blind_name)

    def sorted_originals(self, originals: list[str]) -> list[str]:
        """originals を写しの名前の順に並べ替える（重なりは除く）。"""
        return sorted(set(originals), key=self.blind_name)


def _blind_name(original: str, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}\0{Path(original).resolve()}".encode()).hexdigest()[:16]
    return f"img_{digest}{Path(original).suffix.lower()}"


def make_blind_copies(originals: list[str], dest_dir: str, salt: str) -> BlindCopies:
    """originals の写しを dest_dir に作る。salt は判定ごとに変えてよい（同じ salt なら同じ名前になる）。"""
    if not originals:
        raise ValueError("originals が空")
    if not salt:
        raise ValueError("salt が空")
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, Path] = {}
    for original in dict.fromkeys(originals):
        src = Path(original)
        if not src.is_file():
            raise FileNotFoundError(original)
        path = dest / _blind_name(original, salt)
        if path in mapping.values():
            raise ValueError(f"写しの名前が重なった: {path.name}")
        shutil.copyfile(src, path)
        mapping[original] = path
    return BlindCopies(mapping)
