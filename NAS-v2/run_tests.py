#!/usr/bin/env python3
"""
NAS-v2 快速测试运行器
使用方法: python3 run_tests.py
"""
import requests

BASE_URL = "http://localhost:8003"

def test_auth():
    """认证测试"""
    print("\n=== 认证模块测试 ===")
    
    # 登录
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login",
        json={"email": "admin@nas.local", "password": "admin123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    print("✅ 登录成功")
    
    # 用户信息
    resp = requests.get(f"{BASE_URL}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    print(f"✅ 用户信息: {resp.json()['username']}")
    
    return token

def test_files(token):
    """文件模块测试"""
    print("\n=== 文件模块测试 ===")
    
    # 文件列表
    resp = requests.get(f"{BASE_URL}/api/v1/files/",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    print(f"✅ 文件列表: {len(resp.json())}项")
    
    # 创建文件夹
    import time
    name = f"test_{int(time.time())}"
    resp = requests.post(f"{BASE_URL}/api/v1/files/folder",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "parent_id": None})
    assert resp.status_code == 200
    folder_id = resp.json()["id"]
    print(f"✅ 创建文件夹: {name}")
    
    # 删除文件夹
    requests.delete(f"{BASE_URL}/api/v1/files/{folder_id}",
        headers={"Authorization": f"Bearer {token}"})
    print(f"🧹 删除测试文件夹")

def test_albums(token):
    """相册模块测试"""
    print("\n=== 相册模块测试 ===")
    
    resp = requests.get(f"{BASE_URL}/api/v1/albums",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    print(f"✅ 相册列表: {len(resp.json())}个")

def test_agents(token):
    """智能体模块测试"""
    print("\n=== 智能体模块测试 ===")
    
    resp = requests.get(f"{BASE_URL}/api/v1/agents/status",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    print(f"✅ 智能体状态: {data['stats']['workers']}个工作器")
    
    resp = requests.get(f"{BASE_URL}/api/v1/agents/tasks",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    print(f"✅ 任务列表查询成功")

if __name__ == "__main__":
    print("="*50)
    print("NAS-v2 快速测试")
    print("="*50)
    
    try:
        token = test_auth()
        test_files(token)
        test_albums(token)
        test_agents(token)
        
        print("\n" + "="*50)
        print("✅ 全部测试通过!")
        print("="*50)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        exit(1)
