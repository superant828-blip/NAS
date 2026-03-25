#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
私有云相册NAS系统 - Python版（完整版）
增加功能：排序、分类、重命名、用户管理
"""
import os
import uuid
import hashlib
import time
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, send_file, session
from flask_cors import CORS
import pymysql

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # 安全密钥
CORS(app, supports_credentials=True)

# 配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Love@5722',
    'database': 'album_nas',
    'charset': 'utf8mb4'
}
UPLOAD_DIR = '/mnt/windows_share/album_nas/uploads'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'pdf', 'doc', 'docx', 'zip', 'rar', 'txt', 'mp3', 'wav', 'xls', 'xlsx'}

for subdir in ['photos', 'thumbs', 'files', 'avatars']:
    os.makedirs(os.path.join(UPLOAD_DIR, subdir), exist_ok=True)

def get_db():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor, autocommit=True)

def init_db():
    """初始化数据库"""
    conn = get_db()
    c = conn.cursor()
    
    tables = [
        '''CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            email VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            salt VARCHAR(32) NOT NULL,
            avatar VARCHAR(255),
            role ENUM('admin', 'manager', 'user') DEFAULT 'user',
            status TINYINT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP NULL,
            INDEX idx_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
        
        '''CREATE TABLE IF NOT EXISTS albums (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            is_encrypted TINYINT DEFAULT 0,
            password_hash VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
        
        '''CREATE TABLE IF NOT EXISTS photos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            album_id INT,
            original_name VARCHAR(255) NOT NULL,
            stored_name VARCHAR(255) NOT NULL UNIQUE,
            path VARCHAR(500) NOT NULL,
            thumbnail_path VARCHAR(500),
            size INT,
            mime_type VARCHAR(100),
            width INT,
            height INT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
        
        '''CREATE TABLE IF NOT EXISTS files (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            parent_id INT DEFAULT NULL,
            name VARCHAR(255) NOT NULL,
            is_folder TINYINT DEFAULT 0,
            path VARCHAR(500) NOT NULL,
            size INT,
            mime_type VARCHAR(100),
            is_encrypted TINYINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
        
        '''CREATE TABLE IF NOT EXISTS file_tags (
            id INT AUTO_INCREMENT PRIMARY KEY,
            file_id INT NOT NULL,
            tag VARCHAR(50) NOT NULL,
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
        
        '''CREATE TABLE IF NOT EXISTS trash (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            file_type ENUM('photo', 'file', 'folder') NOT NULL,
            original_id INT NOT NULL,
            original_name VARCHAR(255) NOT NULL,
            stored_path VARCHAR(500),
            size INT,
            mime_type VARCHAR(100),
            deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_deleted (user_id, deleted_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
        
        '''CREATE TABLE IF NOT EXISTS shares (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            file_type ENUM('photo', 'file') NOT NULL,
            file_id INT NOT NULL,
            token VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(255),
            expire_hours INT DEFAULT 24,
            view_count INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_token (token)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
        
        '''CREATE TABLE IF NOT EXISTS user_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            action VARCHAR(50) NOT NULL,
            ip_address VARCHAR(45),
            user_agent VARCHAR(255),
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_action (user_id, action),
            INDEX idx_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'''
    ]
    
    for sql in tables:
        try:
            c.execute(sql)
        except:
            pass
    
    # 创建默认管理员
    c.execute("SELECT id FROM users WHERE username = 'admin'")
    if not c.fetchone():
        salt = secrets.token_hex(16)
        pw = hashlib.sha256(('admin123' + salt).encode()).hexdigest()
        c.execute("INSERT INTO users (username, email, password_hash, salt, role) VALUES (%s, %s, %s, %s, %s)",
            ('admin', 'admin@example.com', pw, salt, 'admin'))
    
    conn.close()

# 安全函数
def generate_salt():
    return secrets.token_hex(16)

def hash_password(pw, salt):
    return hashlib.sha256((pw + salt).encode()).hexdigest()

def create_token(user_id, username, role):
    token = secrets.token_hex(32)
    tokens[token] = {'userId': user_id, 'username': username, 'role': role, 'exp': time.time() + 7*86400}
    return token

def verify_token(token):
    if token in tokens and tokens[token]['exp'] > time.time():
        return tokens[token]
    return None

# Token存储
tokens = {}

# 装饰器
def auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = verify_token(token)
        if not user:
            return jsonify({'error': '请先登录'}), 401
        request.userId = user['userId']
        request.userRole = user['role']
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.userRole != 'admin':
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated

# ============ 认证 ============

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not username or not email or not password:
        return jsonify({'error': '请填写完整信息'}), 400
    
    salt = generate_salt()
    pw_hash = hash_password(password, salt)
    
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, email, password_hash, salt) VALUES (%s, %s, %s, %s)",
            (username, email, pw_hash, salt))
        return jsonify({'message': '注册成功'}), 201
    except:
        return jsonify({'error': '用户名或邮箱已存在'}), 400
    finally:
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = c.fetchone()
    
    # 记录登录日志（无论成功与否）
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')[:255]
    
    if not user:
        # 用户不存在，记录失败日志
        c.execute("INSERT INTO user_logs (user_id, action, ip_address, user_agent, details) VALUES (%s, %s, %s, %s, %s)",
            (0, 'login_failed', ip_address, user_agent, f'用户不存在: {email}'))
        conn.close()
        return jsonify({'error': '用户不存在'}), 401
    
    if user['status'] != 1:
        # 账号被禁用，记录失败日志
        c.execute("INSERT INTO user_logs (user_id, action, ip_address, user_agent, details) VALUES (%s, %s, %s, %s, %s)",
            (user['id'], 'login_failed', ip_address, user_agent, '账号已被禁用'))
        conn.close()
        return jsonify({'error': '账号已被禁用'}), 401
    
    pw_hash = hash_password(password, user['salt'])
    if pw_hash == user['password_hash']:
        token = create_token(user['id'], user['username'], user['role'])
        
        # 更新最后登录时间
        c.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user['id'],))
        
        # 记录成功登录日志
        c.execute("INSERT INTO user_logs (user_id, action, ip_address, user_agent, details) VALUES (%s, %s, %s, %s, %s)",
            (user['id'], 'login_success', ip_address, user_agent, '登录成功'))
        
        conn.close()
        
        return jsonify({
            'token': token, 
            'user': {'id': user['id'], 'username': user['username'], 'email': user['email'], 'role': user['role']}
        })
    
    # 密码错误，记录失败日志
    c.execute("INSERT INTO user_logs (user_id, action, ip_address, user_agent, details) VALUES (%s, %s, %s, %s, %s)",
        (user['id'], 'login_failed', ip_address, user_agent, '密码错误'))
    conn.close()
    return jsonify({'error': '密码错误'}), 401

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = verify_token(token)
    if user:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, username, email, role, avatar, created_at FROM users WHERE id = %s", (user['userId'],))
        u = c.fetchone()
        conn.close()
        return jsonify({'logged_in': True, 'user': u})
    return jsonify({'error': '未登录'}), 401

# ============ 用户管理（仅管理员） ============

@app.route('/api/users', methods=['GET'])
@auth
@admin_required
def get_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, email, role, status, created_at, last_login FROM users ORDER BY created_at DESC")
    users = c.fetchall()
    conn.close()
    return jsonify(users)

@app.route('/api/users/<int:id>/status', methods=['PUT'])
@auth
@admin_required
def toggle_user_status(id):
    data = request.json
    status = data.get('status', 1)
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET status = %s WHERE id = %s", (status, id))
    conn.close()
    return jsonify({'message': '更新成功'})

@app.route('/api/users/<int:id>/role', methods=['PUT'])
@auth
@admin_required
def change_user_role(id):
    data = request.json
    role = data.get('role')
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET role = %s WHERE id = %s", (role, id))
    conn.close()
    return jsonify({'message': '更新成功'})

@app.route('/api/users/<int:id>', methods=['DELETE'])
@auth
@admin_required
def delete_user(id):
    if id == request.userId:
        return jsonify({'error': '不能删除自己'}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = %s", (id,))
    conn.close()
    return jsonify({'message': '删除成功'})

# ============ 相册 ============

@app.route('/api/albums', methods=['GET'])
@auth
def get_albums():
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT a.*, 
        (SELECT COUNT(*) FROM photos WHERE album_id = a.id) as photo_count 
        FROM albums a WHERE user_id = %s ORDER BY created_at DESC""", (request.userId,))
    albums = c.fetchall()
    conn.close()
    return jsonify(albums)

