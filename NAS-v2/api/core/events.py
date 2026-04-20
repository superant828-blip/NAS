"""事件通知系统 - WebSocket支持"""
from typing import Dict, List, Callable
from fastapi import WebSocket
import json
from datetime import datetime
from enum import Enum

class EventType(str, Enum):
    FILE_UPLOAD = "file:upload"
    FILE_DELETE = "file:delete"
    JOB_PROGRESS = "job:progress"
    JOB_COMPLETE = "job:complete"
    STORAGE_ALERT = "storage:alert"
    USER_LOGIN = "user:login"
    SHARE_ACCESS = "share:access"

class EventManager:
    """事件管理器"""
    
    def __init__(self):
        self._connections: List[WebSocket] = []
        self._handlers: Dict[EventType, List[Callable]] = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self._connections:
            self._connections.remove(websocket)
    
    async def broadcast(self, event_type: EventType, data: dict):
        message = {
            "type": event_type.value,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        for conn in self._connections:
            try:
                await conn.send_json(message)
            except:
                self._connections.remove(conn)
    
    def on(self, event_type: EventType, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

event_manager = EventManager()