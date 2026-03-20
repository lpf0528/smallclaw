import os
from typing import Any
from .feishu import FeishuChannel


class ChannelService:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config

        self.is_running = False

    async def start(self):
        if self.is_running:
            return

        await self._start_channel('feishu', {
            'app_id': os.getenv('FEISHU_APP_ID'),
            'app_secret': os.getenv('FEISHU_APP_SECRET'),
        })

        self._running = True
        print("ChannelService start done")

    async def _start_channel(self, name: str, config: dict[str, Any]) -> bool:
        channel = FeishuChannel(config)
        await channel.start()
        print(f"ChannelService startstart channel {name}")
        return True


async def start_channel_service():
    _channel_service = ChannelService()
    await _channel_service.start()
    return _channel_service