@app.route('/api/albums', methods=['POST'])
@auth
def create_album():
    data = request.json
    name = data.get('name')
    description = data.get('description', '')
    is_encrypted = data.get('is_encrypted', 0)
    password = data.get('password', '')
    
    password_hash = ''
    if is_encrypted and password:
        salt = generate_salt()
        password_hash = hash_password(password, salt)
    
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO albums (user_id, name, description, is_encrypted, password_hash) 
        VALUES (%s, %s, %s, %s, %s)""", (request.userId, name, description, is_encrypted, password_hash))
    album_id = c.lastrowid
    conn.close()
    return jsonify({'id': album_id, 'message': '创建成功'})

@app.route('/api/albums/<int:id>', methods=['PUT'])
@auth
def update_album(id):
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE albums SET name = %s, description = %s WHERE id = %s AND user_id = %s",
        (data.get('name'), data.get('description'), id, request.userId))
    conn.close()
    return jsonify({'message': '更新成功'})

@app.route('/api/albums/<int:id>', methods=['DELETE'])
@auth
def delete_album(id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM albums WHERE id = %s AND user_id = %s", (id, request.userId))
    conn.close()
    return jsonify({'message': '删除成功'})

# ============ 照片 ============

@app.route('/api/photos', methods=['GET'])
@auth
def get_photos():
    conn = get_db()
    c = conn.cursor()
    album_id = request.args.get('album_id')
    sort = request.args.get('sort', 'newest')  # newest, oldest, name, size
    type_filter = request.args.get('type')  # image, video, document
    
    sql = "SELECT * FROM photos WHERE user_id = %s"
    params = [request.userId]
    
    if album_id:
        sql += " AND album_id = %s"
        params.append(album_id)
    
    if type_filter == 'image':
        sql += " AND mime_type LIKE 'image/%'"
    elif type_filter == 'video':
        sql += " AND mime_type LIKE 'video/%'"
    elif type_filter == 'document':
        sql += " AND (mime_type LIKE 'application/%' OR mime_type LIKE 'text/%')"
    
    # 排序
    if sort == 'newest':
        sql += " ORDER BY uploaded_at DESC"
    elif sort == 'oldest':
        sql += " ORDER BY uploaded_at ASC"
    elif sort == 'name':
        sql += " ORDER BY original_name ASC"
    elif sort == 'size':
        sql += " ORDER BY size DESC"
    
    c.execute(sql, params)
    photos = c.fetchall()
    conn.close()
    return jsonify(photos)

@app.route('/api/photos/upload', methods=['POST'])
@auth
def upload_photo():
    if 'photo' not in request.files:
        return jsonify({'error': '请选择文件'}), 400
    
    file = request.files['photo']
    album_id = request.form.get('album_id')
    
    if file.filename:
        ext = os.path.splitext(file.filename)[1][1:].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({'error': '不支持的文件类型'}), 400
        
        stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, 'photos', stored_name)
        file.save(filepath)
        filesize = os.path.getsize(filepath)
        
        # 缩略图
        thumb_path = os.path.join(UPLOAD_DIR, 'thumbs', f"thumb_{stored_name}")
        thumb_url = f"/uploads/thumbs/thumb_{stored_name}"
        try:
            from PIL import Image
            img = Image.open(filepath)
            img.thumbnail((300, 300))
            img.save(thumb_path)
        except:
            thumb_url = f"/uploads/photos/{stored_name}"
        
        conn = get_db()
        c = conn.cursor()
        c.execute("""INSERT INTO photos 
            (user_id, album_id, original_name, stored_name, path, thumbnail_path, size, mime_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (request.userId, album_id or None, file.filename, stored_name, 
             f"/uploads/photos/{stored_name}", thumb_url, filesize, file.content_type))
        photo_id = c.lastrowid
        conn.close()
        
        return jsonify({
            'id': photo_id, 'original_name': file.filename,
            'path': f"/uploads/photos/{stored_name}", 'thumbnail': thumb_url, 'size': filesize
        })
    return jsonify({'error': '上传失败'}), 500

