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
        from core.security import InputValidator
        result = InputValidator.validate_password_strength(v)
        if not result.valid:
            raise ValueError(result.message)
        return v
    
    @field_validator('role')
    def validate_role(cls, v):
        allowed = ['user', 'admin', 'guest', 'manager']  # 添加 manager
        if v not in allowed:
            raise ValueError(f"Invalid role. Allowed: {allowed}")
        return v


class UserUpdate(BaseModel):
    """用户更新模型"""
    username: Optional[constr(min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')] = None
    email: Optional[str] = None
    role: Optional[str] = None
    enabled: Optional[bool] = None
    
    @field_validator('email')
    def validate_email(cls, v):
        if v is None:
            return v
        from core.security import InputValidator
        result = InputValidator.validate_email(v)
        if not result.valid:
            raise ValueError(result.message)
        return v
    
    @field_validator('role')
    def validate_role(cls, v):
        if v is None:
            return v
        allowed = ['user', 'admin', 'guest', 'manager']  # 添加 manager
        if v not in allowed:
            raise ValueError(f"Invalid role. Allowed: {allowed}")
        return v


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
    
    @field_validator('new_password')
    def validate_new_password(cls, v):
        from core.security import InputValidator
        result = InputValidator.validate_password_strength(v)
        if not result.valid:
            raise ValueError(result.message)
        return v


class ProfileUpdate(BaseModel):
    """个人资料更新模型"""
    username: Optional[constr(min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')] = None


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


@router.put("/me")
async def update_profile(profile_data: ProfileUpdate, current_user: User = Depends(get_current_user)):
    """更新个人资料"""
    update_fields = {}
    
    if profile_data.username is not None:
        update_fields['username'] = profile_data.username
    
    if update_fields:
        result = auth_manager.update_user(current_user.id, update_fields)
        if result["status"] != "success":
            raise HTTPException(status_code=400, detail=result.get("message"))
    
    # 返回更新后的用户信息
    user = auth_manager.get_user(user_id=current_user.id)
    return {
        "status": "success",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    }


@router.put("/{user_id}")
async def update_user(user_id: int, user_data: UserUpdate, current_user: User = Depends(require_admin)):
    """更新用户 (管理员)"""
    # 不允许修改自己的管理员角色
    if user_id == current_user.id and user_data.role is not None:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    
    update_fields = {}
    
    if user_data.username is not None:
        update_fields['username'] = user_data.username
    if user_data.email is not None:
        update_fields['email'] = user_data.email
    if user_data.role is not None:
        update_fields['role'] = user_data.role
    if user_data.enabled is not None:
        update_fields['enabled'] = user_data.enabled
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    result = auth_manager.update_user(user_id, update_fields)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    user = auth_manager.get_user(user_id=user_id)
    return {
        "status": "success",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "enabled": user.enabled
        }
    }