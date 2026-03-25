require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const path = require('path');
const fs = require('fs');
const mysql = require('mysql2/promise');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const multer = require('multer');

const app = express();
const PORT = process.env.PORT || 5003;

// 中间件
app.use(cors({ origin: true, credentials: true }));
app.use(helmet({ crossOriginResourcePolicy: false }));
app.use(morgan('dev'));
app.use(express.json());

// 静态文件
const UPLOAD_DIR = process.env.UPLOAD_DIR || '/mnt/windows_share/album_nas/uploads';
fs.mkdirSync(path.join(UPLOAD_DIR, 'photos'), { recursive: true });
fs.mkdirSync(path.join(UPLOAD_DIR, 'thumbs'), { recursive: true });
fs.mkdirSync(path.join(UPLOAD_DIR, 'files'), { recursive: true });
fs.mkdirSync(path.join(UPLOAD_DIR, 'avatars'), { recursive: true });

app.use('/uploads', express.static(UPLOAD_DIR));

// 数据库连接
const pool = mysql.createPool({
    host: process.env.DB_HOST,
    user: process.env.DB_USER,
    password: process.env.DB_PASS,
    database: process.env.DB_NAME,
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
});

// 初始化数据库
async function initDatabase() {
    try {
        const conn = await pool.getConnection();
        
        // 用户表
        await conn.query(`CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            email VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            avatar VARCHAR(255),
            role ENUM('admin', 'user') DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_username (username),
            INDEX idx_email (email)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`);

        // 相册表
        await conn.query(`CREATE TABLE IF NOT EXISTS albums (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            cover_photo_id INT,
            is_public TINYINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`);

        // 照片表
        await conn.query(`CREATE TABLE IF NOT EXISTS photos (
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
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE SET NULL,
            INDEX idx_user (user_id),
            INDEX idx_album (album_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`);

        // 文件表
        await conn.query(`CREATE TABLE IF NOT EXISTS files (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            parent_id INT DEFAULT NULL,
            name VARCHAR(255) NOT NULL,
            is_folder TINYINT DEFAULT 0,
            path VARCHAR(500) NOT NULL,
            size INT,
            mime_type VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES files(id) ON DELETE CASCADE,
            INDEX idx_user (user_id),
            INDEX idx_parent (parent_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`);

        // 检查是否有admin用户
        const [rows] = await conn.query('SELECT id FROM users WHERE username = ?', ['admin']);
        if (rows.length === 0) {
            const hashedPassword = await bcrypt.hash('admin123', 10);
            await conn.query('INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ['admin', 'admin@example.com', hashedPassword, 'admin']);
            console.log('✅ 默认管理员账号已创建');
        }

        conn.release();
        console.log('✅ 数据库初始化完成');
    } catch (err) {
        console.error('数据库初始化失败:', err.message);
    }
}

// JWT认证中间件
const auth = (req, res, next) => {
    const token = req.header('Authorization')?.replace('Bearer ', '');
    if (!token) return res.status(401).json({ error: '请先登录' });
    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        req.userId = decoded.userId;
        req.userRole = decoded.role;
        next();
    } catch (err) {
        res.status(401).json({ error: '登录已过期' });
    }
};

