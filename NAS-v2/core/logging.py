"""
日志和错误处理模块
"""
import logging
import traceback
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from functools import wraps
import json

# 项目根目录
ROOT = Path(__file__).parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志文件路径
LOG_FILE = LOG_DIR / "nas-v2.log"
ERROR_LOG_FILE = LOG_DIR / "errors.log"
ACCESS_LOG_FILE = LOG_DIR / "access.log"


def setup_logging(level: str = "INFO") -> None:
    """设置日志配置"""
    
    # 创建日志格式
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # 错误日志处理器
    error_handler = logging.FileHandler(ERROR_LOG_FILE, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)


# 初始化日志
setup_logging()

# 获取日志记录器
logger = logging.getLogger(__name__)


class ErrorLogger:
    """错误日志记录器"""
    
    @staticmethod
    def log_error(
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        request_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        记录错误
        
        Returns:
            错误跟踪ID
        """
        error_id = f"ERR-{datetime.now().strftime('%Y%m%d%H%M%S')}-{id(error) % 10000:04d}"
        
        error_data = {
            "error_id": error_id,
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {},
            "user_id": user_id,
            "request": request_info or {}
        }
        
        # 写入错误日志
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(error_data, ensure_ascii=False, indent=2) + "\n")
            f.write("=" * 80 + "\n")
        
        # 同时写入主日志
        logger.error(
            f"[{error_id}] {type(error).__name__}: {error}",
            extra={"context": context, "user_id": user_id}
        )
        
        return error_id
    
    @staticmethod
    def log_access(
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: Optional[int] = None,
        ip: Optional[str] = None
    ) -> None:
        """记录访问日志"""
        access_data = {
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "path": path,
            "status": status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "ip": ip
        }
        
        with open(ACCESS_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(access_data) + "\n")


class NASException(Exception):
    """NAS自定义异常基类"""
    
    def __init__(
        self,
        message: str,
        code: str = "NAS_ERROR",
        status_code: int = 500,
        details: Optional[Dict] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        result = {
            "error": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


class ValidationError(NASException):
    """验证错误"""
    
    def __init__(self, message: str, field: str = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            details={"field": field} if field else {}
        )


class AuthenticationError(NASException):
    """认证错误"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTH_ERROR",
            status_code=401
        )


class AuthorizationError(NASException):
    """授权错误"""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=403
        )


class NotFoundError(NASException):
    """资源未找到"""
    
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            message=f"{resource} not found",
            code="NOT_FOUND",
            status_code=404
        )


class ConflictError(NASException):
    """冲突错误"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409
        )


class RateLimitError(NASException):
    """速率限制错误"""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            code="RATE_LIMIT",
            status_code=429
        )


class FileTooLargeError(NASException):
    """文件过大错误"""
    
    def __init__(self, max_size: int):
        super().__init__(
            message=f"File too large. Maximum size: {max_size} bytes",
            code="FILE_TOO_LARGE",
            status_code=413,
            details={"max_size": max_size}
        )


def handle_exception(func):
    """异常处理装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except NASException as e:
            # 自定义异常直接抛出
            raise
        except Exception as e:
            # 记录未知错误
            error_id = ErrorLogger.log_error(
                error=e,
                context={"function": func.__name__}
            )
            # 返回友好的错误消息
            raise NASException(
                message="An internal error occurred. Please try again later.",
                code="INTERNAL_ERROR",
                details={"error_id": error_id}
            )
    return wrapper


def log_request(func):
    """请求日志装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        import time
        start_time = time.time()
        
        # 获取请求信息
        request = kwargs.get('request') or (args[0] if args and hasattr(args[0], 'method') else None)
        
        try:
            result = await func(*args, **kwargs)
            
            # 计算耗时
            duration_ms = (time.time() - start_time) * 1000
            
            # 记录访问日志
            if request:
                ErrorLogger.log_access(
                    method=getattr(request, 'method', 'UNKNOWN'),
                    path=str(getattr(request, 'url', '/')),
                    status_code=200,
                    duration_ms=duration_ms
                )
            
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            if request:
                status_code = getattr(e, 'status_code', 500)
                ErrorLogger.log_access(
                    method=getattr(request, 'method', 'UNKNOWN'),
                    path=str(getattr(request, 'url', '/')),
                    status_code=status_code,
                    duration_ms=duration_ms
                )
            
            raise
    
    return wrapper


def get_recent_errors(limit: int = 10) -> list:
    """获取最近的错误日志"""
    if not ERROR_LOG_FILE.exists():
        return []
    
    errors = []
    try:
        with open(ERROR_LOG_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            # 简单解析 - 提取错误ID和消息
            import re
            pattern = r'"error_id":\s*"([^"]+)"'
            id_pattern = r'"error_id":\s*"([^"]+)"'
            msg_pattern = r'"error_message":\s*"([^"]+)"'
            
            entries = content.split("=" * 80)
            for entry in entries[-limit:]:
                error_id = re.search(id_pattern, entry)
                error_msg = re.search(msg_pattern, entry)
                if error_id:
                    errors.append({
                        "error_id": error_id.group(1),
                        "message": error_msg.group(1) if error_msg else "Unknown"
                    })
    except Exception:
        pass
    
    return errors