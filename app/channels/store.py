import time
import threading
from typing import Any
from pathlib import Path
import tempfile
import json
from app.config.paths import get_paths


class ChannelStore:
    """通道存储

    {
            "<channel_name>:<chat_id>": {
                "thread_id": "<uuid>",
                "user_id": "<platform_user>",
                "created_at": 1700000000.0,
                "updated_at": 1700000000.0
            },
            ...
    }
    """

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            path = Path(get_paths().base_dir) / "channels" / "store.json"
        self._path = Path(path)

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data : dict[str, dict[str, Any]] = self._load()
        self._lock = threading.Lock()

    def _load(self) -> dict[str, dict[str, Any]]:
        """加载存储数据
        """
        if self._path.exists():
            return json.loads(self._path.read_text(encoding="utf-8"))
        return {}

    def _save(self) -> None:
        # 先写入临时文件
        # 再重命名临时文件到目标文件
        fd = tempfile.NamedTemporaryFile(mode="w", dir=self._path.parent, suffix='.temp', delete=False)
        try:
            # 写入临时文件
            json.dump(self._data, fd, indent=2)
            fd.close()
            # 重命名临时文件到目标文件
            Path(fd.name).rename(self._path)
        except BaseException:
            fd.close()
            # 删除临时文件
            Path(fd.name).unlink(missing_ok=True)

    @staticmethod
    def _key(channel_name: str, chat_id: str, topic_id: str | None = None) -> str:
        """生成存储键
        """
        if topic_id is None:
            return f"{channel_name}:{chat_id}"
        return f"{channel_name}:{chat_id}:{topic_id}"

    def set_thread_id(self, channel_name: str, chat_id: str, thread_id: str, *, topic_id: str | None = None,
                      user_id: str = ''):
        """设置线程ID
        """

        with self._lock:
            key = self._key(channel_name, chat_id, topic_id)
            existing = self._data.get(key, {})
            self._data[key] = {
                "thread_id": thread_id,
                "user_id": user_id,
                "created_at": existing.get('created_at', time.time()),
                "updated_at": time.time()
            }
            self._save()

    def get_thread_id(self, channel_name: str, chat_id: str, topic_id: str | None = None) -> str | None:
        """获取线程ID
        """
        return self._data.get(self._key(channel_name, chat_id, topic_id), {}).get('thread_id', None)
