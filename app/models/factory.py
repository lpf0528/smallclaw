import logging
from langchain_openai import ChatOpenAI
from langchain.chat_models import BaseChatModel
from app.config.app_config import get_app_config


logger = logging.getLogger(__name__)


def create_chat_model(name: str | None = None, **kwargs) -> BaseChatModel:
    config = get_app_config()
    if name is None:
        name = config.models[0].name
    model_config = config.get_model_config(name)
    if model_config is None:
        raise ValueError(f"模型 {name} 未配置") from None
    model_settings_from_config = model_config.model_dump(
        exclude_none=True,  # 值为 None 的字段不放进结果字典里。
        exclude={  # 排除以下字段：
            "name",
            "display_name",
            "supports_thinking",
            "supports_vision",
        },
    )
    model_instance = ChatOpenAI(**model_settings_from_config)
    return model_instance
