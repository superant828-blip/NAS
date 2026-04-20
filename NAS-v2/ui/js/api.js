/**
 * API 封装模块
 * 包含所有与后端 API 的交互
 */

// 创建 API 工具对象
const API = {
    baseUrl: '',
    token: null,
    
    // 初始化 API 配置
    init(baseUrl, token) {
        this.baseUrl = baseUrl;
        this.token = token;
    },
    
    // 获取认证头
    getHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (this.token) {
            headers['Authorization'] = 'Bearer ' + this.token;
        }
        return headers;
    },
    
    // 获取 FormData 认证头 (用于文件上传)
    getFormHeaders() {
        const headers = {};
        if (this.token) {
            headers['Authorization'] = 'Bearer ' + this.token;
        }
        return headers;
    },
    
    // 通用请求方法
    async request(endpoint, options = {}) {
        const url = this.baseUrl + endpoint;
        const config = {
            ...options,
            headers: { ...this.getHeaders(), ...options.headers }
        };
        
        try {
            const res = await fetch(url, config);
            const data = await res.json();
            return { ok: res.ok, data, status: res.status };
        } catch (e) {
            console.error('API request failed:', e);
            throw e;
        }
    },
    
    // ========== 认证相关 ==========
    async login(email, password) {
        return this.request('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });
    },
    
    async getCurrentUser() {
        return this.request('/auth/me');
    },
    
    // ========== 文件管理 ==========
    async getFiles(parentId = null) {
        const endpoint = parentId ? `/files?parent_id=${parentId}` : '/files';
        return this.request(endpoint);
    },
    
    async getFile(id) {
        return this.request(`/files/${id}`);
    },
    
    async uploadFile(file, parentId = null) {
        const formData = new FormData();
        formData.append('file', file);
        if (parentId) formData.append('parent_id', parentId);
        
        const url = this.baseUrl + '/files/upload';
        const res = await fetch(url, {
            method: 'POST',
            headers: this.getFormHeaders(),
            body: formData
        });
        const data = await res.json();
        return { ok: res.ok, data, status: res.status };
    },
    
    async createFolder(name, parentId = null) {
        return this.request('/files/folder', {
            method: 'POST',
            body: JSON.stringify({ name, parent_id: parentId })
        });
    },
    
    async deleteFile(id) {
        return this.request(`/files/${id}`, { method: 'DELETE' });
    },
    
    async renameFile(id, name) {
        return this.request(`/files/${id}/rename`, {
            method: 'PUT',
            body: JSON.stringify({ name })
        });
    },
    
    async moveFile(id, parentId) {
        return this.request(`/files/${id}/move`, {
            method: 'PUT',
            body: JSON.stringify({ parent_id: parentId })
        });
    },
    
    async getFolders() {
        return this.request('/folders');
    },
    
    async searchFiles(query) {
        return this.request(`/search?q=${encodeURIComponent(query)}`);
    },
    
    // ========== 分享链接 ==========
    async getShareLinks() {
        return this.request('/shares/links');
    },
    
    async createShareLink(fileIds, expiresDays = 0, password = null) {
        return this.request('/shares/links', {
            method: 'POST',
            body: JSON.stringify({ 
                file_ids: fileIds,
                expires_days: expiresDays,
                password: password
            })
        });
    },
    
    async deleteShareLink(id) {
        return this.request(`/shares/links/${id}`, { method: 'DELETE' });
    },
    
    // ========== 回收站 ==========
    async getTrash() {
        return this.request('/trash');
    },
    
    async restoreTrashItem(id) {
        return this.request(`/trash/restore/${id}`, { method: 'POST' });
    },
    
    async permanentDeleteTrash(id) {
        return this.request(`/trash/${id}`, { method: 'DELETE' });
    },
    
    async emptyTrash() {
        return this.request('/trash/empty', { method: 'POST' });
    },
    
    // ========== 存储池 ==========
    async getPools() {
        return this.request('/storage/pools');
    },
    
    async getDatasets() {
        return this.request('/storage/datasets');
    },
    
    async createPool(name, vdevs, layout) {
        return this.request(`/storage/pools?name=${name}&vdevs=${JSON.stringify(vdevs)}&layout=${layout}`, {
            method: 'POST'
        });
    },
    
    async deletePool(name) {
        return this.request(`/storage/pools/${name}?force=true`, { method: 'DELETE' });
    },
    
    async scrubPool(name) {
        return this.request(`/storage/pools/${name}/scrub`, { method: 'POST' });
    },
    
    // ========== 共享 (SMB/NFS) ==========
    async getAllShares() {
        return this.request('/shares/all');
    },
    
    async createSmbShare(name, path, writable, guestOk) {
        return this.request(`/shares/smb?name=${name}&path=${path}&writable=${writable}&guest_ok=${guestOk}`, {
            method: 'POST'
        });
    },
    
    async createNfsShare(path, clients, options) {
        return this.request(`/shares/nfs?path=${path}&clients=${clients}&options=${options}`, {
            method: 'POST'
        });
    },
    
    async deleteShare(type, name) {
        return this.request(`/shares/${type}/${name}`, { method: 'DELETE' });
    },
    
    // ========== 快照 ==========
    async getSnapshots() {
        return this.request('/snapshots');
    },
    
    async createSnapshot(dataset, name) {
        return this.request(`/snapshots?dataset=${dataset}&name=${name}`, { method: 'POST' });
    },
    
    async deleteSnapshot(name) {
        return this.request(`/snapshots/${name}`, { method: 'DELETE' });
    },
    
    async rollbackSnapshot(name) {
        return this.request(`/snapshots/${name}/rollback`, { method: 'POST' });
    },
    
    // ========== 相册 ==========
    async getAlbums() {
        return this.request('/albums');
    },
    
    async getAlbum(albumId) {
        return this.request(`/albums/${albumId}`);
    },
    
    async createAlbum(name) {
        return this.request('/albums', {
            method: 'POST',
            body: JSON.stringify({ name })
        });
    },
    
    async uploadPhoto(file, name, albumId = null) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('name', name);
        if (albumId) formData.append('album_id', albumId);
        
        const url = this.baseUrl + '/photos/upload';
        const res = await fetch(url, {
            method: 'POST',
            headers: this.getFormHeaders(),
            body: formData
        });
        const data = await res.json();
        return { ok: res.ok, data, status: res.status };
    },
    
    async deletePhoto(photoId) {
        return this.request(`/photos/${photoId}`, { method: 'DELETE' });
    },
    
    // ========== 用户管理 ==========
    async getUsers() {
        return this.request('/users');
    },
    
    async createUser(userData) {
        return this.request('/users', {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    },
    
    async deleteUser(id) {
        return this.request(`/users/${id}`, { method: 'DELETE' });
    },
    
    async changePassword(oldPassword, newPassword) {
        return this.request('/users/me/password', {
            method: 'PUT',
            body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
        });
    },
    
    // ========== 系统状态 ==========
    async getSystemStatus() {
        return this.request('/system/status');
    }
};

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}