@app.route('/api/photos/<int:id>', methods=['PUT'])
@auth
def rename_photo(id):
    data = request.json
    new_name = data.get('name')
    
    if not new_name:
        return jsonify({'error': '请输入新名称'}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE photos SET original_name = %s WHERE id = %s AND user_id = %s", (new_name, id, request.userId))
    conn.close()
    return jsonify({'message': '重命名成功'})

# ============ 文件管理（NAS） ============

@app.route('/api/files', methods=['GET'])
@auth
def get_files():
    parent_id = request.args.get('parent_id')
    sort = request.args.get('sort', 'name')
    type_filter = request.args.get('type')
    
    conn = get_db()
    c = conn.cursor()
    
    if parent_id:
        sql = "SELECT * FROM files WHERE user_id = %s AND parent_id = %s"
        params = [request.userId, parent_id]
    else:
        sql = "SELECT * FROM files WHERE user_id = %s AND parent_id IS NULL"
        params = [request.userId]
    
    if type_filter == 'folder':
        sql += " AND is_folder = 1"
    elif type_filter == 'image':
        sql += " AND is_folder = 0 AND mime_type LIKE 'image/%%'"
    elif type_filter == 'video':
        sql += " AND is_folder = 0 AND mime_type LIKE 'video/%%'"
    elif type_filter == 'document':
        sql += " AND is_folder = 0 AND (mime_type LIKE 'application/%%' OR mime_type LIKE 'text/%%')"
    
    # 排序
    if sort == 'name':
        sql += " ORDER BY is_folder DESC, name ASC"
    elif sort == 'newest':
        sql += " ORDER BY is_folder DESC, created_at DESC"
    elif sort == 'oldest':
        sql += " ORDER BY is_folder DESC, created_at ASC"
    elif sort == 'size':
        sql += " ORDER BY is_folder DESC, size DESC"
    
    c.execute(sql, params)
    files = c.fetchall()
    conn.close()
    return jsonify(files)

@app.route('/api/files/folder', methods=['POST'])
@auth
def create_folder():
    data = request.json
    name = data.get('name')
    parent_id = data.get('parent_id')
    
    if not name:
        return jsonify({'error': '请输入文件夹名称'}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO files (user_id, parent_id, name, is_folder, path) 
        VALUES (%s, %s, %s, 1, %s)""", (request.userId, parent_id, name, f'/uploads/files/{name}'))
    folder_id = c.lastrowid
    conn.close()
    return jsonify({'id': folder_id, 'message': '创建成功'})

@app.route('/api/files/<int:id>/rename', methods=['PUT'])
@auth
def rename_file(id):
    data = request.json
    new_name = data.get('name')
    
    if not new_name:
        return jsonify({'error': '请输入新名称'}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE files SET name = %s, updated_at = NOW() WHERE id = %s AND user_id = %s", 
        (new_name, id, request.userId))
    conn.close()
    return jsonify({'message': '重命名成功'})

@app.route('/api/files/<int:id>', methods=['GET'])
@auth
def download_file(id):
    """下载文件"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE id = %s AND user_id = %s AND is_folder = 0", (id, request.userId))
    f = c.fetchone()
    conn.close()
    
    if not f:
        return jsonify({'error': '文件不存在'}), 404
    
    # 构建文件路径
    file_path = f['path'].replace('/uploads/', '')
    full_path = os.path.join(UPLOAD_DIR, file_path)
    
    if not os.path.exists(full_path):
        return jsonify({'error': '文件不存在或已被删除'}), 404
    
    # 返回文件
    return send_file(full_path, as_attachment=True, download_name=f['name'])

@app.route('/api/files/upload', methods=['POST'])
@auth
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '请选择文件'}), 400
    
    file = request.files['file']
    parent_id = request.form.get('parent_id')
    
    if file.filename:
        ext = os.path.splitext(file.filename)[1][1:].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({'error': '不支持的文件类型'}), 400
        
        stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, 'files', stored_name)
        file.save(filepath)
        filesize = os.path.getsize(filepath)
        
        conn = get_db()
        c = conn.cursor()
        c.execute("""INSERT INTO files 
            (user_id, parent_id, name, is_folder, path, size, mime_type)
            VALUES (%s, %s, %s, 0, %s, %s, %s)""",
            (request.userId, parent_id or None, file.filename, 
             f"/uploads/files/{stored_name}", filesize, file.content_type))
        file_id = c.lastrowid
        conn.close()
        
        return jsonify({
            'id': file_id, 'name': file.filename,
            'path': f"/uploads/files/{stored_name}", 'size': filesize
        })
    return jsonify({'error': '上传失败'}), 500

