#!/usr/bin/env python3
"""
NAS-v2 单元测试 - 文件管理模块
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

class TestFiles:
    """文件管理测试"""
    
    def test_list_files(self):
        """获取文件列表"""
        token = get_token()
        response = requests.get(
            f"{BASE_URL}/api/v1/files/",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_create_folder(self):
        """创建文件夹"""
        token = get_token()
        import time
        folder_name = f"test_folder_{int(time.time())}"
        
        response = requests.post(
            f"{BASE_URL}/api/v1/files/folder",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": folder_name, "parent_id": None}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == folder_name
        assert data["is_folder"] == 1
        
        # 清理：删除测试文件夹
        requests.delete(
            f"{BASE_URL}/api/v1/files/{data['id']}",
            headers={"Authorization": f"Bearer {token}"}
        )
    
    def test_get_file_info(self):
        """获取文件详情"""
        token = get_token()
        
        # 先创建测试文件夹
        import time
        folder_name = f"test_info_{int(time.time())}"
        create_resp = requests.post(
            f"{BASE_URL}/api/v1/files/folder",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": folder_name, "parent_id": None}
        )
        folder_id = create_resp.json()["id"]
        
        # 获取详情
        response = requests.get(
            f"{BASE_URL}/api/v1/files/{folder_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == folder_id
        
        # 清理
        requests.delete(
            f"{BASE_URL}/api/v1/files/{folder_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
    
    def test_search_files(self):
        """搜索文件"""
        token = get_token()
        response = requests.get(
            f"{BASE_URL}/api/v1/files/search?q=测试",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
