from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    database_url: str
    storage_channel_id: int
    admin_chat_id: int
    admin_ids: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""

    cbe_account: str = "1000XXXXXXXXX"
    telebirr_number: str = "09XXXXXXXX"
    account_holder: str = "Account Holder"
    price_etb: int = 300
    
    university_name: str = "Addis Ababa University"
    courses: str = "MATH101:Applied Mathematics I, PHYS101:General Physics, CHEM101:General Chemistry, COMP101:Intro to Computing"

    @property
    def courses_dict(self) -> dict[str, str]:
        res = {}
        for part in self.courses.split(","):
            part = part.strip()
            if not part: continue
            if ":" in part:
                code, name = part.split(":", 1)
                res[code.strip().upper()] = name.strip()
            else:
                res[part.upper()] = part.upper()
        return res

    @field_validator("database_url")
    @classmethod
    def _asyncpg_driver(cls, v: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    @property
    def admin_id_set(self) -> set[int]:
        return {int(x) for x in self.admin_ids.replace(" ", "").split(",") if x}


settings = Settings()