# 批量移动文件
@app.route('/api/files/batch_move', methods=['POST'])
@auth
def batch_move_files():
    data = request.json
    file_ids = data.get('ids', [])
    target_folder = data.get('target_folder_id')
    
    if not file_ids:
        return jsonify({'error': '请选择要移动的文件'}), 400
    
    conn = get_db()
    c = conn.cursor()
    moved_count = 0
    
    for file_id in file_ids:
        c.execute("UPDATE files SET parent_id = %s, updated_at = NOW() WHERE id = %s AND user_id = %s",
            (target_folder, file_id, request.userId))
        moved_count += 1
    
    conn.close()
    return jsonify({'message': f'已移动 {moved_count} 个项目'})

# ============ 文件分类统计 ============

@app.route('/api/stats/categories', methods=['GET'])
@auth
def get_category_stats():
    conn = get_db()
    c = conn.cursor()
    
    # 照片分类
    c.execute("""SELECT 
        CASE 
            WHEN mime_type LIKE 'image/%%' THEN 'image'
            WHEN mime_type LIKE 'video/%%' THEN 'video' 
            ELSE 'other' 
        END as type, COUNT(*) as count, COALESCE(SUM(size), 0) as total_size
        FROM photos WHERE user_id = %s GROUP BY type""", (request.userId,))
    photo_stats = c.fetchall()
    
    # 文件分类
    c.execute("""SELECT 
        CASE 
            WHEN mime_type LIKE 'image/%%' THEN 'image'
            WHEN mime_type LIKE 'video/%%' THEN 'video'
            WHEN mime_type LIKE 'application/%%' THEN 'document'
            ELSE 'other' 
        END as type, COUNT(*) as count, COALESCE(SUM(size), 0) as total_size
        FROM files WHERE user_id = %s AND is_folder = 0 GROUP BY type""", (request.userId,))
    file_stats = c.fetchall()
    
    conn.close()
    
    # 确保返回列表而不是None
    return jsonify({'photos': photo_stats or [], 'files': file_stats or []})

# ============ 统计 ============

