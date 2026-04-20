#!/usr/bin/env python3
"""
NAS-v2 API 测试脚本
用法: python3 test_api_python.py
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"
TOKEN = ""

def test_login():
    """测试用户登录"""
    print("\n=== 1. 用户登录 (POST /api/v1/auth/login) ===")
    url = f"{BASE_URL}/api/v1/auth/login"
    data = {"email": "admin@nas.local", "password": "admin123"}
    print(f"请求: POST {url}")
    print(f"body: {json.dumps(data)}")
    
    try:
        resp = requests.post(url, json=data)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text[:200]}...")
        
        if resp.status_code == 200:
            global TOKEN
            TOKEN = resp.json().get("access_token", "")
            print("通过: ✓")
            return True
        else:
            print("通过: ✗")
            return False
    except Exception as e:
        print(f"错误: {e}")
        print("通过: ✗ (服务器可能未运行)")
        return False

def test_register():
    """测试用户注册"""
    print("\n=== 2. 用户注册 (POST /api/v1/auth/register) ===")
    url = f"{BASE_URL}/api/v1/auth/register"
    data = {"username": "testuser", "email": "test2@example.com", "password": "test123"}
    print(f"请求: POST {url}")
    print(f"body: {json.dumps(data)}")
    
    try:
        resp = requests.post(url, json=data)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text[:200]}...")
        print("通过: ✓" if resp.status_code in [200, 400] else "通过: ✗")
    except Exception as e:
        print(f"错误: {e}")
        print("通过: ✗")

def test_file_list():
    """测试文件列表"""
    print("\n=== 3. 文件列表 (GET /api/v1/files) ===")
    url = f"{BASE_URL}/api/v1/files/"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    print(f"请求: GET {url}")
    
    try:
        resp = requests.get(url, headers=headers)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text[:200]}...")
        print("通过: ✓" if resp.status_code == 200 else "通过: ✗")
    except Exception as e:
        print(f"错误: {e}")
        print("通过: ✗")

def test_file_upload():
    """测试文件上传"""
    print("\n=== 4. 文件上传 (POST /api/v1/files/upload) ===")
    url = f"{BASE_URL}/api/v1/files/upload"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    files = {"file": ("test.txt", b"Hello NAS-v2", "text/plain")}
    print(f"请求: POST {url}")
    
    try:
        resp = requests.post(url, headers=headers, files=files)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text[:200]}...")
        print("通过: ✓" if resp.status_code == 200 else "通过: ✗")
    except Exception as e:
        print(f"错误: {e}")
        print("通过: ✗")

def test_create_folder():
    """测试创建文件夹"""
    print("\n=== 5. 创建文件夹 (POST /api/v1/files/folder) ===")
    url = f"{BASE_URL}/api/v1/files/folder?name=testfolder"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    print(f"请求: POST {url}")
    
    try:
        resp = requests.post(url, headers=headers)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text[:200]}...")
        print("通过: ✓" if resp.status_code == 200 else "通过: ✗")
    except Exception as e:
        print(f"错误: {e}")
        print("通过: ✗")

def test_agent_status():
    """测试智能体状态"""
    print("\n=== 6. 智能体状态 (GET /api/v1/agents/status) ===")
    url = f"{BASE_URL}/api/v1/agents/status"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    print(f"请求: GET {url}")
    
    try:
        resp = requests.get(url, headers=headers)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text[:300]}...")
        print("通过: ✓" if resp.status_code == 200 else "通过: ✗")
    except Exception as e:
        print(f"错误: {e}")
        print("通过: ✗")

def main():
    print("="*50)
    print("NAS-v2 API 测试")
    print("="*50)
    
    # 测试前先检查服务器是否运行
    try:
        resp = requests.get(BASE_URL, timeout=2)
        print(f"服务器状态: 运行中 (状态码: {resp.status_code})")
    except:
        print("错误: 无法连接到服务器 http://localhost:8000")
        print("请先启动服务器: cd /home/test/.openclaw/workspace/NAS-v2 && ./start.sh")
        sys.exit(1)
    
    # 执行测试
    test_login()
    test_register()
    test_file_list()
    test_file_upload()
    test_create_folder()
    test_agent_status()
    
    print("\n" + "="*50)
    print("测试完成")
    print("="*50)

if __name__ == "__main__":
    main()