#!/usr/bin/env python3
import socket
import threading
import time
import sys
import os
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, '/home/test/.openclaw/workspace/tech-news-dashboard')

# 先导入并配置 Flask
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 加载配置
import json
CONFIG_FILE = '/home/test/.openclaw/workspace/tech-news-dashboard/config.json'
with open(CONFIG_FILE) as f:
    CONFIG = json.load(f)

# 定义监控板块
DOMAINS = ['AI', '具身智能', '半导体', 'AI 应用', '大模型', '新能源', '商业航天', 'AI PC', '国际局势']
NEWS_CACHE = {}

# 新闻获取函数
def fetch_domain_news(domain):
    """获取特定板块的新闻"""
    import subprocess
    try:
        result = subprocess.run(
            ['python3', '/home/test/.openclaw/workspace/skills/tech-news-direct/scripts/search.py', domain, 'news', domain],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except:
                return []
        return []
    except Exception as e:
        print(f"获取新闻失败 {domain}: {e}")
        return []

def search_news(keyword, limit=20):
    """搜索新闻"""
    import subprocess
    try:
        result = subprocess.run(
            ['node', '/home/test/.openclaw/workspace/skills/baidu-web-search/scripts/search.js', keyword, '-n', str(limit)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except:
                return []
        return []
    except Exception as e:
        print(f"搜索失败 {keyword}: {e}")
        return []

# 路由
@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/news')
def get_news():
    domain = request.args.get('domain', 'AI')
    return jsonify(NEWS_CACHE.get(domain, []))

@app.route('/api/domains')
def get_domains():
    return jsonify(DOMAINS)

@app.route('/api/search')
def search():
    keyword = request.args.get('q', '')
    limit = int(request.args.get('limit', 20))
    results = search_news(keyword, limit)
    return jsonify({'results': results, 'total': len(results)})

# 后台线程
def background_news_fetcher():
    global NEWS_CACHE
    while True:
        try:
            for domain in DOMAINS:
                news_data = fetch_domain_news(domain)
                NEWS_CACHE[domain] = news_data
            time.sleep(CONFIG.get('refresh_interval', 60))
        except Exception as e:
            print(f"新闻获取错误：{e}")
            time.sleep(30)

if __name__ == '__main__':
    # 启动后台线程
    fetcher_thread = threading.Thread(target=background_news_fetcher, daemon=True)
    fetcher_thread.start()
    
    print("=" * 50)
    print("🚀 科技资讯监控 Dashboard 启动")
    print("📡 访问地址：http://localhost:5000")
    print(f"🔄 刷新间隔：{CONFIG.get('refresh_interval', 60)}秒")
    print(f"📊 监控板块：{', '.join(DOMAINS)}")
    print("=" * 50)
    
    # 使用 socket 设置 SO_REUSEADDR
    from werkzeug.serving import make_server
    class ReuseAddrWSGIServer:
        def server_bind(self):
            socket.socket().setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            super().server_bind()
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)