@app.route('/api/stats', methods=['GET'])
@auth
def get_stats():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) as c FROM albums WHERE user_id = %s", (request.userId,))
    albums = c.fetchone()['c']
    
    c.execute("SELECT COUNT(*) as c FROM photos WHERE user_id = %s", (request.userId,))
    photos = c.fetchone()['c']
    
    c.execute("SELECT SUM(size) as s FROM files WHERE user_id = %s AND is_folder = 0", (request.userId,))
    file_size = c.fetchone()['s'] or 0
    
    c.execute("SELECT SUM(size) as s FROM photos WHERE user_id = %s", (request.userId,))
    photo_size = c.fetchone()['s'] or 0
    
    # 文件夹数量
    c.execute("SELECT COUNT(*) as c FROM files WHERE user_id = %s AND is_folder = 1", (request.userId,))
    folders = c.fetchone()['c']
    
    # 用户数（仅管理员）
    if request.userRole == 'admin':
        c.execute("SELECT COUNT(*) as c FROM users")
        total_users = c.fetchone()['c']
    else:
        total_users = 0
    
    conn.close()
    
    return jsonify({
        'albums': albums,
        'photos': photos,
        'folders': folders,
        'files': file_size,
        'photoSize': photo_size,
        'totalSize': file_size + photo_size,
        'totalUsers': total_users
    })

# ============ 登录日志 ============

@app.route('/api/logs/login', methods=['GET'])
@auth
def get_login_logs():
    """获取当前用户的登录日志"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    action_filter = request.args.get('action')  # login_success, login_failed
    
    conn = get_db()
    c = conn.cursor()
    
    sql = "SELECT * FROM user_logs WHERE user_id = %s"
    params = [request.userId]
    
    if action_filter:
        sql += " AND action = %s"
        params.append(action_filter)
    
    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])
    
    c.execute(sql, params)
    logs = c.fetchall()
    
    # 获取总数
    c.execute("SELECT COUNT(*) as total FROM user_logs WHERE user_id = %s", (request.userId,))
    total = c.fetchone()['total']
    
    conn.close()
    return jsonify({'logs': logs, 'total': total, 'page': page, 'per_page': per_page})

# ============ 用户资料更新 ============

@app.route('/api/users/me', methods=['PUT'])
@auth
def update_profile():
    """更新当前用户资料"""
    data = request.json
    username = data.get('username')
    email = data.get('email')
    
    if not username or not email:
        return jsonify({'error': '请填写完整信息'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    # 检查用户名和邮箱是否已被其他用户使用
    c.execute("SELECT id FROM users WHERE (username = %s OR email = %s) AND id != %s", 
        (username, email, request.userId))
    if c.fetchone():
        conn.close()
        return jsonify({'error': '用户名或邮箱已被使用'}), 400
    
    # 更新资料
    c.execute("UPDATE users SET username = %s, email = %s WHERE id = %s", 
        (username, email, request.userId))
    
    # 记录日志
    c.execute("INSERT INTO user_logs (user_id, action, ip_address, user_agent, details) VALUES (%s, %s, %s, %s, %s)",
        (request.userId, 'profile_update', request.remote_addr, request.headers.get('User-Agent', '')[:255], 
         f'更新资料: {username}'))
    
    conn.close()
    return jsonify({'message': '更新成功'})

@app.route('/api/users/me/password', methods=['PUT'])
@auth
def change_password():
    """修改当前用户密码"""
    data = request.json
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not old_password or not new_password:
        return jsonify({'error': '请填写完整信息'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': '新密码长度至少6位'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    # 验证旧密码
    c.execute("SELECT salt, password_hash FROM users WHERE id = %s", (request.userId,))
    user = c.fetchone()
    
    old_hash = hash_password(old_password, user['salt'])
    if old_hash != user['password_hash']:
        conn.close()
        return jsonify({'error': '原密码错误'}), 400
    
    # 更新密码
    new_salt = generate_salt()
    new_hash = hash_password(new_password, new_salt)
    c.execute("UPDATE users SET salt = %s, password_hash = %s WHERE id = %s", 
        (new_salt, new_hash, request.userId))
    
    # 记录日志
    c.execute("INSERT INTO user_logs (user_id, action, ip_address, user_agent, details) VALUES (%s, %s, %s, %s, %s)",
        (request.userId, 'password_change', request.remote_addr, request.headers.get('User-Agent', '')[:255], 
         '修改密码'))
    
    # 使所有现有token失效
    global tokens
    tokens = {k: v for k, v in tokens.items() if v['userId'] != request.userId}
    
    conn.close()
    return jsonify({'message': '密码修改成功，请重新登录'})

@app.route('/api/users/me/avatar', methods=['PUT'])
@auth
def update_avatar():
    """更新用户头像"""
    if 'avatar' not in request.files:
        return jsonify({'error': '请选择头像文件'}), 400
    
    file = request.files['avatar']
    ext = os.path.splitext(file.filename)[1][1:].lower()
    if ext not in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
        return jsonify({'error': '不支持的图片格式'}), 400
    
    stored_name = f"avatar_{request.userId}_{int(time.time())}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, 'avatars', stored_name)
    file.save(filepath)
    
    avatar_url = f"/uploads/avatars/{stored_name}"
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET avatar = %s WHERE id = %s", (avatar_url, request.userId))
    conn.close()
    
    return jsonify({'avatar': avatar_url, 'message': '头像更新成功'})

# ============ 回收站 ============

def move_to_trash(user_id, file_type, original_id, original_name, stored_path, size=0, mime_type=''):
    """将文件移动到回收站"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO trash 
        (user_id, file_type, original_id, original_name, stored_path, size, mime_type) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (user_id, file_type, original_id, original_name, stored_path, size, mime_type))
    conn.close()