// 上传配置
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        const type = req.uploadType || 'photos';
        cb(null, path.join(UPLOAD_DIR, type));
    },
    filename: (req, file, cb) => {
        const uniqueName = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}${path.extname(file.originalname)}`;
        cb(null, uniqueName);
    }
});

const upload = multer({
    storage,
    limits: { fileSize: 100 * 1024 * 1024 }, // 100MB
    fileFilter: (req, file, cb) => {
        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'video/mp4', 'application/pdf'];
        if (allowedTypes.includes(file.mimetype)) {
            cb(null, true);
        } else {
            cb(new Error('不支持的文件类型'));
        }
    }
});

// ============ 认证路由 ============

// 注册
app.post('/api/auth/register', async (req, res) => {
    try {
        const { username, email, password } = req.body;
        const hashedPassword = await bcrypt.hash(password, 10);
        
        const [result] = await pool.query(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            [username, email, hashedPassword]
        );
        res.status(201).json({ id: result.insertId, message: '注册成功' });
    } catch (err) {
        res.status(400).json({ error: '用户名或邮箱已存在' });
    }
});

// 登录
app.post('/api/auth/login', async (req, res) => {
    try {
        const { email, password } = req.body;
        const [rows] = await pool.query('SELECT * FROM users WHERE email = ?', [email]);
        
        if (rows.length === 0) return res.status(401).json({ error: '用户不存在' });
        
        const user = rows[0];
        const valid = await bcrypt.compare(password, user.password_hash);
        if (!valid) return res.status(401).json({ error: '密码错误' });
        
        const token = jwt.sign(
            { userId: user.id, role: user.role, username: user.username },
            process.env.JWT_SECRET,
            { expiresIn: '7d' }
        );
        
        res.json({
            token,
            user: { id: user.id, username: user.username, email: user.email, role: user.role, avatar: user.avatar }
        });
    } catch (err) {
        res.status(500).json({ error: '登录失败' });
    }
});

// 检查登录状态
app.get('/api/auth/check', auth, async (req, res) => {
    const [rows] = await pool.query('SELECT id, username, email, role, avatar FROM users WHERE id = ?', [req.userId]);
    if (rows.length === 0) return res.status(404).json({ error: '用户不存在' });
    res.json({ logged_in: true, user: rows[0] });
});

// ============ 相册路由 ============

// 获取相册列表
app.get('/api/albums', auth, async (req, res) => {
    try {
        const [rows] = await pool.query(
            'SELECT a.*, (SELECT COUNT(*) FROM photos WHERE album_id = a.id) as photo_count FROM albums a WHERE a.user_id = ? ORDER BY a.created_at DESC',
            [req.userId]
        );
        
        // 获取每个相册的封面照片
        for (let album of rows) {
            if (album.cover_photo_id) {
                const [photos] = await pool.query('SELECT thumbnail_path FROM photos WHERE id = ?', [album.cover_photo_id]);
                album.cover = photos.length > 0 ? photos[0].thumbnail_path : null;
            }
        }
        res.json(rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// 创建相册
app.post('/api/albums', auth, async (req, res) => {
    try {
        const { name, description } = req.body;
        const [result] = await pool.query(
            'INSERT INTO albums (user_id, name, description) VALUES (?, ?, ?)',
            [req.userId, name, description || '']
        );
        res.json({ id: result.insertId, message: '相册创建成功' });
    } catch (err) {
        res.status(500).json({ error: '创建失败' });
    }
});

// 删除相册
app.delete('/api/albums/:id', auth, async (req, res) => {
    try {
        await pool.query('DELETE FROM albums WHERE id = ? AND user_id = ?', [req.params.id, req.userId]);
        res.json({ message: '删除成功' });
    } catch (err) {
        res.status(500).json({ error: '删除失败' });
    }
});

// ============ 照片路由 ============

// 获取照片列表
app.get('/api/photos', auth, async (req, res) => {
    try {
        const { album_id } = req.query;
        let sql = 'SELECT * FROM photos WHERE user_id = ?';
        let params = [req.userId];
        
        if (album_id) {
            sql += ' AND album_id = ?';
            params.push(album_id);
        }
        
        sql += ' ORDER BY uploaded_at DESC';
        const [rows] = await pool.query(sql, params);
        res.json(rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// 上传照片
app.post('/api/photos/upload', auth, (req, res) => {
    req.uploadType = 'photos';
    
    upload.single('photo')(req, res, async (err) => {
        if (err) return res.status(400).json({ error: err.message });
        
        try {
            const { album_id } = req.body;
            const file = req.file;
            
            if (!file) return res.status(400).json({ error: '请选择文件' });
            
            const storedName = file.filename;
            const thumbName = 'thumb-' + storedName;
            const thumbPath = '/uploads/thumbs/' + thumbName;
            
            // 生成缩略图
            try {
                const sharp = require('sharp');
                await sharp(file.path)
                    .resize(300, 300, { fit: 'cover' })
                    .toFile(path.join(UPLOAD_DIR, 'thumbs', thumbName));
            } catch (e) {
                console.log('缩略图生成失败:', e.message);
            }
            
            // 保存到数据库
            const [result] = await pool.query(
                `INSERT INTO photos (user_id, album_id, original_name, stored_name, path, thumbnail_path, size, mime_type)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
                [req.userId, album_id || null, file.originalname, storedName, '/uploads/photos/' + storedName, thumbPath, file.size, file.mimetype]
            );
            
            res.json({
                id: result.insertId,
                original_name: file.originalname,
                path: '/uploads/photos/' + storedName,
                thumbnail: thumbPath
            });
        } catch (err) {
            res.status(500).json({ error: '上传失败' });
        }
    });
});

// 删除照片
app.delete('/api/photos/:id', auth, async (req, res) => {
    try {
        const [rows] = await pool.query('SELECT * FROM photos WHERE id = ? AND user_id = ?', [req.params.id, req.userId]);
        if (rows.length === 0) return res.status(404).json({ error: '文件不存在' });
        
        const photo = rows[0];
        
        // 删除物理文件
        try {
            fs.unlinkSync(path.join(UPLOAD_DIR, 'photos', photo.stored_name));
            fs.unlinkSync(path.join(UPLOAD_DIR, 'thumbs', 'thumb-' + photo.stored_name));
        } catch (e) {}
        
        await pool.query('DELETE FROM photos WHERE id = ?', [req.params.id]);
        res.json({ message: '删除成功' });
    } catch (err) {
        res.status(500).json({ error: '删除失败' });
    }
});

