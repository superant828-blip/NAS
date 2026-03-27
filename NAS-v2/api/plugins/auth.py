"""
认证插件 - 用户登录、注册、登出和当前用户信息
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, field_validator, constr

from security.auth import auth_manager, User
from core.security import InputValidator, PasswordStrengthChecker


# ==================== 路由配置 ====================

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


# ==================== 请求模型 ====================

class LoginRequest(BaseModel):
    email: str
    password: str
    
    @field_validator('email')
    def validate_email(cls, v):
        result = InputValidator.validate_email(v)
        if not result.valid:
            raise ValueError(result.message)
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    email: str
    password: str
    role: str = "user"
    
    @field_validator('email')
    def validate_email(cls, v):
        result = InputValidator.validate_email(v)
        if not result.valid:
            raise ValueError(result.message)
        return v
    
    @field_validator('password')
    def validate_password(cls, v):
        result = InputValidator.validate_password_strength(v)
        if not result.valid:
            raise ValueError(result.message)
        return v
    
    @field_validator('role')
    def validate_role(cls, v):
        allowed = ['user', 'admin', 'guest']
        if v not in allowed:
            raise ValueError(f"Invalid role. Allowed: {allowed}")
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


# ==================== 认证接口 ====================

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """用户登录"""
    user = auth_manager.authenticate(request.email, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    token = auth_manager.create_token(user)
    
    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    )


@router.post("/register")
async def register(user_data: UserCreate):
    """用户注册"""
    result = auth_manager.create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        role=user_data.role
    )
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """用户登出"""
    return {"status": "success", "message": "Logged out"}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login
    }


# ==================== 密码强度检查端点 - 单独路由 ====================

password_router = APIRouter(prefix="/api/v1/password", tags=["密码检查"])


@password_router.get("/check")
async def check_password_strength(password: str, current_user: User = Depends(get_current_user)):
    """检查密码强度"""
    result = PasswordStrengthChecker.check(password)
    return result