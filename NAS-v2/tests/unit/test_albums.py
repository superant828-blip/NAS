#!/usr/bin/env python3
"""
NAS-v2 单元测试 - 相册模块
"""
import pytest
import requests

BASE_URL = "http://localhost:8003"

def get_token():
    """获取测试token"""
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": "admin@nas.local", "password": "admin123"}
    )
    return resp.json()["access_token"]

class TestAlbums:
    """相册模块测试"""
    
    def test_list_albums(self):
        """获取相册列表"""
        token = get_token()
        response = requests.get(
            f"{BASE_URL}/api/v1/albums",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_album(self):
        """创建相册"""
        token = get_token()
        import time
        album_name = f"test_album_{int(time.time())}"
        
        response = requests.post(
            f"{BASE_URL}/api/v1/albums",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": album_name, "description": "测试相册"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == album_name
        
        # 清理
        requests.delete(
            f"{BASE_URL}/api/v1/albums/{data['id']}",
            headers={"Authorization": f"Bearer {token}"}
        )
    
    def test_get_album(self):
        """获取相册详情"""
        token = get_token()
        
        # 先创建相册
        import time
        album_name = f"test_get_{int(time.time())}"
        create_resp = requests.post(
            f"{BASE_URL}/api/v1/albums",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": album_name, "description": "测试"}
        )
        album_id = create_resp.json()["id"]
        
        # 获取详情
        response = requests.get(
            f"{BASE_URL}/api/v1/albums/{album_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == album_id
        
        # 清理
        requests.delete(
            f"{BASE_URL}/api/v1/albums/{album_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

class TestAgents:
    """智能体模块测试"""
    
    def test_get_agent_status(self):
        """获取智能体状态"""
        token = get_token()
        response = requests.get(
            f"{BASE_URL}/api/v1/agents/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        assert "workers" in data
        assert data["stats"]["workers"] == 3  # 3个工作器
    
    def test_list_tasks(self):
        """列出任务"""
        token = get_token()
        response = requests.get(
            f"{BASE_URL}/api/v1/agents/tasks",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "tasks" in data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
