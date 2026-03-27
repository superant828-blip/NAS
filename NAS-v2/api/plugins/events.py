"""事件通知 WebSocket 端点"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional
import json
import logging

from api.core.events import event_manager, EventType

logger = logging.getLogger(__name__)
router = APIRouter(tags=["events"])

@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """
    WebSocket 事件流端点
    支持实时推送：
    - 文件上传进度 (file:upload)
    - 文件删除通知 (file:delete)
    - 任务进度 (job:progress)
    - 任务完成 (job:complete)
    - 存储警报 (storage:alert)
    - 用户登录 (user:login)
    - 分享访问 (share:access)
    """
    await event_manager.connect(websocket)
    logger.info("WebSocket客户端已连接")
    
    try:
        while True:
            # 保持连接，可以接收客户端消息
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # 处理客户端发送的消息（可选）
                logger.debug(f"收到WebSocket消息: {message}")
            except json.JSONDecodeError:
                logger.warning(f"收到无效的JSON消息: {data}")
    except WebSocketDisconnect:
        event_manager.disconnect(websocket)
        logger.info("WebSocket客户端已断开连接")
    except Exception as e:
        event_manager.disconnect(websocket)
        logger.error(f"WebSocket错误: {e}")


@router.get("/events/status")
async def get_events_status():
    """获取事件系统状态"""
    return {
        "connected_clients": len(event_manager._connections),
        "event_types": [e.value for e in EventType],
        "status": "active"
    }


async def notify_file_upload(user_id: int, file_name: str, progress: int, total: int):
    """通知文件上传进度"""
    await event_manager.broadcast(EventType.FILE_UPLOAD, {
        "user_id": user_id,
        "file_name": file_name,
        "progress": progress,
        "total": total,
        "percentage": round(progress / total * 100, 2) if total > 0 else 0
    })


async def notify_file_delete(user_id: int, file_name: str, file_path: str):
    """通知文件删除"""
    await event_manager.broadcast(EventType.FILE_DELETE, {
        "user_id": user_id,
        "file_name": file_name,
        "file_path": file_path
    })


async def notify_job_progress(job_id: str, progress: int, status: str):
    """通知任务进度"""
    await event_manager.broadcast(EventType.JOB_PROGRESS, {
        "job_id": job_id,
        "progress": progress,
        "status": status
    })


async def notify_job_complete(job_id: str, result: dict):
    """通知任务完成"""
    await event_manager.broadcast(EventType.JOB_COMPLETE, {
        "job_id": job_id,
        "result": result
    })


async def notify_storage_alert(alert_type: str, used_percent: float, message: str):
    """通知存储警报"""
    await event_manager.broadcast(EventType.STORAGE_ALERT, {
        "alert_type": alert_type,
        "used_percent": used_percent,
        "message": message
    })