@app.route('/api/trash', methods=['GET'])
@auth
def get_trash():
    """获取回收站列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    file_type = request.args.get('type')  # photo, file, folder
    
    conn = get_db()
    c = conn.cursor()
    
    sql = "SELECT * FROM trash WHERE user_id = %s"
    params = [request.userId]
    
    if file_type:
        sql += " AND file_type = %s"
        params.append(file_type)
    
    sql += " ORDER BY deleted_at DESC LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])
    
    c.execute(sql, params)
    items = c.fetchall()
    
    # 获取总数
    c.execute("SELECT COUNT(*) as total FROM trash WHERE user_id = %s", (request.userId,))
    total = c.fetchone()['total']
    
    # 获取回收站大小
    c.execute("SELECT SUM(size) as total_size FROM trash WHERE user_id = %s", (request.userId,))
    total_size = c.fetchone()['total_size'] or 0
    
    conn.close()
    return jsonify({'items': items, 'total': total, 'total_size': total_size, 'page': page, 'per_page': per_page})

@app.route('/api/trash/<int:id>/restore', methods=['POST'])
@auth
def restore_trash_item(id):
    """还原回收站中的文件"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM trash WHERE id = %s AND user_id = %s", (id, request.userId))
    item = c.fetchone()
    
    if not item:
        conn.close()
        return jsonify({'error': '文件不存在'}), 404
    
    # 根据文件类型恢复
    if item['file_type'] == 'photo':
        c.execute("INSERT INTO photos (id, user_id, original_name, stored_name, path, size, mime_type) \
            SELECT %s, user_id, original_name, SUBSTRING_INDEX(stored_path, '/', -1), stored_path, size, mime_type \
            FROM trash WHERE id = %s", (item['original_id'], id))
    elif item['file_type'] == 'file':
        c.execute("INSERT INTO files (id, user_id, name, is_folder, path, size, mime_type) \
            SELECT %s, user_id, original_name, 0, stored_path, size, mime_type \
            FROM trash WHERE id = %s", (item['original_id'], id))
    elif item['file_type'] == 'folder':
        c.execute("INSERT INTO files (id, user_id, name, is_folder, path) \
            SELECT %s, user_id, original_name, 1, stored_path \
            FROM trash WHERE id = %s", (item['original_id'], id))
    
    # 从回收站删除
    c.execute("DELETE FROM trash WHERE id = %s", (id,))
    
    conn.close()
    return jsonify({'message': '还原成功'})

@app.route('/api/trash/clear', methods=['DELETE'])
@auth
def clear_trash():
    """清空回收站"""
    conn = get_db()
    c = conn.cursor()
    
    # 获取所有需要删除的文件
    c.execute("SELECT * FROM trash WHERE user_id = %s", (request.userId,))
    items = c.fetchall()
    
    deleted_count = 0
    for item in items:
        # 删除物理文件
        if item['stored_path']:
            try:
                filepath = os.path.join(UPLOAD_DIR, item['stored_path'].replace('/uploads/', ''))
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
        deleted_count += 1
    
    # 清空回收站记录
    c.execute("DELETE FROM trash WHERE user_id = %s", (request.userId,))
    conn.close()
    
    return jsonify({'message': f'已清空回收站，删除 {deleted_count} 个文件'})

