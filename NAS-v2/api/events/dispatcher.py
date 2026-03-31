"""
事件分发器
参考 Claude Code 事件驱动架构设计
"""
from typing import Callable, Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """事件类型"""
    # 文件事件
    FILE_CREATED = "file.created"
    FILE_DELETED = "file.deleted"
    FILE_MODIFIED = "file.modified"
    FILE_READ = "file.read"
    
    # 用户事件
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_REGISTERED = "user.registered"
    
    # 任务事件
    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"
    
    # 存储事件
    ZFS_SNAPSHOT_CREATED = "zfs.snapshot.created"
    ZFS_SNAPSHOT_DELETED = "zfs.snapshot.deleted"
    ZFS_POOL_STATUS = "zfs.pool.status"
    
    # 共享事件
    SHARE_CREATED = "share.created"
    SHARE_DELETED = "share.deleted"
    
    # 系统事件
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"


@dataclass
class Event:
    """事件数据"""
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "unknown"
    user_id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "user_id": self.user_id
        }


class EventHandler:
    """事件处理器"""
    
    def __init__(self, handler: Callable, event_types: List[EventType] = None):
        self.handler = handler
        self.event_types = event_types or []
        self.call_count = 0
        self.error_count = 0
    
    async def handle(self, event: Event):
        """处理事件"""
        try:
            await self.handler(event)
            self.call_count += 1
        except Exception as e:
            self.error_count += 1
            logger.error(f"Event handler error: {e}")


class EventDispatcher:
    """
    事件分发器
    
    功能：
    - 事件订阅/取消订阅
    - 同步/异步事件分发
    - 事件过滤
    - 错误处理
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers: Dict[EventType, List[EventHandler]] = {}
            cls._instance._event_history: List[Event] = []
            cls._instance._max_history = 1000
        return cls._instance
    
    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
    
    def on(
        self,
        event_type: EventType,
        handler: Callable[[Event], Any]
    ) -> EventHandler:
        """
        订阅事件
        
        Usage:
            @dispatcher.on(EventType.FILE_CREATED)
            async def handle_file_created(event):
                print(f"File created: {event.data}")
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        event_handler = EventHandler(handler, [event_type])
        self._handlers[event_type].append(event_handler)
        
        logger.info(f"Registered handler for {event_type.value}")
        
        return event_handler
    
    def on_multiple(
        self,
        event_types: List[EventType],
        handler: Callable[[Event], Any]
    ) -> EventHandler:
        """订阅多个事件类型"""
        event_handler = EventHandler(handler, event_types)
        
        for event_type in event_types:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(event_handler)
        
        return event_handler
    
    def off(self, event_type: EventType, handler: Callable = None):
        """取消订阅"""
        if event_type not in self._handlers:
            return
        
        if handler is None:
            # 移除该类型所有处理器
            del self._handlers[event_type]
        else:
            # 移除指定处理器
            self._handlers[event_type] = [
                h for h in self._handlers[event_type]
                if h.handler != handler
            ]
    
    async def dispatch(self, event: Event):
        """分发事件"""
        # 记录历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        # 获取处理器
        handlers = self._handlers.get(event.type, [])
        
        if not handlers:
            return
        
        # 并发执行所有处理器
        import asyncio
        
        tasks = []
        for handler in handlers:
            tasks.append(self._safe_handle(handler, event))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_handle(self, handler: EventHandler, event: Event):
        """安全处理事件"""
        try:
            result = handler.handle(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Event handler error: {e}")
    
    def emit(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        source: str = "system",
        user_id: int = None
    ):
        """发送事件（同步包装）"""
        event = Event(
            type=event_type,
            data=data,
            source=source,
            user_id=user_id
        )
        
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.dispatch(event))
            else:
                loop.run_until_complete(self.dispatch(event))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.dispatch(event))
    
    def get_history(
        self,
        event_type: EventType = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取事件历史"""
        history = self._event_history
        
        if event_type:
            history = [e for e in history if e.type == event_type]
        
        return [e.to_dict() for e in history[-limit:]]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "total_events": len(self._event_history),
            "handlers": {}
        }
        
        for event_type, handlers in self._handlers.items():
            stats["handlers"][event_type.value] = len(handlers)
        
        return stats


# 全局实例
_dispatcher = EventDispatcher()


def get_event_dispatcher() -> EventDispatcher:
    """获取事件分发器实例"""
    return _dispatcher