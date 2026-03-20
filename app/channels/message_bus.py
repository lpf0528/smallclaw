import time
from typing import Any
from dataclasses import dataclass, field
from enum import StrEnum


class InboundMessageType(StrEnum):

    CHAT = "chat"
    COMMAND = "command"


@dataclass
class InboundMessage:
    channel_name: str
    chat_id: str
    user_id: str
    text: str
    msg_type: InboundMessageType = InboundMessageType.CHAT
    thread_ts: str | None = None
    topic_id: str | None = None
    files: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
