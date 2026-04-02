"""
认证路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from datetime import datetime, timedelta
import jwt
import uuid

from core.config import config
from core.security import PasswordStrengthChecker
from security.auth import auth_manager
from core.logging import logger

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    username: str = None
    
    @field_validator('password')
    def validate_password(cls, v):
        checker = PasswordStrengthChecker()
        if not checker.check(v).is_valid:
            raise ValueError('Password too weak')
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """用户登录"""
    user = await auth_manager.authenticate(request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )
    
    # 生成token
    token = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "exp": datetime.utcnow() + timedelta(days=7)
        },
        config.JWT_SECRET,
        algorithm="HS256"
    )
    
    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role
        }
    )


@router.post("/register")
async def register(request: RegisterRequest):
    """用户注册"""
    # 检查邮箱是否存在
    existing = await auth_manager.get_user_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    # 创建用户
    user = await auth_manager.create_user(
        email=request.email,
        password=request.password,
        username=request.username or request.email.split('@')[0]
    )
    
    return {"id": user.id, "email": user.email, "username": user.username}


@router.post("/logout")
async def logout():
    """用户登出"""
    return {"message": "已登出"}


@router.get("/me")
async def get_current_user(authorization: str = Depends(lambda: None)):
    """获取当前用户信息"""
    # 从authorization header获取用户信息
    # 实现依赖于auth_manager
    pass