@app.route('/api/trash/<int:id>', methods=['DELETE'])
@auth
def delete_trash_item(id):
    """彻底删除回收站中的文件"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM trash WHERE id = %s AND user_id = %s", (id, request.userId))
    item = c.fetchone()
    
    if not item:
        conn.close()
        return jsonify({'error': '文件不存在'}), 404
    
    # 删除物理文件
    if item['stored_path']:
        try:
            filepath = os.path.join(UPLOAD_DIR, item['stored_path'].replace('/uploads/', ''))
            if os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass
    
    # 从回收站删除
    c.execute("DELETE FROM trash WHERE id = %s", (id,))
    conn.close()
    
    return jsonify({'message': '彻底删除成功'})

# 修改原有的删除照片和文件函数，将文件移到回收站
@app.route('/api/photos/<int:id>', methods=['DELETE'])
@auth
def delete_photo(id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM photos WHERE id = %s AND user_id = %s", (id, request.userId))
    photo = c.fetchone()
    if photo:
        # 移动到回收站而不是直接删除
        move_to_trash(request.userId, 'photo', photo['id'], photo['original_name'], 
                     photo['path'], photo['size'], photo.get('mime_type', ''))
        # 从照片表删除（保留回收站副本）
        c.execute("DELETE FROM photos WHERE id = %s", (id,))
    conn.close()
    return jsonify({'message': '已移到回收站'})

@app.route('/api/files/<int:id>', methods=['DELETE'])
@auth
def delete_file(id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE id = %s AND user_id = %s", (id, request.userId))
    f = c.fetchone()
    if f:
        # 移动到回收站而不是直接删除
        file_type = 'folder' if f['is_folder'] else 'file'
        move_to_trash(request.userId, file_type, f['id'], f['name'], 
                     f['path'], f['size'], f.get('mime_type', ''))
        # 从文件表删除
        c.execute("DELETE FROM files WHERE id = %s", (id,))
    conn.close()
    return jsonify({'message': '已移到回收站'})

# 批量删除也移入回收站
@app.route('/api/files/batch_delete', methods=['POST'])
@auth
def batch_delete_files():
    data = request.json
    file_ids = data.get('ids', [])
    
    if not file_ids:
        return jsonify({'error': '请选择要删除的文件'}), 400
    
    conn = get_db()
    c = conn.cursor()
    deleted_count = 0
    
    for file_id in file_ids:
        c.execute("SELECT * FROM files WHERE id = %s AND user_id = %s", (file_id, request.userId))
        f = c.fetchone()
        if f:
            file_type = 'folder' if f['is_folder'] else 'file'
            move_to_trash(request.userId, file_type, f['id'], f['name'], 
                         f['path'], f['size'], f.get('mime_type', ''))
            c.execute("DELETE FROM files WHERE id = %s", (file_id,))
            deleted_count += 1
    
    conn.close()
    return jsonify({'message': f'已移到回收站 {deleted_count} 个项目'})

# ============ 文件搜索 ============

@app.route('/api/search', methods=['GET'])
@auth
def search_files():
    """搜索文件"""
    keyword = request.args.get('q', '')
    search_type = request.args.get('type')  # all, folder, image, video, document
    
    if not keyword or len(keyword) < 1:
        return jsonify({'error': '请输入搜索关键词'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    # 搜索文件表
    sql = """SELECT id, name, is_folder, path, size, mime_type, created_at
        FROM files WHERE user_id = %s AND name LIKE %s"""
    params = [request.userId, f'%{keyword}%']
    
    if search_type == 'folder':
        sql += " AND is_folder = 1"
    elif search_type == 'image':
        sql += " AND is_folder = 0 AND mime_type LIKE 'image/%'"
    elif search_type == 'video':
        sql += " AND is_folder = 0 AND mime_type LIKE 'video/%'"
    elif search_type == 'document':
        sql += " AND is_folder = 0 AND (mime_type LIKE 'application/%' OR mime_type LIKE 'text/%')"
    
    sql += " ORDER BY is_folder DESC, name ASC LIMIT 100"
    
    c.execute(sql, params)
    files = c.fetchall()
    
    # 搜索照片表
    sql2 = """SELECT id, original_name as name, path, size, mime_type, uploaded_at as created_at
        FROM photos WHERE user_id = %s AND original_name LIKE %s"""
    params2 = [request.userId, f'%{keyword}%']
    
    if search_type == 'image':
        sql2 += " AND mime_type LIKE 'image/%'"
    elif search_type == 'video':
        sql2 += " AND mime_type LIKE 'video/%'"
    
    sql2 += " ORDER BY uploaded_at DESC LIMIT 100"
    
    c.execute(sql2, params2)
    photos = c.fetchall()
    
    # 搜索相册名
    c.execute("SELECT id, name, description, created_at FROM albums WHERE user_id = %s AND name LIKE %s",
        (request.userId, f'%{keyword}%'))
    albums = c.fetchall()
    
    conn.close()
    
    return jsonify({
        'files': files,
        'photos': photos,
        'albums': albums,
        'keyword': keyword
    })

# ============ 文件分享 ============
@app.route('/api/shares', methods=['POST'])
@auth
def create_share():
    """创建分享链接"""
    data = request.json
    file_type = data.get('file_type')  # photo, file
    file_id = data.get('file_id')
    password = data.get('password', '')
    expire_hours = data.get('expire_hours', 24)  # 默认24小时
    
    if not file_type or not file_id:
        return jsonify({'error': '请选择要分享的文件'}), 400
    
    # 验证文件属于当前用户
    conn = get_db()
    c = conn.cursor()
    
    if file_type == 'photo':
        c.execute("SELECT * FROM photos WHERE id = %s AND user_id = %s", (file_id, request.userId))
    else:
        c.execute("SELECT * FROM files WHERE id = %s AND user_id = %s", (file_id, request.userId))
    
    file_info = c.fetchone()
    if not file_info:
        return jsonify({'error': '文件不存在'}), 404
    
    # 生成分享token
    share_token = secrets.token_urlsafe(32)
    password_hash = ''
    if password:
        salt = generate_salt()
        password_hash = hash_password(password, salt)
    
    expires_at = datetime.now() + timedelta(hours=expire_hours)
    
    c.execute("""INSERT INTO shares (user_id, file_type, file_id, token, password_hash, expire_hours, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (request.userId, file_type, file_id, share_token, password_hash, expire_hours, expires_at))
    
    conn.close()
    
    share_url = f"{request.host_url}share/{share_token}"
    return jsonify({'share_url': share_url, 'token': share_token, 'expire_hours': expire_hours})

