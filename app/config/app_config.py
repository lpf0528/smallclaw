import os
import yaml
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from typing import Self, Any
from model_config import ModelConfig
from dotenv import load_dotenv
from db_config import load_db_config_from_dict, DbConfig

load_dotenv()


class AppConfig(BaseModel):

    models: list[ModelConfig] = Field(default_factory=list, description="Available models")    # allow:允许接收并存储模型中未显式定义的额外属性。frozen=False:意味着实例在创建后可以被修改
    # (extra="allow":允许传入模型中未定义的额外字段。extra="ignore"：多余字段会被忽略，不保存到模型中)
    # (frozen=False:模型实例不是冻结的，可以修改字段值, frozen=True:模型实例是冻结的，不能修改字段值)
    model_config = ConfigDict(extra="allow", frozen=False)
    dbs: list[DbConfig] = Field(default_factory=list, description="Database configuration")

    @classmethod
    def get_config_path(cls) -> Path:
        # 获取当前工作目录
        path = Path(os.getcwd()) / "config.yaml"
        if not path.exists():
            # 检查父目录是否存在配置文件
            path = Path(os.getcwd()).parent / "config.yaml"
            if not path.exists():
                raise FileNotFoundError("`config.yaml` 文件不存在")
        return path

    @classmethod
    def resolve_env_variables(cls, config: Any) -> Any:
        if isinstance(config, str):
            if config.startswith("$"):
                env_value = os.getenv(config[1:])
                if not env_value:
                    raise ValueError(f"环境变量 {config[1:]} 未设置")
                return env_value
        elif isinstance(config, dict):
            return {key: cls.resolve_env_variables(value) for key, value in config.items()}
        elif isinstance(config, list):
            return [cls.resolve_env_variables(item) for item in config]
        return config

    @classmethod
    def from_file(cls) -> Self:
        resolved_path = cls.get_config_path()
        with open(resolved_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

        # 解析配置文件中的环境变量
        config_data = cls.resolve_env_variables(config_data)

        # Load memory config if present
        # if "memory" in config_data:
        #     load_memory_config_from_dict(config_data["memory"])

        # Load db config if present
        if "dbs" in config_data:
            load_db_config_from_dict(config_data["dbs"])

        result = cls.model_validate(config_data)
        return result


_app_config: AppConfig | None = None


def get_app_config():
    global _app_config
    if _app_config:
        return _app_config
    return AppConfig.from_file()
