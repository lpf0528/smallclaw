import time
from typing import Any
from collections.abc import Mapping
import logging
import asyncio
import json
from .message_bus import MessageBus, InboundMessage, InboundMessageType, OutboundMessage
from .store import ChannelStore
logger = logging.getLogger(__name__)

DEFAULT_LANGGRAPH_URL = "http://localhost:2024"
DEFAULT_GATEWAY_URL = "http://localhost:8001"
DEFAULT_ASSISTANT_ID = "lead_agent"
# 流更新最小间隔秒数
STREAM_UPDATE_MIN_INTERVAL_SECONDS = 0.35
# 默认的运行配置
DEFAULT_RUN_CONFIG: dict[str, Any] = {"recursion_limit": 100}
# 默认的运行上下文
DEFAULT_RUN_CONTEXT: dict[str, Any] = {
    "thinking_enabled": True,
    "is_plan_mode": False,
    "subagent_enabled": False,
}


def _merge_dicts(*layers: Any) -> dict[str, Any]:
    """合并多个字典，返回一个新的字典
    """
    merged = {}
    for layer in layers:
        if isinstance(layer, Mapping):
            merged.update(layer)
    return merged


def _extract_response_text(values: dict[str, Any] | list | None) -> str:
    """提取最后一条AI回复文本
    """
    if isinstance(values, list):
        messages = values
    elif isinstance(values, dict):
        messages = values.get('messages', [])
    else:
        return ''

    # 从后往前遍历，找到第一个AI回复
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue

        msg_type = msg.get('type', '')
        if msg_type == 'human':
            # 遇到human消息，说明已到达本轮的起点，终止遍历
            break

        if msg_type == 'tool' and msg.get('name') == 'ask_clarification':
            # 情况1：智能体通过 ask_clarification 工具，发起中断请求，需要用户澄清
            content = msg.get('content', '')
            if isinstance(content, str) and content:
                return content

        if msg_type == 'ai':
            content = msg.get('content', '')
            # 情况2：普通的AI回复，直接返回内容
            if isinstance(content, str) and content:
                return content
            # 情况3：AI回复是一个列表，需要提取最后一个元素
            if isinstance(content, list):
                parts = []
                for blcok in content:
                    if isinstance(blcok, dict) and blcok.get('type') == 'text':
                        parts.append(blcok.get('text', ''))
                    elif isinstance(blcok, str):
                        parts.append(blcok)
                return ''.join(parts)
    return ''


