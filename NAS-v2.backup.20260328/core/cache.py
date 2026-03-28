"""
缓存模块 - API响应缓存
"""
import time
import hashlib
import json
from typing import Any, Optional, Callable
from functools import wraps
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    expires_at: float
    created_at: float = field(default_factory=time.time)


class SimpleCache:
    """简单内存缓存"""
    
    def __init__(self, default_ttl: int = 300):
        """
        初始化缓存
        
        Args:
            default_ttl: 默认过期时间(秒)
        """
        self._cache = {}
        self._lock = Lock()
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            # 检查过期
            if time.time() > entry.expires_at:
                del self._cache[key]
                return None
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        ttl = ttl if ttl is not None else self.default_ttl
        
        with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl,
                created_at=time.time()
            )
    
    def delete(self, key: str) -> None:
        """删除缓存"""
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self, pattern: Optional[str] = None) -> int:
        """清除缓存"""
        with self._lock:
            if pattern is None:
                count = len(self._cache)
                self._cache.clear()
                return count
            
            # 支持简单模式匹配
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)
    
    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        count = 0
        now = time.time()
        
        with self._lock:
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if now > entry.expires_at
            ]
            for key in keys_to_delete:
                del self._cache[key]
                count += 1
        
        return count
    
    def get_stats(self) -> dict:
        """获取缓存统计"""
        with self._lock:
            total = len(self._cache)
            now = time.time()
            expired = sum(1 for e in self._cache.values() if now > e.expires_at)
            
            return {
                "total": total,
                "active": total - expired,
                "expired": expired
            }


# 全局缓存实例
api_cache = SimpleCache(default_ttl=300)


def cache_key(*args, **kwargs) -> str:
    """生成缓存键"""
    key_data = {
        "args": args,
        "kwargs": sorted(kwargs.items())
    }
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    缓存装饰器
    
    Args:
        ttl: 缓存时间(秒)
        key_prefix: 缓存键前缀
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 生成缓存键
            ck = f"{key_prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # 尝试从缓存获取
            cached_value = api_cache.get(ck)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 存入缓存
            api_cache.set(ck, result, ttl)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 生成缓存键
            ck = f"{key_prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # 尝试从缓存获取
            cached_value = api_cache.get(ck)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            api_cache.set(ck, result, ttl)
            
            return result
        
        # 根据函数类型选择包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def invalidate_cache(pattern: str = None) -> int:
    """
    清除缓存
    
    Args:
        pattern: 缓存键匹配模式
    """
    return api_cache.clear(pattern)


# 定时清理任务
def start_cache_cleanup(interval: int = 60):
    """启动缓存清理任务"""
    import threading
    
    def cleanup():
        while True:
            time.sleep(interval)
            api_cache.cleanup_expired()
    
    thread = threading.Thread(target=cleanup, daemon=True)
    thread.start()
    return thread


# 缓存统计端点用
def get_cache_stats() -> dict:
    """获取缓存统计"""
    return api_cache.get_stats()