import logging
import asyncio
from pathlib import Path
import time
from typing import Any, Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


class InboundMessageType(StrEnum):

    CHAT = "chat"
    COMMAND = "command"


@dataclass
class InboundMessage:
    """入站消息
    """
    channel_name: str
    chat_id: str
    user_id: str
    text: str
    msg_type: InboundMessageType = InboundMessageType.CHAT
    # 可选的平台线程标识符（消息ID）。
    thread_ts: str | None = None
    topic_id: str | None = None
    files: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class ResolvedAttachment:
    """已解析的文件附件
    """

    virtual_path: str
    actual_path: Path
    filename: str
    mime_type: str
    size: int
    is_image: bool


@dataclass
class OutboundMessage:
    """出站消息
    """
    channel_name: str
    chat_id: str
    # DeerFlow 生成此响应的线程 ID。
    thread_id: str
    text: str
    artifacts: list[str] = field(default_factory=list)
    # 任意附加数据。如文件附件等。
    attachments: list[ResolvedAttachment] = field(default_factory=list)
    is_final: bool = True
    # 消息ID
    thread_ts: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


OutboundCallback = Callable[[OutboundMessage], Coroutine[Any, Any, None]]


class MessageBus:
    """消息总线
    """

    def __init__(self) -> None:
        # 入站消息队列：asyncio.Queue：异步环境下实现生产者-消费者模式的队列
        self._inbound_queue: asyncio.Queue[InboundMessage] = asyncio.Queue()
        # 出站消息回调列表
        self._outbound_listeners: list[OutboundCallback] = []

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """发布入站消息
        """
        logger.info(f"发布入站消息: {msg}")
        await self._inbound_queue.put(msg)

    def subscribe_outbound(self, callback: OutboundCallback) -> None:
        """订阅出站消息回调
        """
        self._outbound_listeners.append(callback)

    async def get_inbound(self) -> InboundMessage:
        """从队列中取出一个项目。如果队列为空，将等待直到有项目可用。
        """
        return await self._inbound_queue.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """向所有注册的回调发送一条出站消息。
        """
        logger.info(f"发布出站消息: {self._outbound_listeners}")
        for callback in self._outbound_listeners:
            await callback(msg)
