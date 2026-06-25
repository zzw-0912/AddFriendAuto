from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "FriendAuto"
    debug: bool = True
    database_url: str = "sqlite:///./friendauto.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 1440
    refresh_token_expire_minutes: int = 43200
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    wechat_mch_id: str = ""
    wechat_api_key: str = ""
    alipay_app_id: str = ""
    alipay_private_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
