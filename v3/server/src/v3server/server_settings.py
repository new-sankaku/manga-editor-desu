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


@lru_cache
def get_settings() -> Settings:
    return Settings()
