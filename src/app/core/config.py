from dataclasses import dataclass
import environs

env = environs.Env()
env.read_env()


@dataclass
class Settings:
    bot_token: str 
    tg_api_server_url: str
    admins_ids: list[int]
    redis_url: str
    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: int = 5432
    click_provider_token: str | None = None
    payme_provider_token: str | None = None
    payment_card: str = "8600 1234 5678 9012"
    webhook_url: str | None = None
    webhook_path: str = "/webhook"
    use_webhook: bool = False

    def construct_postgresql_url(self):
        postgresql_dsn = (
            f"postgresql+asyncpg://"
            f"{self.db_user}:"
            f"{self.db_password}@"
            f"{self.db_host}:"
            f"{self.db_port}/"
            f"{self.db_name}"
        )
        return postgresql_dsn


def load_config() -> Settings:
    return Settings(
        bot_token=env.str("BOT_TOKEN"),
        tg_api_server_url=env.str("TG_API_SERVER_URL"),
        admins_ids=env.list("ADMINS_IDS", subcast=int),
        db_name=env.str("POSTGRES_DB"),
        db_user=env.str("POSTGRES_USER"),
        db_password=env.str("POSTGRES_PASSWORD"),
        db_host=env.str("POSTGRES_HOST"),
        db_port=env.int("POSTGRES_PORT"),
        redis_url=env.str("REDIS_URL"),
        click_provider_token=env.str("CLICK_PROVIDER_TOKEN", None),
        payme_provider_token=env.str("PAYME_PROVIDER_TOKEN", None),
        payment_card=env.str("PAYMENT_CARD", "8600 1234 5678 9012"),
        webhook_url=env.str("WEBHOOK_URL", None),
        webhook_path=env.str("WEBHOOK_PATH", "/webhook"),
        use_webhook=env.bool("USE_WEBHOOK", False)
    )
