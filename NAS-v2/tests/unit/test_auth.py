#!/usr/bin/env python3
"""
NAS-v2 单元测试 - 认证模块
"""
import pytest
import requests
import sys

BASE_URL = "http://localhost:8003"

class TestAuth:
    """认证模块测试"""
    
    def test_login_success(self):
        """测试登录成功"""
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "admin@nas.local", "password": "admin123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "admin@nas.local"
    
    def test_login_invalid_password(self):
        """测试密码错误"""
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "admin@nas.local", "password": "wrong"}
        )
        assert response.status_code == 401
    
    def test_login_invalid_email(self):
        """测试用户不存在"""
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "notexist@nas.local", "password": "admin123"}
        )
        assert response.status_code == 401
    
    def test_get_current_user(self):
        """获取当前用户信息"""
        # 先登录获取token
        login_resp = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "admin@nas.local", "password": "admin123"}
        )
        token = login_resp.json()["access_token"]
        
        # 获取用户信息
        response = requests.get(
            f"{BASE_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@nas.local"
        assert data["role"] == "admin"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
