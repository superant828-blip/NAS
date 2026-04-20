"""系统配置插件"""
from fastapi import APIRouter, Depends, HTTPException, Header
from security.auth import auth_manager, User
import json
from pathlib import Path

router = APIRouter(prefix="/api/v1/config", tags=["系统配置"])

ROOT = Path(__file__).parent.parent.parent

# 全局配置
ALLOWED_EXTENSIONS = {'txt', 'jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar', '7z', 'mp4', 'avi', 'mov', 'mp3', 'wav'}
APP_CONFIG = {"allowed_extensions": sorted(list(ALLOWED_EXTENSIONS))}

def load_app_config():
    config_file = ROOT / "data" / "app_config.json"
    if config_file.exists():
        return json.loads(config_file.read_text())
    return {"allowed_extensions": sorted(list(ALLOWED_EXTENSIONS))}

def save_app_config(config_data):
    config_file = ROOT / "data" / "app_config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config_data, ensure_ascii=False, indent=2))

# 初始化配置
APP_CONFIG = load_app_config()
if APP_CONFIG.get("allowed_extensions"):
    ALLOWED_EXTENSIONS = set(APP_CONFIG["allowed_extensions"])

def get_current_user(authorization: str = Header(None)) -> User:
    """获取当前用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    payload = auth_manager.verify_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = auth_manager.get_user(user_id=payload.get("user_id"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return current_user

@router.get("")
async def get_config(current_user: User = Depends(get_current_user)):
    """获取系统配置"""
    return {
        "allowed_extensions": sorted(list(ALLOWED_EXTENSIONS))
    }

@router.post("/update")
async def update_config(request: dict, current_user: User = Depends(require_admin)):
    """更新系统配置（仅管理员）"""
    global ALLOWED_EXTENSIONS
    if "allowed_extensions" in request:
        allowed = [ext.strip().lower() for ext in request["allowed_extensions"] if ext.strip()]
        ALLOWED_EXTENSIONS = set(allowed)
        APP_CONFIG["allowed_extensions"] = allowed
        save_app_config(APP_CONFIG)
    
    return {"success": True, "allowed_extensions": sorted(list(ALLOWED_EXTENSIONS))}
