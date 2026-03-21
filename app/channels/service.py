import logging
from typing import Any
from .feishu import FeishuChannel
from .message_bus import MessageBus
from .manager import ChannelManager, DEFAULT_LANGGRAPH_URL, DEFAULT_GATEWAY_URL
from .store import ChannelStore
from app.config.app_config import get_app_config

logger = logging.getLogger(__name__)


class ChannelService:
    def __init__(self, channels_config: dict[str, Any] | None = None):

        self.bus = MessageBus()
        self.store = ChannelStore()

        config = dict(channels_config or {})

        self.manager = ChannelManager(
            self.bus,
            store=self.store,
            langgraph_url=config.pop("langgraph_url", DEFAULT_LANGGRAPH_URL),
            gateway_url=config.pop("gateway_url", DEFAULT_GATEWAY_URL),
            default_session=config.pop('session', None),  # 全局 session 默认值
            channel_sessions={  # 渠道单独配置，可以覆盖全局的session配置
                name : channel_config.get('session')
                for name, channel_config in config.items() if isinstance(channel_config , dict)
            },
        )
        self._config = config
        self.is_running = False

    async def start(self):
        if self.is_running:
            return

        # 启动通道管理器, 启动调度循环
        logger.info("启动通道管理器, 启动调度循环")
        await self.manager.start()
        # 启动飞书通道
        channel = FeishuChannel(self.bus, config=self._config.get('feishu', {}))
        await channel.start()

        self._running = True
        print("ChannelService start done")


# 使用单例模式, 确保只有一个实例
_channel_service: ChannelService | None = None


async def start_channel_service():
    global _channel_service
    if _channel_service:
        return _channel_service
    config = get_app_config()
    extra = config.model_extra or {}

    channels_config = extra.get('channels') if 'channels' in extra else {}
    _channel_service = ChannelService(channels_config=channels_config)
    await _channel_service.start()
    return _channel_service