// ============ 文件管理路由（NAS） ============

// 获取文件列表
app.get('/api/files', auth, async (req, res) => {
    try {
        const { parent_id } = req.query;
        let sql = 'SELECT * FROM files WHERE user_id = ?';
        let params = [req.userId];
        
        if (parent_id) {
            sql += ' AND parent_id = ?';
            params.push(parent_id);
        } else {
            sql += ' AND parent_id IS NULL';
        }
        
        sql += ' ORDER BY is_folder DESC, name ASC';
        const [rows] = await pool.query(sql, params);
        res.json(rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// 创建文件夹
app.post('/api/files/folder', auth, async (req, res) => {
    try {
        const { name, parent_id } = req.body;
        
        // 检查父文件夹是否存在
        if (parent_id) {
            const [check] = await pool.query('SELECT id FROM files WHERE id = ? AND user_id = ? AND is_folder = 1', [parent_id, req.userId]);
            if (check.length === 0) return res.status(404).json({ error: '父文件夹不存在' });
        }
        
        const folderPath = parent_id ? `folder-${parent_id}/${name}` : `folder-root/${name}`;
        
        const [result] = await pool.query(
            'INSERT INTO files (user_id, parent_id, name, is_folder, path) VALUES (?, ?, ?, 1, ?)',
            [req.userId, parent_id || null, name, '/uploads/files/' + folderPath]
        );
        
        res.json({ id: result.insertId, message: '文件夹创建成功' });
    } catch (err) {
        res.status(500).json({ error: '创建失败' });
    }
});

// 上传文件
app.post('/api/files/upload', auth, (req, res) => {
    req.uploadType = 'files';
    
    upload.single('file')(req, res, async (err) => {
        if (err) return res.status(400).json({ error: err.message });
        
        try {
            const { parent_id } = req.body;
            const file = req.file;
            
            if (!file) return res.status(400).json({ error: '请选择文件' });
            
            const [result] = await pool.query(
                `INSERT INTO files (user_id, parent_id, name, is_folder, path, size, mime_type)
                 VALUES (?, ?, ?, 0, ?, ?, ?)`,
                [req.userId, parent_id || null, file.originalname, '/uploads/files/' + file.filename, file.size, file.mimetype]
            );
            
            res.json({
                id: result.insertId,
                name: file.originalname,
                path: '/uploads/files/' + file.filename,
                size: file.size
            });
        } catch (err) {
            res.status(500).json({ error: '上传失败' });
        }
    });
});

// 删除文件/文件夹
app.delete('/api/files/:id', auth, async (req, res) => {
    try {
        const [rows] = await pool.query('SELECT * FROM files WHERE id = ? AND user_id = ?', [req.params.id, req.userId]);
        if (rows.length === 0) return res.status(404).json({ error: '文件不存在' });
        
        const file = rows[0];
        
        if (!file.is_folder) {
            try {
                const filename = file.path.split('/').pop();
                fs.unlinkSync(path.join(UPLOAD_DIR, 'files', filename));
            } catch (e) {}
        }
        
        await pool.query('DELETE FROM files WHERE id = ?', [req.params.id]);
        res.json({ message: '删除成功' });
    } catch (err) {
        res.status(500).json({ error: '删除失败' });
    }
});

// ============ 统计路由 ============

app.get('/api/stats', auth, async (req, res) => {
    try {
        const [albums] = await pool.query('SELECT COUNT(*) as count FROM albums WHERE user_id = ?', [req.userId]);
        const [photos] = await pool.query('SELECT COUNT(*) as count FROM photos WHERE user_id = ?', [req.userId]);
        const [files] = await pool.query('SELECT SUM(size) as total FROM files WHERE user_id = ?', [req.userId]);
        const [photoSize] = await pool.query('SELECT SUM(size) as total FROM photos WHERE user_id = ?', [req.userId]);
        
        res.json({
            albums: albums[0].count,
            photos: photos[0].count,
            files: files[0].total || 0,
            photoSize: photoSize[0].total || 0,
            totalSize: (files[0].total || 0) + (photoSize[0].total || 0)
        });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// 根路径
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// 启动
initDatabase().then(() => {
    app.listen(PORT, '0.0.0.0', () => {
        console.log(`🚀 相册NAS系统启动: http://0.0.0.0:${PORT}`);
        console.log(`📁 上传目录: ${UPLOAD_DIR}`);
    });
});