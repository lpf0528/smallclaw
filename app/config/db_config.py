
from pydantic import BaseModel, Field, ConfigDict


class DbConfig(BaseModel):
    name: str = Field(default="postgres", description="Database name")
    model_config = ConfigDict(extra="allow")


_db_config: DbConfig | None = None


def get_db_config() -> DbConfig:
    global _db_config
    if _db_config is None:
        _db_config = DbConfig()
    return _db_config


def load_db_config_from_dict(config_dict: dict) -> None:
    global _db_config
    _db_config = DbConfig(**config_dict)