class ChannelManager:
    """通道管理器
    """

    def __init__(self, bus: MessageBus, store: ChannelStore, *,
                 langgraph_url: str = DEFAULT_LANGGRAPH_URL,
                 gateway_url : str = DEFAULT_GATEWAY_URL,
                 assistant_id: str = DEFAULT_ASSISTANT_ID,
                 max_concurrency: int = 5,
                 default_session: dict[str, Any] | None = None,
                 channel_sessions: dict[str, Any] | None = None) -> None:
        self.bus = bus
        self.store = store

        self._client = None  # langgraph 的api客户端
        self._langgraph_url = langgraph_url
        self._gateway_url = gateway_url
        self._assistant_id = assistant_id

        self._default_session = default_session or {}  # 默认的全局session配置
        self._channel_sessions = channel_sessions or {}  # 渠道单独的session配置

        self._max_concurrency = max_concurrency  # 最大的并发配置
        self._semaphore: asyncio.Semaphore | None = None  # 并发信号量
        self._running = False

    async def start(self):
        """启动调度循环
        """
        if self._running:
            return
        # 定义并发数限制
        self._semaphore = asyncio.Semaphore(self._max_concurrency)
        # 启动调度循环
        self._task = asyncio.create_task(self._dispatch_loop())
        self._running = True

    async def _dispatch_loop(self) -> None:
        """调度循环
        """
        logger.info("调度循环开始")
        while self._running:
            try:
                # 从队列中取出一个项目。如果队列为空，将等待直到有项目可用。
                msg = await asyncio.wait_for(self.bus.get_inbound(), timeout=1.0)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            # 创建一个任务来处理消息
            task = asyncio.create_task(self._handle_message(msg))
            task.add_done_callback(self._log_task_error)

    def _resolve_run_params(self, msg: InboundMessage, thread_id: str):
        """解析agent调用所需的参数
        :param msg: 入站消息
        :param thread_id: 线程ID
        :return: 运行参数
        """
        # 获取渠道层配置
        channel_layer = self._channel_sessions.get(msg.channel_name) or {}
        # 依次从渠道层、全局层、默认层获取assistant_id
        assistant_id = channel_layer.get('assistant_id') or self._default_session.get('assistant_id') or self._assistant_id
        run_config = _merge_dicts(DEFAULT_RUN_CONFIG, self._default_session.get('config', {}), channel_layer.get('config', {}))
        run_context = _merge_dicts(DEFAULT_RUN_CONTEXT, self._default_session.get('context', {}), channel_layer.get('context', {}))
        return assistant_id, run_config, run_context

    @staticmethod
    def _log_task_error(task: asyncio.Task) -> None:
        """记录任务错误
        """
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"[Manager] Task error: {exc}", exc_info=exc)

    async def _handle_message(self, msg: InboundMessage) -> None:
        """处理入站消息
        """
        logger.info(f"处理入站消息: {msg.text}")
        async with self._semaphore:
            try:
                if msg.msg_type == InboundMessageType.COMMAND:
                    # 处理命令消息
                    await self._handle_command(msg)
                else:
                    # 处理聊天消息
                    await self._handle_chat(msg)
            except Exception:
                await self._send_error(msg, '网络错误，请稍后重试')

    async def _handle_chat(self, msg: InboundMessage) -> None:
        """处理聊天消息 # TODO
        """
        logger.info(f"处理聊天消息: {msg.text}")
        thread_id = self.store.get_thread_id(msg.channel_name, msg.chat_id, msg.topic_id) or ''
        if not thread_id:
            thread_id = await self._create_thread(msg)

        client = self._get_client()

        # 解析出运行的参数
        assistant_id , run_config, run_context = self._resolve_run_params(msg, thread_id)
        if msg.channel_name == 'feishu':
            await self._handle_streaming_chat(
                client, msg,
                thread_id=thread_id,
                assistant_id=assistant_id,
                run_config=run_config,
                run_context=run_context
            )
            return

        # TODO
    async def _handle_streaming_chat(self, client,
                                     msg: InboundMessage,
                                     thread_id: str, assistant_id: str,
                                     run_config: dict[str, Any],
                                     run_context: dict[str, Any],
                                     ):
        """处理飞书频道的流式聊天
        1、订阅两种流式事件：
            - message-tuple: 逐 token 输出
            - values: 图状态快照（每次节点完成后的完整状态）
        """
        # 最后一次values事件的完整图状态（用于finally提取最终的响应）
        last_values: dict[str, Any] | list | None = None
        # 按消息ID索引的文本缓冲区字典
        # streamed_buffers: dict[str, str] = {}
        # 当前正在流式输出的消息ID
        # current_message_id: str | None = None
        # 最新的文本
        latest_text = ''
        # 上次推送的文本
        last_published_text = ''
        # 上次推送的事件戳（用于限速）
        last_publish_at = 0.0
        stream_error: BaseException | None = None

        logger.info(f"[Manager] 开始调用 runs.stream(thread_id={thread_id}, text={msg.text[:20]})")
        try:
            async for chunk in client.runs.stream(
                thread_id, assistant_id,
                input={
                    'messages': [{
                        'role': 'user',
                        'content': msg.text
                    }]
                },
                config=run_config,
                context=run_context,
                stream_mode=['messages-tuple', 'values']
            ):
                event = getattr(chunk, 'event', '')
                data = getattr(chunk, 'data', None)
                if event == 'messages-tuple':
                    # TODO
                    latest_text = "[Manager] 收到 messages-tuple 消息: TODO"
                elif event == 'values' and isinstance(data, (dict, list)):
                    last_values = data
                    # 从 values 中提取响应文本
                    snapshot_text = _extract_response_text(data)
                    if snapshot_text:
                        latest_text = snapshot_text
                else:  # event: metadata, messages
                    pass

                if not latest_text or latest_text == last_published_text:
                    # 忽略重复文本
                    continue

                now = time.monotonic()
                if last_published_text and now - last_publish_at < STREAM_UPDATE_MIN_INTERVAL_SECONDS:
                    # 流更新最小间隔秒数
                    continue

                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel_name=msg.channel_name,
                        chat_id=msg.chat_id,
                        thread_id=thread_id,
                        text=latest_text,
                        is_final=False,  # 标记为中间状态，非最终响应
                        thread_ts=msg.thread_ts
                    )
                )

                last_published_text = latest_text
                last_publish_at = now

        except Exception as exc:
            stream_error = exc
            logger.exception(f"[Manager] 处理流式聊天时出错: {exc}")
        finally:
            # 无论是否出错，都需要发送最终消息
            result = last_values if last_values else {
                'messages': [{'type': 'ai', 'content': latest_text}]
            }
            response_text = _extract_response_text(result)
            if not response_text:
                if stream_error:
                    response_text = "一个错误，请稍后重试"
                else:
                    response_text = latest_text or "(agent 没有响应)"
            # 推送最终消息
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel_name=msg.channel_name,
                    chat_id=msg.chat_id,
                    thread_id=thread_id,
                    text=response_text,
                    is_final=True,
                    thread_ts=msg.thread_ts
                )
            )

    async def _create_thread(self, msg: InboundMessage) -> str:
        client = self._get_client()
        thread = await client.threads.create()
        thread_id = thread['thread_id']
        self.store.set_thread_id(
            channel_name=msg.channel_name,
            chat_id=msg.chat_id,
            thread_id=thread_id,
            topic_id=msg.topic_id,
            user_id=msg.user_id
        )
        return thread_id

    async def _handle_command(self, msg: InboundMessage) -> None:
        """处理命令消息 
        """
        text = msg.text.strip()
        parts = text.split(maxsplit=1)
        command = parts[0].lower().lstrip('/')
        if command == 'new':
            # 创建新线程
            await self._create_thread(msg)
            reply = '已开启新的会话。'
        elif command == 'models':
            reply = await self._fetch_gateway('/api/models', 'models')
        else:
            reply = f'未知命令: {command}，请输入 /help 查看有效的命令'

        logger.info(f"处理命令消息: {command}")
        outbound = OutboundMessage(
            channel_name=msg.channel_name,
            chat_id=msg.chat_id,
            thread_id=self.store.get_thread_id(msg.channel_name, msg.chat_id, msg.topic_id) or '',
            text=reply,
            thread_ts=msg.thread_ts
        )
        logger.info(f"发布出站消息: {outbound}")
        await self.bus.publish_outbound(outbound)

    async def _fetch_gateway(self, path: str, kind: str) -> str:
        """从网关获取模型列表
        """
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self._gateway_url + path, timeout=10)
                response.raise_for_status()

                data = response.json()
                if kind == 'models':
                    names = [m['name'] for m in data.get('models', [])]
                    return f"当前可用模型: {", ".join(names)}" if names else '无模型'
                return json.dumps(data, ensure_ascii=False)

        except httpx.HTTPError as e:
            logger.error(f"获取模型列表失败: {e}")
            return f"获取模型列表失败: {e}"

    async def _send_error(self, msg: InboundMessage, error: str) -> None:
        """发送错误消息  # TODO
        """
        logger.error(f"发送错误消息: {error}")

    def _get_client(self):
        """获取langgraph客户端
        """
        if self._client is None:
            from langgraph_sdk import get_client
            self._client = get_client(url=self._langgraph_url)
        return self._client
