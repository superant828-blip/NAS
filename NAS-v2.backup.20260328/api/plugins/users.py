"""
用户管理插件
包含用户列表、创建、删除、密码修改等API
"""
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, field_validator, constr
from security.auth import auth_manager, User

# ==================== Pydantic Models ====================

class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    email: str
    password: str
    role: str = "user"
    
    @field_validator('email')
    def validate_email(cls, v):
        from core.security import InputValidator
        result = InputValidator.validate_email(v)
        if not result.valid:
            raise ValueError(result.message)
        return v
    
    @field_validator('password')
    def validate_password(cls, v):
        from core.security import PasswordStrengthChecker
        result = PasswordStrengthChecker.check(v)
        if not result.valid:
            raise ValueError(result.message)
        return v
    
    @field_validator('role')
    def validate_role(cls, v):
        allowed = ['user', 'admin', 'guest']
        if v not in allowed:
            raise ValueError(f"Invalid role. Allowed: {allowed}")
        return v


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
    
    @field_validator('new_password')
    def validate_new_password(cls, v):
        from core.security import PasswordStrengthChecker
        result = PasswordStrengthChecker.check(v)
        if not result.valid:
            raise ValueError(result.message)
        return v


# ==================== 依赖注入 ====================

def get_current_user(authorization: str = Header(None)) -> User:
    """获取当前用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization[7:]
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


# ==================== 创建Router ====================

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# ==================== 用户API ====================

@router.get("")
async def list_users(current_user: User = Depends(require_admin)):
    """列出所有用户"""
    users = auth_manager.list_users()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "created_at": u.created_at,
            "last_login": u.last_login,
            "enabled": u.enabled
        }
        for u in users
    ]


@router.post("")
async def create_user(user_data: UserCreate, current_user: User = Depends(require_admin)):
    """创建用户"""
    result = auth_manager.create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        role=user_data.role
    )
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@router.delete("/{user_id}")
async def delete_user(user_id: int, current_user: User = Depends(require_admin)):
    """删除用户"""
    result = auth_manager.delete_user(user_id)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@router.put("/me/password")
async def change_password(password_data: PasswordChange, current_user: User = Depends(get_current_user)):
    """修改密码"""
    result = auth_manager.change_password(
        user_id=current_user.id,
        old_password=password_data.old_password,
        new_password=password_data.new_password
    )
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result