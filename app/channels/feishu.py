import asyncio

from abc import ABC
import json
import threading
from typing import Any


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

    def __init__(self, config: dict[str, Any]) -> None:
        self.name = 'feishu'
        # 保存主线程的事件循环引用，供子线程跨线程提交协程使用
        self._main_loop: asyncio.AbstractEventLoop | None = None
        # 运行飞书 WebSocket 客户端的子线程
        self._thread: threading.Thread | None = None

        self.config = config
        self._running = False

        self._api_client = None
        self._CreateMessageReactionRequest = None
        self._CreateMessageReactionRequestBody = None
        self._CreateMessageRequest = None
        self._CreateMessageRequestBody = None
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

        if self.is_running:
            return

        try:
            import lark_oapi as lark
            from lark_oapi.api.im.v1 import CreateMessageReactionRequest, CreateMessageReactionRequestBody, Emoji, CreateMessageRequest, CreateMessageRequestBody
        except ImportError as e:
            print(f"FeishuChannel start error: {e}")
            return

        self._CreateMessageReactionRequest = CreateMessageReactionRequest
        self._CreateMessageReactionRequestBody = CreateMessageReactionRequestBody
        self._CreateMessageRequest = CreateMessageRequest
        self._CreateMessageRequestBody = CreateMessageRequestBody
        self._Emoji = Emoji

        self._lark = lark

        app_id = self.config['app_id']
        app_secret = self.config['app_secret']
        # 2、捕获当前主线程的时间循环，用于子线程跨线程提交协程使用
        # 子线程无法直接使用该 loop（asyncio 不是线程安全的），
        # 但可通过 run_coroutine_threadsafe() 向它安全地提交协程。
        self._main_loop = asyncio.get_event_loop()

        # 创建一个 API Client
        self._api_client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
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
        content = json.loads(message.content)
        print(f'content: {content}')

        robot_id = getattr(message, 'robot_id', None)
        msg_id = message.message_id
        msg_id = robot_id or msg_id
        # 消息所在的群/会话 ID，用于后续回复消息时指定目标
        chat_id = message.chat_id

        # 跨线程安全地将协程提交给主线程的事件循环执行。
        # 这是从非 asyncio 线程调用异步代码的标准做法：
        # - asyncio.run_coroutine_threadsafe() 是线程安全的
        # - 返回一个 concurrent.futures.Future（非 asyncio.Future）
        fut = asyncio.run_coroutine_threadsafe(
            self._prepare_inbound(msg_id, chat_id, {}),
            self._main_loop,
        )
        # 为 Future 添加完成回调（无论成功/失败/取消均会触发），用于日志记录。
        fut.add_done_callback(lambda f, mid=msg_id: print(f'prepare inbound {mid} done'))

    async def _prepare_inbound(self, msg_id: str, content: dict[str, Any]) -> None:
        """在主线程事件循环中并发处理收到的消息：
        """
        # create_task() 将协程包装为 Task 并立即调度，不等待其完成就继续往下执行。
        rection_task = asyncio.create_task(self._add_reaction(msg_id, 'OK'))
        rection_task.add_done_callback(lambda f: print(f'add reaction to {msg_id}'))

    async def _add_reaction(self, msg_id: str, emoji_type: str = 'THUMBSUP') -> None:
        """通过飞书 REST API 给指定消息添加 Emoji 表情回应。
        https://open.feishu.cn/document/server-docs/im-v1/message-reaction/create?appId=cli_a93e6e5177b99cd3
        """
        request = self._CreateMessageReactionRequest.builder().message_id(msg_id).request_body(
            self._CreateMessageReactionRequestBody.builder().reaction_type(
                self._Emoji.builder().emoji_type(emoji_type).build()
            ).build()).build()
        # 飞书 SDK 的 API 调用（_api_client.im.v1.message_reaction.create）是同步阻塞的。
        # 直接在协程中调用会阻塞整个事件循环，导致其他任务无法执行。
        # asyncio.to_thread() 将其放入线程池执行，事件循环可继续处理其他任务。
        await asyncio.to_thread(self._api_client.im.v1.message_reaction.create, request)
