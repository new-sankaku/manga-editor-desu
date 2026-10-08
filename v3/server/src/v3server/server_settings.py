from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """接続先はすべて .env か環境変数で与える。既定値は置かない（足りなければ起動時に止まる）。"""

    model_config = SettingsConfigDict(env_prefix="V3_", env_file=".env", extra="ignore")

    database_url: str
    temporal_address: str
    openfga_url: str
    litellm_url: str
    # compose と同じ .env の LITELLM_MASTER_KEY を読む。LLMを呼ぶときに無ければその場で止める
    litellm_master_key: str | None = Field(
        default=None, validation_alias=AliasChoices("V3_LITELLM_MASTER_KEY", "LITELLM_MASTER_KEY")
    )
    # ログインが入るまでの間だけ使う。"1" のときだけ X-V3-User を利用者として受け取る
    dev_auth: str = "0"
    # ロックの期限（秒）
    lock_ttl_seconds: int = 900
    # 絵のファイルを置くフォルダ。絵を扱う口は、これが無ければ止まる（S3互換の置き場は製品を選んでから足す）
    image_dir: str | None = None
    # 書き出しで文字を描くときの書体のフォルダ。文字を描く書き出しは、これが無ければ止まる
    font_dir: str | None = None
    # 書き出しで使う Node（文字を描く・PSD を書く）
    node_executable: str = "node"
    # PSD を書く台本（v3/psd_writer/write_layered_psd.js）。PSD の書き出しは、これが無ければ止まる
    psd_writer_script: str | None = None
    # 文字を絵にする台本（v3/psd_writer/render_text.js）。文字のある書き出しは、これが無ければ止まる
    text_render_script: str | None = None
    # 書き出したファイルを置くフォルダ。書き出しは、これが無ければ止まる
    export_dir: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
