import asyncio
import logging

from abc import ABC
import json
import threading
from typing import Any

from .message_bus import InboundMessage, InboundMessageType, MessageBus, OutboundMessage
logger = logging.getLogger(__name__)


class FeishuChannel(ABC):
    """
    线程模型：
    ┌─────────────────────┐       ┌──────────────────────────┐
    │   主线程             │       │   子线程（_thread）        │
    │  asyncio event loop │       │   独立 asyncio event loop │
    │  （_main_loop）      │       │   用于运行飞书 WS 客户端    │
    └─────────┬───────────┘       └────────────┬─────────────┘
              │  run_coroutine_threadsafe()    │  _on_message() 回调
              │◄───────────────────────────────┘
              │  将协程安全地提交到主线程 loop 执行

    **三层并发模型**

    主线程 (asyncio _main_loop)
    ├── start() 启动子线程
    ├── _prepare_inbound()   ← 由子线程跨线程提交
    │     ├── _add_reaction()  [Task, 并发]
    │     └── _add_message()   [Task, 并发]
    │           └── asyncio.to_thread() → 线程池执行阻塞 SDK 调用

    子线程 (_thread, 独立 loop)
    └── 飞书 WS 客户端（阻塞监听）
            └── _on_message() → run_coroutine_threadsafe() → 主线程 loop
    """

    def __init__(self, bus: MessageBus, config: dict[str, Any]) -> None:
        self.bus = bus
        self.name = 'feishu'
        # 保存主线程的事件循环引用，供子线程跨线程提交协程使用
        self._main_loop: asyncio.AbstractEventLoop | None = None
        # 运行飞书 WebSocket 客户端的子线程
        self._thread: threading.Thread | None = None
        # 保存所有并发任务的引用，用于取消
        self._background_tasks: set[asyncio.Task] = set()
        # 回复的卡片消息
        self._running_card_ids: dict[str, str] = {}
        self._running_card_tasks: dict[str, asyncio.Task.Task] = {}

        self.config = config
        self._running = False

        self._api_client = None
        self._CreateMessageReactionRequest = None
        self._CreateMessageReactionRequestBody = None
        self._CreateMessageRequest = None
        self._CreateMessageRequestBody = None
        self._ReplyMessageRequest = None
        self._ReplyMessageRequestBody = None
        self._PatchMessageRequest = None
        self._PatchMessageRequestBody = None
        self._Emoji = None

    @property
    def is_running(self) -> bool:
        return self._running

    # # -- lifecycle ---------------------------------------------------------
    async def start(self) -> None:
        """
        启动飞书 WebSocket 客户端，监听消息事件
        """
        # 幂等检查
        if self.is_running:
            return
        try:
            import lark_oapi as lark
            from lark_oapi.api.im.v1 import (
                CreateMessageReactionRequest, CreateMessageReactionRequestBody, Emoji, CreateMessageRequest, CreateMessageRequestBody,
                ReplyMessageRequest, ReplyMessageRequestBody, PatchMessageRequest, PatchMessageRequestBody
            )
        except ImportError as e:
            print(f"FeishuChannel start error: {e}")
            return

        self._CreateMessageReactionRequest = CreateMessageReactionRequest
        self._CreateMessageReactionRequestBody = CreateMessageReactionRequestBody
        self._CreateMessageRequest = CreateMessageRequest
        self._CreateMessageRequestBody = CreateMessageRequestBody
        self._ReplyMessageRequest = ReplyMessageRequest
        self._ReplyMessageRequestBody = ReplyMessageRequestBody
        self._PatchMessageRequest = PatchMessageRequest
        self._PatchMessageRequestBody = PatchMessageRequestBody
        self._Emoji = Emoji

        self._lark = lark

        app_id = self.config['app_id']
        app_secret = self.config['app_secret']

        # 创建一个 API Client
        self._api_client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
        # 2、捕获当前主线程的时间循环，用于子线程跨线程提交协程使用
        # 子线程无法直接使用该 loop（asyncio 不是线程安全的），
        # 但可通过 run_coroutine_threadsafe() 向它安全地提交协程。
        self._main_loop = asyncio.get_event_loop()

        self._running = True
        # 订阅出站消息回调
        self.bus.subscribe_outbound(self._on_outbound)

        # 3、启动守护子线程，在子线程中运行WebSocket 客户端
        # daemon=True：主进程退出时，该子线程会自动被销毁，无需手动清理。
        self._thread = threading.Thread(target=self._run_ws, args=(app_id, app_secret), daemon=True)
        self._thread.start()

    def _run_ws(self, app_id: str, app_secret: str) -> None:
        """
        在子线程中启动飞书WebSocket 客户端，持续监听消息事件
        为啥需要独立的子线程：
        - 飞书ws客户端的start()是一个阻塞调用（持续运行直到断开），不能直接跑在主线程，否则会阻塞整个应用。

        为什么需要在子线程中创建事件循环：
        - asyncio的事件循环是线程绑定的，每个线程只有一个事件循环
        - 主线程的事件循环已经被占用，子线程必须自建
        - 飞书SDK内部依赖asyncio,必须在有事件循环的环境中运行。
        """

        # 为当前子线程创建一个全新的事件循环
        # 在子线程里运行异步代码，通常“不能”直接依赖主线程的事件循环，所以会手动创建一个新的 loop。
        loop = asyncio.new_event_loop()
        # 将该 loop 设置为当前线程的默认事件循环。
        # 这样在本线程内调用 asyncio.get_event_loop() 时，
        # 返回的是这个新创建的 loop，而不是主线程的 loop。
        asyncio.set_event_loop(loop)

        try:

            import lark_oapi as lark
            import lark_oapi.ws.client as _ws_client_mod
            # 关键 Hack：将飞书 WS SDK 模块级别的 loop 变量替换为当前子线程的 loop。
            # 原因：SDK 内部在模块层面引用了 loop，若不替换，
            # 它可能会拿到主线程的 uvloop（已在运行中），
            # 导致 "This event loop is already running" 等错误。
            _ws_client_mod.loop = loop

            # 构建事件分发器：注册消息接收事件的处理回调。
            # - register_p2_im_message_receive_v1：监听「接收到用户发来的 IM 消息」事件，调用 self._on_message
            # https://open.larksuite.com/document/ukTMukTMukTM/uYDNxYjL2QTM24iN0EjN/event-subscription-configure-/use-websocket#1c227849
            event_handler = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(self._on_message).build()

            # 构建 WebSocket 客户端并启动（阻塞，持续监听飞书推送的事件）
            ws_client = lark.ws.Client(
                app_id=app_id,
                app_secret=app_secret,
                event_handler=event_handler,
                log_level=lark.LogLevel.INFO,
            )
            ws_client.start()  # 阻塞，直到连接断开或进程退出
        except ImportError as e:
            print(f"FeishuChannel _run_ws error: {e}")

    def _on_message(self, event) -> None:
        """飞书 WS 客户端的消息事件回调（运行在子线程中）。
        此方法由飞书 SDK 在子线程的事件循环中同步调用，
        不能直接 await 协程，也不能直接操作主线程的 asyncio 资源。
        必须通过 run_coroutine_threadsafe() 将任务安全地提交给主线程的事件循环。
        """

        message = event.event.message
        # 当该消息是在飞书线程中对某条消息的回复时，会设置 `root_id`。
        root_id = getattr(message, 'root_id', None)
        msg_id = message.message_id
        sender_id = event.event.sender.sender_id.open_id

        content = json.loads(message.content)
        text = content.get("text", "").strip()
        if text.startswith("/"):
            msg_type = InboundMessageType.COMMAND
        else:
            msg_type = InboundMessageType.CHAT

        inbound = InboundMessage(
            channel_name=self.name,
            chat_id=message.chat_id,  # 消息所在的群/会话 ID，用于后续回复消息时指定目标
            user_id=sender_id,
            text=text,
            msg_type=msg_type,
            thread_ts=msg_id,
            metadata={"message_id": msg_id, "root_id": root_id},
        )
        inbound.topic_id = root_id or msg_id

        if self._main_loop and self._main_loop.is_running():
            # 跨线程安全地将协程提交给主线程的事件循环执行。
            # 这是从非 asyncio 线程调用异步代码的标准做法：
            # - asyncio.run_coroutine_threadsafe() 是线程安全的
            # - 返回一个 concurrent.futures.Future（非 asyncio.Future）
            fut = asyncio.run_coroutine_threadsafe(
                self._prepare_inbound(msg_id, inbound),
                self._main_loop,
            )
            # 为 Future 添加完成回调（无论成功/失败/取消均会触发），用于日志记录。
            fut.add_done_callback(lambda f, mid=msg_id: print(f'处理入站消息 {mid} 完成'))

    async def _prepare_inbound(self, msg_id: str, inbound: InboundMessage) -> None:
        """在主线程事件循环中并发处理收到的入站消息：
        """
        # create_task() 将协程包装为 Task 并立即调度，不等待其完成就继续往下执行。
        # 1、发送一个 "OK" 反应，确认消息已收到。
        rection_task = asyncio.create_task(self._add_reaction(msg_id, 'OK'))
        self._track_background_task(rection_task, name="add_reaction", msg_id=msg_id)
        # 2、开启卡片消息回复任务
        self._ensure_running_card_started(msg_id)
        await self.bus.publish_inbound(inbound)

    def _ensure_running_card_started(self, msg_id: str, text: str = "Working on it...") -> None:
        """开启卡片消息回复任务
        """
        # 1、检查是否已存在卡片消息 ID
        running_card_id = self._running_card_ids.get(msg_id, None)
        if running_card_id:
            # 已存在卡片消息 ID，无需重复回复。
            return None

        # 2、检查是否已存在卡片消息回复任务
        running_card_task = self._running_card_tasks.get(msg_id)
        if running_card_task:
            return running_card_task

        running_card_task = asyncio.create_task(
            self._create_running_card(msg_id, text)
        )

        self._running_card_tasks[msg_id] = running_card_task
        running_card_task.add_done_callback(lambda task, mid=msg_id: self._finalize_running_card_task(task, mid))
        return running_card_task

    async def _create_running_card(self, msg_id: str, text: str):
        #
        running_card_id = await self._reply_card(msg_id, text)
        if running_card_id:
            self._running_card_ids[msg_id] = running_card_id
        return running_card_id

    def _finalize_running_card_task(self, task: asyncio.Task, msg_id: str) -> None:
        """卡片消息回复完成
        """
        if self._running_card_tasks.get(msg_id) is task:
            self._running_card_tasks.pop(msg_id, None)
        self._log_task_error(task, 'create_running_card', msg_id)

    async def _reply_card(self, msg_id: str, text: str) -> str | None:
        """回复卡片消息，返回回复消息 ID。
        https: // open.feishu.cn / document / server - docs / im - v1 / message / reply?appId = cli_a93e6e5177b99cd3
        """
        content = self._build_card_content(text)
        request = self._ReplyMessageRequest.builder().message_id(msg_id) \
            .request_body(self._ReplyMessageRequestBody.builder()
                          .msg_type("interactive")  # 卡片
                          .content(content)
                          .reply_in_thread(True)  # true 时将以话题形式回复。
                          .build()) \
            .build()

        response = await asyncio.to_thread(self._api_client.im.v1.message.reply, request)
        response_data = getattr(response, "data", None)
        return getattr(response_data, "message_id", None)

    @staticmethod
    def _build_card_content(text: str) -> str:
        """创建卡片消息内容
        https: // open.feishu.cn / document / feishu - cards / card - json - structure
        """
        return json.dumps({
            "config": {"wide_screen_mode": True, "update_multi": True},
            "elements": [{"tag": "markdown", "content": text}],
        })

    def _track_background_task(self, task: asyncio.Task, *, name: str, msg_id: str) -> None:
        """追踪后台任务
        """
        # 记录任务，用于后续完成、取消时释放资源。
        self._background_tasks.add(task)
        # 为任务添加完成回调
        task.add_done_callback(lambda done_task, name=name, mid=msg_id: self._finalize_background_task(done_task, name, mid))

    def _finalize_background_task(self, task: asyncio.Task, name: str, msg_id: str):
        """后台任务完成回调
        """
        # 任务完成时，从记录中移除它，释放资源。
        self._background_tasks.discard(task)  # remove： 会抛出异常，discard： 不会抛出异常。
        self._log_task_error(task, name, msg_id)

    @staticmethod
    def _log_task_error(task: asyncio.Task, name: str, msg_id: str):
        """记录后台任务执行的错误日志
        """
        try:
            exc = task.exception()
            if exc:
                logger.error(f"[FeishuChannel] 任务 {name} {msg_id} 执行异常 : {exc}")
        except asyncio.CancelledError:
            logger.info(f"[FeishuChannel] 任务 {name} {msg_id} 已取消")
        except Exception:
            pass

    async def _add_reaction(self, msg_id: str, emoji_type: str = 'THUMBSUP') -> None:
        """通过飞书 REST API 给指定消息添加 Emoji 表情回应。
        https://open.feishu.cn/document/server-docs/im-v1/message/create?appId=cli_a93e6e5177b99cd3
        """
        request = self._CreateMessageReactionRequest.builder().message_id(msg_id).request_body(
            self._CreateMessageReactionRequestBody.builder().reaction_type(
                self._Emoji.builder().emoji_type(emoji_type).build()
            ).build()).build()
        # 飞书 SDK 的 API 调用（_api_client.im.v1.message_reaction.create）是同步阻塞的。
        # 直接在协程中调用会阻塞整个事件循环，导致其他任务无法执行。
        # asyncio.to_thread() 将其放入线程池执行，事件循环可继续处理其他任务。
        await asyncio.to_thread(self._api_client.im.v1.message_reaction.create, request)

    async def _on_outbound(self, msg: OutboundMessage) -> None:
        """处理出站消息回调
        """
        if msg.channel_name == self.name:
            try:
                await self.send(msg)
            except Exception:
                pass

            # 其他任意附加数据， 例如：文件 TODO
            # for attachment in msg.attachments:
            #     try:
            #         success = await self.send_file(msg, attachment)
            #         if not success:
            #             pass
            #     except Exception:
            #         pass

    async def send(self, msg: OutboundMessage, *, _max_retries=3) -> None:
        if not self._api_client:
            return

        last_exc: Exception | None = None
        for attempt in range(_max_retries):
            try:
                await self._send_card_message(msg)
                return
            except Exception as exc:
                logger.error(f"[FeishuChannel] 发送卡片消息异常: {exc}", exc_info=exc)
                last_exc = exc
                if attempt < _max_retries - 1:
                    delay = 2**attempt
                    await asyncio.sleep(delay)
        raise last_exc

    async def _send_card_message(self, msg: OutboundMessage) -> None:
        msg_id = msg.thread_ts
        if msg_id:
            # 获取运行的卡片ID
            running_card_id = self._running_card_ids.get(msg_id)
            # awaited_running_card_task = False

            if not running_card_id:
                running_card_task = self._running_card_tasks.get(msg_id)
                if running_card_task:
                    # awaited_running_card_task = True
                    running_card_id = await running_card_task

            # 存在卡片ID，更新卡片内容
            if running_card_id:
                try:
                    await self._update_card(running_card_id, msg.text)
                except Exception:
                    pass
            elif msg.is_final:
                # 流式输出：最后一条消息，创建卡片 TODO
                await self._reply_card(msg_id, msg.text)

            if msg.is_final:
                self._running_card_ids.pop(msg_id, None)
                await self._add_reaction(msg_id, "DONE")
            return

        # await self._create_card(msg)
    async def _update_card(self, msg_id: str, text: str):
        """更新卡片内容
        """
        content = self._build_card_content(text)
        request = self._PatchMessageRequest.builder().message_id(msg_id).request_body(
            self._PatchMessageRequestBody.builder().content(content).build()
        ).build()
        await asyncio.to_thread(self._api_client.im.v1.message.patch, request)
