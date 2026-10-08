from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ログインの方式で、それぞれ要る設定
_OIDC_FIELDS = ("oidc_issuer", "oidc_discovery_url", "oidc_client_id", "oidc_client_secret", "public_url",
                "session_secret", "session_max_age_seconds")
# S3互換の置き場で要る設定
_S3_FIELDS = ("s3_endpoint_url", "s3_bucket", "s3_region", "s3_access_key_id", "s3_secret_access_key")


class Settings(BaseSettings):
    """接続先はすべて .env か環境変数で与える。既定値は置かない（足りなければ起動時に止まる）。
    None にしてあるものは「その機能を使うときだけ要る」もので、使うのに無ければ止まる。"""

    model_config = SettingsConfigDict(env_prefix="V3_", env_file=".env", extra="ignore")

    database_url: str
    temporal_address: str
    openfga_url: str
    litellm_url: str
    # compose と同じ .env の LITELLM_MASTER_KEY を読む。LLMを呼ぶときに無ければその場で止める
    litellm_master_key: str | None = Field(
        default=None, validation_alias=AliasChoices("V3_LITELLM_MASTER_KEY", "LITELLM_MASTER_KEY")
    )

    # ---- ログイン（V3サーバーの土台 1.3）
    # oidc: Keycloak の OIDC でログインする。dev_header: 開発と試験だけ。X-V3-User の値をそのまま利用者にする
    auth_mode: Literal["oidc", "dev_header"]
    # 本番のイメージ（Dockerfile）は 1 にしてある。1 のとき dev_header では起動しない
    forbid_dev_header: bool = False
    # 発行元（トークンの iss と同じ文字列。利用者のブラウザが開く住所）
    oidc_issuer: str | None = None
    # サーバーが発行元の設定を読みに行く住所（コンテナの中からは発行元の公開の住所に届かないことがあるため別に持つ）
    oidc_discovery_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    # 利用者がこのサーバーを開く住所（https://...）。ログインから戻る先とクッキーの Secure を決める
    public_url: str | None = None
    # セッションのクッキーに署名する鍵
    session_secret: str | None = None
    # ログインしてからセッションが切れるまでの秒数（使い続けても延びない）
    session_max_age_seconds: int | None = None

    # ロックの期限（秒）
    lock_ttl_seconds: int

    # ---- 絵のファイルの置き場（image_file_storage.py）
    # local: サーバーの手元のフォルダ（開発用。V3_IMAGE_DIR）。s3: S3互換の置き場（本番は SeaweedFS）
    image_store: Literal["local", "s3"]
    image_dir: str | None = None
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    # 書き出しで文字を描くときの書体のフォルダ。文字を描く書き出しは、これが無ければ止まる
    font_dir: str | None = None
    # 書き出しで使う Node（文字を描く・PSD を書く）
    node_executable: str
    # PSD を書く台本（v3/psd_writer/write_layered_psd.js）。PSD の書き出しは、これが無ければ止まる
    psd_writer_script: str | None = None
    # 文字を絵にする台本（v3/psd_writer/render_text.js）。文字のある書き出しは、これが無ければ止まる
    text_render_script: str | None = None
    # 書き出したファイルを置くフォルダ。書き出しは、これが無ければ止まる
    export_dir: str | None = None

    @model_validator(mode="after")
    def _required_by_mode(self) -> "Settings":
        if self.auth_mode == "dev_header" and self.forbid_dev_header:
            raise ValueError("このイメージでは V3_AUTH_MODE=dev_header を使えない（V3_FORBID_DEV_HEADER=1）")
        if self.auth_mode == "oidc":
            _require(self, _OIDC_FIELDS, "V3_AUTH_MODE=oidc")
        if self.image_store == "s3":
            _require(self, _S3_FIELDS, "V3_IMAGE_STORE=s3")
        return self


def _require(s: Settings, fields: tuple[str, ...], why: str) -> None:
    missing = [f"V3_{f.upper()}" for f in fields if getattr(s, f) in (None, "")]
    if missing:
        raise ValueError(f"{why} には {', '.join(missing)} が要る")


@lru_cache
def get_settings() -> Settings:
    return Settings()
