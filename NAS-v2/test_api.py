#!/usr/bin/env python3
"""
NAS-v2 端到端集成测试脚本
使用 Python requests 库执行API测试
"""
import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
TOKEN = ""

def print_test(name: str, response: requests.Response):
    """打印测试结果"""
    print(f"\n{'='*50}")
    print(f"测试: {name}")
    print(f"{'='*50}")
    print(f"状态码: {response.status_code}")
    try:
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except:
        print(f"响应: {response.text}")
    return response

def test_user_flow():
    """1. 完整用户流程测试"""
    print("\n" + "="*60)
    print("1. 完整用户流程测试")
    print("="*60)
    
    # 1.1 登录
    print("\n[1.1] 用户登录...")
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": "admin@nas.local",
        "password": "admin123"
    })
    print_test("登录", resp)
    
    global TOKEN
    if resp.status_code == 200:
        TOKEN = resp.json().get("access_token", "")
        print(f"\n✓ 获取Token: {TOKEN[:20]}...")
    else:
        print("\n⚠ 登录失败，使用测试Token")
        TOKEN = "test_token"
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    # 1.2 获取用户信息
    print("\n[1.2] 获取用户信息...")
    resp = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
    print_test("获取用户信息", resp)
    
    # 1.3 获取文件列表
    print("\n[1.3] 获取文件列表...")
    resp = requests.get(f"{BASE_URL}/api/v1/files/", headers=headers)
    print_test("获取文件列表", resp)
    
    # 1.4 创建文件夹
    print("\n[1.4] 创建文件夹...")
    resp = requests.post(f"{BASE_URL}/api/v1/files/folder", 
        headers=headers,
        json={"name": "test_folder", "parent_id": None})
    print_test("创建文件夹", resp)
    
    # 1.5 上传文件
    print("\n[1.5] 上传文件...")
    files = {'file': ('test.txt', b'test content', 'text/plain')}
    resp = requests.post(f"{BASE_URL}/api/v1/files/upload", 
        headers=headers, 
        files=files)
    print_test("上传文件", resp)
    
    # 1.6 获取分享链接
    print("\n[1.6] 获取分享链接...")
    resp = requests.get(f"{BASE_URL}/api/v1/share/links", headers=headers)
    print_test("获取分享链接", resp)

def test_file_management():
    """2. 文件管理流程测试"""
    print("\n" + "="*60)
    print("2. 文件管理流程测试")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    # 2.1 创建文件夹
    print("\n[2.1] 创建文件夹...")
    resp = requests.post(f"{BASE_URL}/api/v1/files/folder",
        headers=headers,
        json={"name": "folder_management_test", "parent_id": None})
    print_test("创建文件夹", resp)
    
    # 2.2 移动文件
    print("\n[2.2] 移动文件...")
    resp = requests.post(f"{BASE_URL}/api/v1/files/move",
        headers=headers,
        json={"file_id": 1, "new_parent_id": 1})
    print_test("移动文件", resp)
    
    # 2.3 删除文件
    print("\n[2.3] 删除文件...")
    resp = requests.delete(f"{BASE_URL}/api/v1/files/1", headers=headers)
    print_test("删除文件", resp)
    
    # 2.4 获取回收站
    print("\n[2.4] 获取回收站...")
    resp = requests.get(f"{BASE_URL}/api/v1/trash/", headers=headers)
    print_test("获取回收站", resp)

def test_album_flow():
    """3. 相册流程测试"""
    print("\n" + "="*60)
    print("3. 相册流程测试")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    # 3.1 创建相册
    print("\n[3.1] 创建相册...")
    resp = requests.post(f"{BASE_URL}/api/v1/albums",
        headers=headers,
        json={"name": "test_album", "description": "Test album"})
    print_test("创建相册", resp)
    
    # 3.2 获取相册列表
    print("\n[3.2] 获取相册列表...")
    resp = requests.get(f"{BASE_URL}/api/v1/albums", headers=headers)
    print_test("获取相册列表", resp)
    
    # 3.3 上传照片
    print("\n[3.3] 上传照片...")
    files = {'photo': ('test.jpg', b'fake image', 'image/jpeg')}
    resp = requests.post(f"{BASE_URL}/api/v1/albums/1/photos",
        headers=headers,
        files=files)
    print_test("上传照片", resp)
    
    # 3.4 获取相册照片
    print("\n[3.4] 获取相册照片...")
    resp = requests.get(f"{BASE_URL}/api/v1/albums/1/photos", headers=headers)
    print_test("获取相册照片", resp)

def test_agent_flow():
    """4. 智能体流程测试"""
    print("\n" + "="*60)
    print("4. 智能体流程测试")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    # 4.1 获取智能体状态
    print("\n[4.1] 获取智能体状态...")
    resp = requests.get(f"{BASE_URL}/api/v1/agents/status", headers=headers)
    print_test("获取智能体状态", resp)
    
    # 4.2 运行测试智能体
    print("\n[4.2] 运行测试智能体...")
    resp = requests.post(f"{BASE_URL}/api/v1/agents/test/run",
        headers=headers,
        json={"test_type": "unit", "target": "test.py"})
    print_test("运行测试智能体", resp)
    
    # 4.3 创建智能体任务
    print("\n[4.3] 创建智能体任务...")
    resp = requests.post(f"{BASE_URL}/api/v1/agents/tasks",
        headers=headers,
        json={
            "agent_type": "test",
            "task": "run unit tests",
            "input_data": {},
            "mode": "parallel"
        })
    print_test("创建智能体任务", resp)
    
    # 4.4 列出任务
    print("\n[4.4] 列出任务...")
    resp = requests.get(f"{BASE_URL}/api/v1/agents/tasks", headers=headers)
    print_test("列出任务", resp)
    
    # 4.5 获取存储池
    print("\n[4.5] 获取存储池...")
    resp = requests.get(f"{BASE_URL}/api/v1/storage/pools", headers=headers)
    print_test("获取存储池", resp)
    
    # 4.6 获取快照
    print("\n[4.6] 获取快照...")
    resp = requests.get(f"{BASE_URL}/api/v1/snapshots", headers=headers)
    print_test("获取快照", resp)

def main():
    """主函数"""
    print("="*60)
    print("NAS-v2 端到端集成测试")
    print("="*60)
    print(f"后端地址: {BASE_URL}")
    
    try:
        # 测试服务器连接
        resp = requests.get(BASE_URL, timeout=5)
        print(f"\n✓ 服务器连接成功: {resp.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"\n✗ 服务器连接失败: {e}")
        print("请确保后端服务正在运行: python3 api/main.py")
        sys.exit(1)
    
    # 运行测试
    test_user_flow()
    test_file_management()
    test_album_flow()
    test_agent_flow()
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)

if __name__ == "__main__":
    main()