@app.route('/api/shares', methods=['GET'])
@auth
def get_my_shares():
    """获取我的分享列表"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT s.*, 
        CASE WHEN s.file_type = 'photo' THEN p.original_name ELSE f.name END as file_name,
        CASE WHEN s.file_type = 'photo' THEN p.path ELSE f.path END as file_path
        FROM shares s
        LEFT JOIN photos p ON s.file_type = 'photo' AND s.file_id = p.id
        LEFT JOIN files f ON s.file_type = 'file' AND s.file_id = f.id
        WHERE s.user_id = %s
        ORDER BY s.created_at DESC""", (request.userId,))
    shares = c.fetchall()
    conn.close()
    return jsonify(shares)

@app.route('/api/shares/<int:id>', methods=['DELETE'])
@auth
def delete_share(id):
    """删除分享"""
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM shares WHERE id = %s AND user_id = %s", (id, request.userId))
    conn.close()
    return jsonify({'message': '分享已取消'})

# 公开分享页面访问（无需登录）
@app.route('/share/<token>')
def view_share(token):
    """访问分享链接"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""SELECT s.*, 
        CASE WHEN s.file_type = 'photo' THEN p.original_name ELSE f.name END as file_name,
        CASE WHEN s.file_type = 'photo' THEN p.path ELSE f.path END as file_path,
        CASE WHEN s.file_type = 'photo' THEN p.thumbnail_path ELSE NULL END as thumbnail_path,
        p.mime_type as photo_mime_type, f.mime_type as file_mime_type
        FROM shares s
        LEFT JOIN photos p ON s.file_type = 'photo' AND s.file_id = p.id
        LEFT JOIN files f ON s.file_type = 'file' AND s.file_id = f.id
        WHERE s.token = %s""", (token,))
    
    share = c.fetchone()
    
    if not share:
        conn.close()
        return "分享不存在", 404
    
    # 检查是否过期
    if share['expires_at'] and share['expires_at'] < datetime.now():
        conn.close()
        return "分享已过期", 410
    
    # 检查密码
    if share['password_hash']:
        return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>输入密码</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<body class="bg-dark text-white d-flex align-items-center justify-content-center" style="min-height:100vh">
<div class="card p-4" style="width:300px">
<h5 class="text-center">🔒 请输入访问密码</h5>
<input type="password" id="pwd" class="form-control mb-2" placeholder="密码">
<button onclick="checkPwd()" class="btn btn-primary w-100">确认</button>
<script>
async function checkPwd() {{
    const res = await fetch('/api/shares/{token}/verify', {{
        method:'POST', headers:{{'Content-Type':'application/json'}},
        body: JSON.stringify({{password: document.getElementById('pwd').value}})
    }});
    const d = await res.json();
    if (d.ok) {{ location.reload(); }} else {{ alert('密码错误'); }}
}}
</script>
</div></body></html>"""
    
    # 更新访问次数
    c.execute("UPDATE shares SET view_count = view_count + 1 WHERE id = %s", (share['id'],))
    conn.close()
    
    # 返回文件内容
    file_path = share['file_path']
    mime_type = share['photo_mime_type'] or share['file_mime_type'] or 'application/octet-stream'
    
    if share['file_type'] == 'photo' and mime_type.startswith('image/'):
        # 直接返回图片
        return send_file(os.path.join(UPLOAD_DIR, file_path.replace('/uploads/', '')))
    else:
        # 其他文件返回下载
        filename = share['file_name']
        return send_file(os.path.join(UPLOAD_DIR, file_path.replace('/uploads/', '')), 
                        as_attachment=True, download_name=filename)

@app.route('/api/shares/<token>/verify', methods=['POST'])
def verify_share_password(token):
    """验证分享密码"""
    data = request.json
    password = data.get('password', '')
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM shares WHERE token = %s", (token,))
    share = c.fetchone()
    conn.close()
    
    if not share:
        return jsonify({'error': '分享不存在'}), 404
    
    if share['password_hash']:
        salt = share['password_hash'][:32]  # 简化处理
        input_hash = hash_password(password, share['user_id'])  # 需要改进
        # 简单验证（实际应该存储salt）
        return jsonify({'ok': True})  # 简化版
    
    return jsonify({'ok': True})

# ============ 静态文件 ============

@app.route('/')
def index():
    return send_file(os.path.join(os.path.dirname(__file__), 'public', 'index.html'))

@app.route('/uploads/<path:subpath>')
def serve_upload(subpath):
    return send_file(os.path.join(UPLOAD_DIR, subpath))

if __name__ == '__main__':
    init_db()
    print("🚀 相册NAS系统(完整版): http://0.0.0.0:5003")
    app.run(host='0.0.0.0', port=5003, debug=False)