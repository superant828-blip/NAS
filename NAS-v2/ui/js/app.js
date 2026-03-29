/**
 * NAS 主应用模块
 * 包含所有 Vue 的 ref/reactive 定义和业务逻辑函数
 */

const { createApp, ref, computed, watch, onMounted } = Vue;

// 创建 Vue 应用
createApp({
    setup() {
        // ========== 基础配置 ==========
        const API_BASE = 'http://' + location.host + '/api/v1';
        
        // ========== 响应式状态 ==========
        const token = ref(localStorage.getItem('token') || '');
        const isLoggedIn = ref(false);
        const currentUser = ref({ username: '', email: '', role: 'user' });
        const currentPage = ref('dashboard');
        const currentFolderId = ref(null);
        const currentFolderName = ref('');
        const loading = ref(false);
        const sidebarShow = ref(false);
        const btnLoading = ref({});
        
        // 上传进度
        const uploadProgress = ref(0);
        const uploadStatus = ref('');
        
        // 角色权限配置
        const rolePermissions = {
            'admin': ['dashboard', 'files', 'albums', 'shares', 'snapshots', 'storage', 'users', 'monitor', 'trash', 'settings'],
            'manager': ['dashboard', 'files', 'albums', 'shares', 'snapshots', 'storage', 'monitor', 'trash'],
            'user': ['dashboard', 'files', 'albums', 'trash'],
            'guest': ['dashboard', 'files']
        };
        
        // 检查用户是否有权限访问某个模块
        const canAccess = (module) => {
            const role = currentUser.value?.role || 'guest';
            const permissions = rolePermissions[role] || [];
            return permissions.includes(module);
        };
        
        // 数据
        const pools = ref([]);
        const datasets = ref([]);
        const shares = ref({ smb: [], nfs: [] });
        const shareLinks = ref([]);
        const snapshots = ref([]);
        const trashItems = ref([]);
        const albums = ref([]);
        const users = ref([]);
        const files = ref([]);
        const jobs = ref([]);
        const jobsLoading = ref(false);
        const selectedFiles = ref(new Set());
        const searchQuery = ref('');
        const sortBy = ref('name');
        const sortOrder = ref('asc');
        const viewMode = ref('grid'); // grid, list, details
        const systemStatus = ref({ pools: 0, shares: 0, links: 0, users: 0, snapshots: 0 });
        
        // 表单
        const loginForm = ref({ email: '', password: '' });
        const profileForm = ref({ username: '', oldPassword: '', newPassword: '' });
        const allowedExtensionsInput = ref('');
        const poolForm = ref({ name: '', vdevs: '', layout: 'basic' });
        const shareForm = ref({ 
            name: '', path: '', writable: true, guest_ok: false, 
            clients: '*', options: 'rw,sync,no_subtree_check,no_root_squash', 
            expires: 0, password: '', username: '' 
        });
        const snapshotForm = ref({ dataset: '', name: '' });
        const userForm = ref({ email: '', username: '', password: '', role: 'user' });
        const newFolderName = ref('');
        const createLinkForm = ref({ fileId: '', expires: 0 });
        
        // 模态框
        const showCreatePool = ref(false);
        const showSmbModal = ref(false);
        const showNfsModal = ref(false);
        const showSnapshotModal = ref(false);
        const showUserModal = ref(false);
        const showFolderModal = ref(false);
        const showShareModal = ref(false);
        const showCreateLinkModal = ref(false);
        const showRenameModal = ref(false);
        const showMoveModal = ref(false);
        const moveForm = ref({ targetFolderId: null, folders: [] });
        const renameForm = ref({ id: null, name: '' });
        
        // 照片预览
        const showPhotoPreview = ref(false);
        const previewPhoto = ref(null);
        
        // 相册
        const currentAlbumId = ref(null);
        const currentAlbumPhotos = ref([]);
        const toasts = ref([]);
        
        // ========== 系统监控 ==========
        const wsConnected = ref(false);
        const wsConnection = ref(null);
        const eventLogs = ref([]);
        const connectedClients = ref(0);
        const storageWarning = ref(false);
        
        // 连接 WebSocket
        const connectWebSocket = () => {
            const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = wsProtocol + '//' + location.host + '/ws';
            
            try {
                wsConnection.value = new WebSocket(wsUrl);
                
                wsConnection.value.onopen = () => {
                    wsConnected.value = true;
                    showToast('WebSocket 已连接', 'success');
                    // 发送认证
                    if (token.value) {
                        wsConnection.value.send(JSON.stringify({ type: 'auth', token: token.value }));
                    }
                };
                
                wsConnection.value.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === 'client_count') {
                            connectedClients.value = data.count || 0;
                        } else if (data.type === 'event') {
                            // 添加新事件到日志
                            eventLogs.value.unshift({
                                id: Date.now(),
                                time: new Date().toLocaleString('zh-CN'),
                                type: data.event_type || 'info',
                                description: data.message || '',
                                status: data.status || 'success'
                            });
                            // 保持最多100条
                            if (eventLogs.value.length > 100) {
                                eventLogs.value = eventLogs.value.slice(0, 100);
                            }
                            // 显示通知
                            showToast('新事件: ' + (data.message || ''), 'info');
                        } else if (data.type === 'storage_warning') {
                            storageWarning.value = data.warning || false;
                        }
                    } catch(e) {
                        console.error('WS消息解析失败:', e);
                    }
                };
                
                wsConnection.value.onclose = () => {
                    wsConnected.value = false;
                    connectedClients.value = 0;
                    showToast('WebSocket 已断开', 'info');
                };
                
                wsConnection.value.onerror = (error) => {
                    console.error('WebSocket 错误:', error);
                    showToast('WebSocket 连接错误', 'error');
                };
            } catch(e) {
                console.error('WebSocket 连接失败:', e);
                showToast('WebSocket 连接失败', 'error');
            }
        };
        
        // 断开 WebSocket
        const disconnectWebSocket = () => {
            if (wsConnection.value) {
                wsConnection.value.close();
                wsConnection.value = null;
            }
            wsConnected.value = false;
            connectedClients.value = 0;
            showToast('WebSocket 已断开', 'info');
        };
        
        // 加载事件日志 (从API)
        const loadEventLogs = async () => {
            try {
                const res = await fetch(API_BASE + '/events', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (res.ok) {
                    const data = await res.json();
                    eventLogs.value = Array.isArray(data) ? data : [];
                }
            } catch(e) {
                console.error('加载事件日志失败:', e);
            }
            
            // 同时检查存储使用率告警
            try {
                const res = await fetch(API_BASE + '/storage/pools', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (res.ok) {
                    const pools = await res.json();
                    storageWarning.value = false;
                    for (const pool of pools) {
                        if (pool.usage_percent > 80) {
                            storageWarning.value = true;
                            break;
                        }
                    }
                }
            } catch(e) {
                console.error('检查存储告警失败:', e);
            }
        };
        
        // ========== 工具函数 ==========
        
        // Toast 提示
        const showToast = (message, type = 'info') => {
            const id = Date.now();
            toasts.value.push({ id, message, type });
            setTimeout(() => {
                toasts.value = toasts.value.filter(t => t.id !== id);
            }, 3000);
        };
        
        // 按钮 loading 状态
        const setBtnLoading = (key, val) => {
            btnLoading.value = { ...btnLoading.value, [key]: val };
        };
        
        // 格式化文件大小
        const formatSize = (bytes) => {
            if (!bytes) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
        };
        
        // 格式化日期
        const formatDate = (dateStr) => {
            if (!dateStr) return '';
            return new Date(dateStr).toLocaleString('zh-CN');
        };
        
        // 获取文件图标
        const getFileIcon = (f) => {
            if (f.is_folder) return 'bi bi-folder-fill';
            const ext = f.name.split('.').pop().toLowerCase();
            if (['jpg','jpeg','png','gif','webp'].includes(ext)) return 'bi bi-image-fill';
            if (['mp4','avi','mov','mkv'].includes(ext)) return 'bi bi-film-fill';
            if (ext === 'pdf') return 'bi bi-file-earmark-pdf-fill';
            if (['doc','docx','txt'].includes(ext)) return 'bi bi-file-earmark-text-fill';
            if (['zip','rar','7z'].includes(ext)) return 'bi bi-archive-fill';
            return 'bi bi-file-earmark-fill';
        };
        
        // ========== 生命周期 ==========
        
        onMounted(async () => {
            // 初始化数据
            pools.value = [];
            shares.value = { smb: [], nfs: [] };
            snapshots.value = [];
            files.value = [];
            trashItems.value = [];
            albums.value = [];
            users.value = [];
            shareLinks.value = [];
            
            if (token.value) {
                try {
                    const res = await fetch(API_BASE + '/auth/me', { 
                        headers: { 'Authorization': 'Bearer ' + token.value } 
                    });
                    if (res.ok) {
                        currentUser.value = await res.json();
                        profileForm.value.username = currentUser.value.username;
                        isLoggedIn.value = true;
                        loadData();
                    } else {
                        token.value = '';
                        localStorage.removeItem('token');
                        isLoggedIn.value = false;
                    }
                } catch(e) { 
                    console.error(e); 
                    isLoggedIn.value = false;
                }
            } else {
                isLoggedIn.value = false;
            }
        });
        
        // 监听页面变化
        watch(currentPage, (page) => {
            if (page === 'dashboard') loadPools();
            else if (page === 'files') loadFiles();
            else if (page === 'shares') loadShares();
            else if (page === 'links') loadShareLinks();
            else if (page === 'snapshots') loadSnapshots();
            else if (page === 'trash') loadTrash();
            else if (page === 'albums') loadAlbums();
            else if (page === 'users') loadUsers();
            else if (page === 'jobs') loadJobs();
            else if (page === 'monitor') loadEventLogs();
        });
        
        // 监听排序变化
        watch(sortBy, () => { sortFiles(); });
        watch(sortOrder, () => { sortFiles(); });
        
        // ========== 核心功能 ==========
        
        const loadData = () => { 
            loadPools();
            loadShares();
            loadSnapshots();
            loadSystemStatus();
        };
        
        const navigateTo = (page) => {
            currentPage.value = page;
            if (page === 'profile') {
                loadConfig();
            }
        };
        
        // 登录/登出
        const handleLogin = async () => {
            const res = await fetch(API_BASE + '/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(loginForm.value)
            });
            
            if (res.ok) {
                const data = await res.json();
                token.value = data.access_token;
                localStorage.setItem('token', token.value);
                currentUser.value = data.user;
                profileForm.value.username = data.user.username;
                isLoggedIn.value = true;
                loadData();
                // 自动连接 WebSocket
                connectWebSocket();
            } else {
                alert('登录失败');
            }
        };
        
        const logout = () => {
            disconnectWebSocket();
            token.value = '';
            localStorage.removeItem('token');
            isLoggedIn.value = false;
        };
        
        // 系统状态
        const loadSystemStatus = async () => {
            try {
                const res = await fetch(API_BASE + '/system/status', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                systemStatus.value = await res.json();
            } catch(e) { console.error(e); }
        };
        
        // ========== 文件管理 ==========
        
        const loadFiles = async () => { 
            files.value = []; 
            loading.value = true;
            try {
                let url = API_BASE + '/files';
                // 搜索模式
                if (searchQuery.value && searchQuery.value.trim()) {
                    url = API_BASE + '/search?q=' + encodeURIComponent(searchQuery.value.trim());
                } else if (currentFolderId.value) {
                    url += '?parent_id=' + currentFolderId.value;
                }
                const res = await fetch(url, { 
                    headers: { 'Authorization': 'Bearer ' + token.value } 
                });
                if (!res.ok) {
                    files.value = [];
                    loading.value = false;
                    return;
                }
                const data = await res.json();
                // 处理搜索结果格式 {files: [...]} 或直接数组
                if (Array.isArray(data)) {
                    files.value = data;
                } else if (data.files) {
                    files.value = data.files;
                } else {
                    files.value = [];
                }
                sortFiles();
            } catch(e) {
                console.error(e);
                files.value = [];
            }
            loading.value = false;
        };
        
        const sortFiles = () => {
            if (!files.value || !files.value.length) return;
            const arr = [...files.value];
            arr.sort((a, b) => {
                let va, vb;
                if (sortBy.value === 'name') {
                    va = (a.name || '').toLowerCase();
                    vb = (b.name || '').toLowerCase();
                } else if (sortBy.value === 'size') {
                    va = a.size || 0;
                    vb = b.size || 0;
                } else if (sortBy.value === 'type') {
                    // 按类型排序：文件夹优先，然后按扩展名
                    const getExt = (f) => {
                        if (f.is_folder) return '0';
                        const name = f.name || '';
                        const idx = name.lastIndexOf('.');
                        return idx > 0 ? name.substring(idx + 1).toLowerCase() : 'zzz';
                    };
                    va = getExt(a);
                    vb = getExt(b);
                } else if (sortBy.value === 'date') {
                    va = a.updated_at || a.created_at || '';
                    vb = b.updated_at || b.created_at || '';
                } else {
                    va = a.updated_at || '';
                    vb = b.updated_at || '';
                }
                if (va < vb) return sortOrder.value === 'asc' ? -1 : 1;
                if (va > vb) return sortOrder.value === 'asc' ? 1 : -1;
                return 0;
            });
            files.value = arr;
        };
        
        const handleFileClick = (f) => {
            if (f.is_folder) {
                currentFolderId.value = f.id;
                currentFolderName.value = f.name;
                loadFiles();
            } else {
                previewFile(f.id);
            }
        };
        
        const toggleSelect = (id) => {
            if (selectedFiles.value.has(id)) {
                selectedFiles.value.delete(id);
            } else {
                selectedFiles.value.add(id);
            }
            selectedFiles.value = new Set(selectedFiles.value);
        };
        
        const clearSelection = () => {
            selectedFiles.value = new Set();
        };
        
        const goParent = async () => {
            if (!currentFolderId.value) return;
            try {
                const res = await fetch(API_BASE + "/files/" + currentFolderId.value, {
                    headers: { "Authorization": "Bearer " + token.value }
                });
                if (res.ok) {
                    const file = await res.json();
                    if (file.parent_id) {
                        currentFolderId.value = file.parent_id;
                        loadFiles();
                    } else {
                        goHome();
                    }
                }
            } catch(e) { console.error(e); }
        };

        const goHome = () => {
            currentFolderId.value = null;
            currentFolderName.value = '';
            loadFiles();
        };
        
        const refreshFiles = () => {
            searchQuery.value = '';
            loadFiles();
        };
        
        const searchFiles = async () => {
            if (!searchQuery.value.trim()) { loadFiles(); return; }
            loading.value = true;
            const res = await fetch(API_BASE + '/search?q=' + encodeURIComponent(searchQuery.value), {
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            const data = await res.json();
            files.value = data.files || [];
            loading.value = false;
        };
        
        // 文件操作
        const triggerUpload = () => {
            const input = document.getElementById('uploadInput');
            if (input) input.click();
        };
        
        const handleUpload = async (e) => {
            const fileList = e.target.files;
            if (!fileList || fileList.length === 0) return;
            const files = Array.from(fileList);
            
            uploadProgress.value = 0;
            const totalSize = files.reduce((sum, f) => sum + f.size, 0);
            let uploadedSize = 0;
            const startTime = Date.now();
            let lastLoaded = 0;
            let speedSamples = [];
            
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                const formData = new FormData();
                formData.append('file', file);
                if (currentFolderId.value) formData.append('parent_id', currentFolderId.value);
                
                uploadStatus.value = `正在上传 ${i+1}/${files.length}: ${file.name}`;
                
                await new Promise((resolve, reject) => {
                    const xhr = new XMLHttpRequest();
                    const fileStartTime = Date.now();
                    xhr.open('POST', API_BASE + '/files/upload');
                    xhr.setRequestHeader('Authorization', 'Bearer ' + token.value);
                    
                    xhr.upload.onprogress = (event) => {
                        if (event.lengthComputable) {
                            const fileProgress = (event.loaded / event.total) * 100;
                            const currentFileSize = event.loaded;
                            const allProgress = ((uploadedSize + currentFileSize) / totalSize) * 100;
                            uploadProgress.value = Math.round(allProgress);
                            
                            // 计算平均速度（使用最近3秒的数据）
                            const now = Date.now();
                            const elapsed = (now - fileStartTime) / 1000;
                            if (elapsed > 0.5) {
                                const currentSpeed = event.loaded / elapsed;
                                speedSamples.push(currentSpeed);
                                if (speedSamples.length > 5) speedSamples.shift();
                                const avgSpeed = speedSamples.reduce((a, b) => a + b, 0) / speedSamples.length;
                                
                                const remaining = event.total - event.loaded;
                                const remainingSec = avgSpeed > 0 ? Math.round(remaining / avgSpeed) : 0;
                                
                                if (remainingSec > 0 && remainingSec < 3600) {
                                    const mins = Math.floor(remainingSec / 60);
                                    const secs = remainingSec % 60;
                                    let timeStr = mins > 0 ? `${mins}分${secs}秒` : `${secs}秒`;
                                    const speedMB = (avgSpeed / 1024 / 1024).toFixed(1);
                                    uploadStatus.value = `${file.name} - ${Math.round(fileProgress)}% ${speedMB}MB/s 预计${timeStr}`;
                                } else {
                                    const speedMB = (avgSpeed / 1024 / 1024).toFixed(1);
                                    uploadStatus.value = `${file.name} - ${Math.round(fileProgress)}% ${speedMB}MB/s`;
                                }
                            }
                        }
                    };
                    
                    xhr.onload = () => {
                        console.log('Upload response:', xhr.status, xhr.responseText);
                        if (xhr.status >= 200 && xhr.status < 300) {
                            try {
                                const response = JSON.parse(xhr.responseText);
                                if (response.id || response.name) {
                                    uploadedSize += file.size;
                                    resolve();
                                    return;
                                }
                            } catch(e) {}
                            reject(new Error('上传失败: ' + xhr.responseText));
                        } else {
                            reject(new Error('上传失败: ' + xhr.status + ' - ' + xhr.responseText));
                        }
                    };
                    xhr.onerror = () => reject(new Error('上传失败'));
                    xhr.send(formData);
                });
            }
            
            uploadStatus.value = '上传完成';
            showToast('上传成功', 'success');
            setTimeout(() => { uploadProgress.value = 0; uploadStatus.value = ''; }, 2000);
            loadFiles();
            e.target.value = '';
        };
        
        const createFolder = async () => {
            if (!newFolderName.value) return;
            await fetch(API_BASE + '/files/folder', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value, 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newFolderName.value, parent_id: currentFolderId.value })
            });
            showFolderModal.value = false;
            newFolderName.value = '';
            loadFiles();
        };
        
        const deleteSelected = async () => {
            if (selectedFiles.value.size === 0) return;
            if (!confirm('确定要删除选中的 ' + selectedFiles.value.size + ' 个文件吗？')) return;
            setBtnLoading('delete', true);
            try {
                for (let id of selectedFiles.value) {
                    await fetch(API_BASE + '/files/' + id, {
                        method: 'DELETE',
                        headers: { 'Authorization': 'Bearer ' + token.value }
                    });
                }
                showToast('删除成功', 'success');
                selectedFiles.value = new Set();
                loadFiles();
            } catch(e) {
                showToast('删除失败', 'error');
            }
            setBtnLoading('delete', false);
        };
        
        const renameFile = async () => {
            if (!renameForm.value.id || !renameForm.value.name) return;
            
            const res = await fetch(API_BASE + '/files/' + renameForm.value.id + '/rename', {
                method: 'PUT',
                headers: { 'Authorization': 'Bearer ' + token.value, 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: renameForm.value.name })
            });
            
            if (res.ok) {
                showRenameModal.value = false;
                renameForm.value = { id: null, name: '' };
                loadFiles();
                // 刷新移动对话框的文件夹列表
                if (showMoveModal.value) {
                    loadFolders();
                }
            } else {
                alert('重命名失败');
            }
        };
        
        const prepareRename = () => {
            if (selectedFiles.value.size === 1) {
                const fileId = Array.from(selectedFiles.value)[0];
                const file = files.value.find(f => f.id === fileId);
                if (file) {
                    renameForm.value = { id: fileId, name: file.name };
                    showRenameModal.value = true;
                }
            }
        };
        
        const previewFile = (id) => {
            window.open(API_BASE + '/files/' + id + '/download', '_blank');
        };
        
        // 批量移动
        const loadFolders = async () => {
            try {
                const res = await fetch(API_BASE + '/folders', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (!res.ok) {
                    moveForm.value.folders = [];
                    return;
                }
                const data = await res.json();
                moveForm.value.folders = Array.isArray(data) ? data.sort((a, b) => (a.full_path || '').localeCompare(b.full_path || '')) : [];
            } catch(e) { 
                console.error(e); 
                moveForm.value.folders = [];
            }
        };
        
        const showMoveDialog = async () => {
            if (selectedFiles.value.size === 0) return;
            await loadFolders();
            moveForm.value.targetFolderId = null;
            showMoveModal.value = true;
        };
        
        const moveSelected = async () => {
            if (!moveForm.value.targetFolderId) {
                showToast('请选择目标文件夹', 'error');
                return;
            }
            setBtnLoading('move', true);
            let successCount = 0;
            let failCount = 0;
            let newPaths = [];
            try {
                const fileIds = Array.from(selectedFiles.value);
                for (let id of fileIds) {
                    const res = await fetch(API_BASE + '/files/' + id + '/move', {
                        method: 'PUT',
                        headers: { 'Authorization': 'Bearer ' + token.value, 'Content-Type': 'application/json' },
                        body: JSON.stringify({ parent_id: moveForm.value.targetFolderId })
                    });
                    if (res.ok) {
                        const data = await res.json();
                        if (data.new_path) newPaths.push(data.new_path);
                        successCount++;
                    } else {
                        failCount++;
                    }
                }
                if (failCount === 0) {
                    showToast(`移动成功！${newPaths.length > 0 ? '\n新路径: ' + newPaths.join(', ') : ''}`, 'success');
                } else {
                    showToast(`移动完成：成功 ${successCount} 个，失败 ${failCount} 个`, 'warning');
                }
                showMoveModal.value = false;
                selectedFiles.value = new Set();
                loadFiles();
            } catch(e) {
                showToast('移动失败: ' + (e.message || '未知错误'), 'error');
            }
            setBtnLoading('move', false);
        };
        
        // ========== 分享链接 ==========
        
        const loadShareLinks = async () => {
            loading.value = true;
            try {
                const res = await fetch(API_BASE + '/shares/links', { 
                    headers: { 'Authorization': 'Bearer ' + token.value } 
                });
                if (!res.ok) {
                    shareLinks.value = [];
                    loading.value = false;
                    return;
                }
                const data = await res.json();
                shareLinks.value = Array.isArray(data) ? data : [];
                systemStatus.value.links = (shareLinks && shareLinks.length) || 0;
            } catch(e) { 
                console.error(e); 
                shareLinks.value = [];
            }
            loading.value = false;
        };
        
        const getShareUrl = (shareToken) => {
            return window.location.origin + '/share/' + shareToken;
        };
        
        const copyShareUrl = async (shareToken) => {
            const url = getShareUrl(shareToken);
            await navigator.clipboard.writeText(url);
            showToast('链接已复制到剪贴板', 'success');
        };
        
        const createShareLink = async () => {
            if (selectedFiles.value.size === 0) {
                alert('请选择要分享的文件'); return;
            }
            
            const fileIds = Array.from(selectedFiles.value);
            const expires = shareForm.value.expires > 0 ? parseInt(shareForm.value.expires) : 0;
            
            const res = await fetch(API_BASE + '/shares/links', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value, 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    file_ids: fileIds,
                    expires_days: expires,
                    password: shareForm.value.password || null
                })
            });
            
            if (res.ok) {
                showShareModal.value = false;
                shareForm.value = { name: '', path: '', writable: true, guest_ok: false, clients: '*', options: 'rw,sync,no_subtree_check,no_root_squash', expires: 0, password: '' };
                loadShareLinks();
                alert('分享链接创建成功');
            } else {
                alert('创建失败');
            }
        };
        
        // 下载文件
        const downloadFile = async () => {
            if (selectedFiles.value.size !== 1) {
                alert('请选择一个文件'); return;
            }
            const fileId = Array.from(selectedFiles.value)[0];
            
            // 检查选中的是文件还是文件夹
            const file = files.value.find(f => f.id === fileId);
            if (!file) {
                alert('文件不存在'); return;
            }
            if (file.is_folder) {
                alert('文件夹无法下载，请选择文件'); return;
            }
            
            // 检查token
            if (!token.value) {
                alert('请先登录'); return;
            }
            
            try {
                const res = await fetch(API_BASE + '/files/' + fileId + '/download', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (res.ok) {
                    const blob = await res.blob();
                    // 检查是否是错误响应（blob太小可能是错误JSON）
                    if (blob.size < 100) {
                        const text = await blob.text();
                        if (text.includes('detail')) {
                            alert('文件不存在于磁盘上');
                            return;
                        }
                    }
                    const fileName = file?.name || 'download';
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = fileName;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                } else {
                    const errorText = await res.text();
                    console.error('下载失败:', res.status, errorText);
                    alert('下载失败: ' + res.status);
                }
            } catch(e) {
                console.error(e);
                alert('下载失败: ' + e.message);
            }
        };
        
        const createShareLinkFromModal = async () => {
            if (!createLinkForm.value.fileId) {
                alert('请选择文件'); return;
            }
            
            const expires = createLinkForm.value.expires > 0 ? parseInt(createLinkForm.value.expires) : 0;
            
            const res = await fetch(API_BASE + '/shares/links', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value, 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    file_ids: [createLinkForm.value.fileId],
                    expires_days: expires
                })
            });
            
            if (res.ok) {
                showCreateLinkModal.value = false;
                createLinkForm.value = { fileId: '', expires: 0 };
                loadShareLinks();
                alert('分享链接创建成功');
            } else {
                alert('创建失败');
            }
        };
        
        const deleteShareLink = async (id) => {
            if (!confirm('确定要删除这个分享链接吗？')) return;
            
            const res = await fetch(API_BASE + '/shares/links/' + id, {
                method: 'DELETE',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                loadShareLinks();
                alert('删除成功');
            } else {
                alert('删除失败');
            }
        };
        
        // ========== 回收站 ==========
        
        const loadTrash = async () => {
            loading.value = true;
            try {
                const res = await fetch(API_BASE + '/trash', { 
                    headers: { 'Authorization': 'Bearer ' + token.value } 
                });
                if (!res.ok) {
                    trashItems.value = [];
                    loading.value = false;
                    return;
                }
                const data = await res.json();
                trashItems.value = Array.isArray(data) ? data : [];
            } catch(e) { 
                console.error(e); 
                trashItems.value = [];
            }
            loading.value = false;
        };
        
        const restoreTrash = async (id) => {
            try {
                await fetch(API_BASE + '/trash/restore/' + id, {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                showToast('恢复成功', 'success');
                loadTrash();
            } catch(e) {
                showToast('恢复失败', 'error');
            }
        };
        
        const permanentDelete = async (id) => {
            if (!confirm('确定要彻底删除吗？此操作不可恢复！')) return;
            try {
                await fetch(API_BASE + '/trash/' + id, {
                    method: 'DELETE',
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                showToast('删除成功', 'success');
                loadTrash();
            } catch(e) {
                showToast('删除失败', 'error');
            }
        };
        
        const emptyTrash = async () => {
            if ((trashItems && trashItems.length) || 0 === 0) {
                showToast('回收站已经是空的', 'info');
                return;
            }
            if (!confirm('确定要清空回收站吗？此操作不可恢复！')) return;
            
            const res = await fetch(API_BASE + '/trash/empty', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                showToast('回收站已清空', 'success');
                loadTrash();
            } else {
                showToast('清空失败', 'error');
            }
        };
        
        // ========== 存储池 ==========
        
        const loadPools = async () => {
            loading.value = true;
            pools.value = [];
            try {
                const res = await fetch(API_BASE + '/storage/pools', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (!res.ok) {
                    pools.value = [];
                    loading.value = false;
                    return;
                }
                const data = await res.json();
                pools.value = Array.isArray(data) ? data : [];
                systemStatus.value.pools = pools.value ? (pools && pools.length) || 0 : 0;
            } catch(e) { 
                console.error(e); 
                pools.value = [];
            }
            loading.value = false;
        };
        
        const loadDatasets = async () => {
            try {
                const res = await fetch(API_BASE + '/storage/datasets', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (!res.ok) {
                    datasets.value = [];
                    return;
                }
                const data = await res.json();
                datasets.value = Array.isArray(data) ? data : [];
            } catch(e) { 
                console.error(e); 
                datasets.value = [];
            }
        };
        
        const createPool = async () => {
            if (!poolForm.value.name || !poolForm.value.vdevs) {
                alert('请填写完整信息'); return;
            }
            
            const vdevs = poolForm.value.vdevs.split(' ').filter(s => s.trim());
            
            const res = await fetch(API_BASE + '/storage/pools?name=' + poolForm.value.name + 
                '&vdevs=' + JSON.stringify(vdevs) + '&layout=' + poolForm.value.layout, {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                showCreatePool.value = false;
                poolForm.value = { name: '', vdevs: '', layout: 'basic' };
                loadPools();
                alert('创建成功');
            } else {
                alert('创建失败');
            }
        };
        
        const deletePool = async (name) => {
            if (!confirm('确定要删除存储池 ' + name + ' 吗？')) return;
            
            const res = await fetch(API_BASE + '/storage/pools/' + name + '?force=true', {
                method: 'DELETE',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                loadPools();
                alert('删除成功');
            } else {
                alert('删除失败');
            }
        };
        
        const scrubPool = async (name) => {
            const res = await fetch(API_BASE + '/storage/pools/' + name + '/scrub', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                alert('清理已启动');
            } else {
                alert('操作失败');
            }
        };
        
        // ========== 共享 (SMB/NFS) ==========
        
        const loadShares = async () => { 
            shares.value = { smb: [], nfs: [] };
            try {
                const res = await fetch(API_BASE + '/shares/smb/all', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (!res.ok) {
                    shares.value = { smb: [], nfs: [] };
                    return;
                }
                const data = await res.json();
                shares.value = { smb: data.smb || [], nfs: data.nfs || [] };
                systemStatus.value.shares = (shares.value.smb?.length || 0) + (shares.value.nfs?.length || 0);
            } catch(e) { 
                console.error(e); 
                shares.value = { smb: [], nfs: [] };
            }
        };
        
        const createSmbShare = async () => {
            if (!shareForm.value.name || !shareForm.value.path) {
                alert('请填写完整信息'); return;
            }
            
            const res = await fetch(API_BASE + '/shares/smb?name=' + shareForm.value.name + 
                '&path=' + shareForm.value.path + 
                '&writable=' + shareForm.value.writable + 
                '&guest_ok=' + shareForm.value.guest_ok, {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                showSmbModal.value = false;
                shareForm.value = { name: '', path: '', writable: true, guest_ok: false, clients: '*', options: 'rw,sync,no_subtree_check,no_root_squash', expires: 0, password: '' };
                loadShares();
                alert('创建成功');
            } else {
                alert('创建失败');
            }
        };
        
        const createNfsShare = async () => {
            if (!shareForm.value.path) {
                alert('请填写路径'); return;
            }
            
            const res = await fetch(API_BASE + '/shares/nfs?path=' + shareForm.value.path + 
                '&clients=' + shareForm.value.clients + 
                '&options=' + shareForm.value.options, {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                showNfsModal.value = false;
                shareForm.value = { name: '', path: '', writable: true, guest_ok: false, clients: '*', options: 'rw,sync,no_subtree_check,no_root_squash', expires: 0, password: '' };
                loadShares();
                alert('创建成功');
            } else {
                alert('创建失败');
            }
        };
        
        const deleteShare = async (type, name) => {
            if (!confirm('确定要删除这个共享吗？')) return;
            
            const res = await fetch(API_BASE + '/shares/' + type + '/' + name, {
                method: 'DELETE',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                loadShares();
                alert('删除成功');
            } else {
                alert('删除失败');
            }
        };
        
        const copyShareLink = (type, name) => {
            let link = type === 'smb' 
                ? '\\\\' + location.host + '\\' + name
                : location.host + ':' + name;
            navigator.clipboard.writeText(link);
            showToast('链接已复制到剪贴板', 'success');
        };
        
        // ========== 快照 ==========
        
        const loadSnapshots = async () => { 
            snapshots.value = []; 
            loading.value = true;
            try {
                const res = await fetch(API_BASE + '/snapshots', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (!res.ok) {
                    snapshots.value = [];
                    loading.value = false;
                    return;
                }
                const data = await res.json();
                snapshots.value = Array.isArray(data) ? data : [];
                systemStatus.value.snapshots = (snapshots && snapshots.length) || 0;
            } catch(e) { 
                console.error(e); 
                snapshots.value = [];
            }
            loading.value = false;
        };
        
        const createSnapshot = async () => {
            if (!snapshotForm.value.dataset || !snapshotForm.value.name) {
                alert('请填写完整信息'); return;
            }
            
            const res = await fetch(API_BASE + '/snapshots?dataset=' + snapshotForm.value.dataset + 
                '&name=' + snapshotForm.value.name, {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                showSnapshotModal.value = false;
                snapshotForm.value = { dataset: '', name: '' };
                loadSnapshots();
                alert('创建成功');
            } else {
                alert('创建失败');
            }
        };
        
        const deleteSnapshot = async (name) => {
            if (!confirm('确定要删除快照吗？')) return;
            
            const res = await fetch(API_BASE + '/snapshots/' + name, {
                method: 'DELETE',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                loadSnapshots();
                alert('删除成功');
            } else {
                alert('删除失败');
            }
        };
        
        const rollbackSnapshot = async (name) => {
            if (!confirm('警告: 回滚将丢失快照之后的所有更改! 继续吗?')) return;
            
            const res = await fetch(API_BASE + '/snapshots/' + name + '/rollback', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                alert('回滚成功');
            } else {
                alert('回滚失败');
            }
        };
        
        // ========== 相册 ==========
        
        const loadAlbums = async () => {
            loading.value = true;
            try {
                const res = await fetch(API_BASE + '/albums', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (!res.ok) {
                    albums.value = [];
                    loading.value = false;
                    return;
                }
                const data = await res.json();
                albums.value = Array.isArray(data) ? data : [];
            } catch(e) { 
                console.error(e); 
                albums.value = [];
            }
            loading.value = false;
        };
        
        const viewAlbum = async (albumId) => {
            currentAlbumId.value = albumId;
            try {
                const res = await fetch(API_BASE + '/albums/' + albumId, {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                const album = await res.json();
                currentAlbumPhotos.value = album.photos || [];
                currentPage.value = 'album-detail';
            } catch(e) { 
                console.error(e); 
                alert('加载相册失败');
            }
        };
        
        const handlePhotoUpload = async (e) => {
            const albumId = currentAlbumId.value;
            for (let file of e.target.files) {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('name', file.name);
                if (albumId) {
                    formData.append('album_id', albumId);
                }
                const res = await fetch(API_BASE + '/photos/upload', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token.value },
                    body: formData
                });
                if (!res.ok) {
                    const err = await res.json();
                    alert('上传失败: ' + (err.detail || '未知错误'));
                    return;
                }
            }
            if (currentAlbumId.value) {
                viewAlbum(currentAlbumId.value);
            } else {
                loadAlbums();
            }
            alert('上传成功');
            e.target.value = '';
        };
        
        const createAlbum = async () => {
            const name = prompt('请输入相册名称:');
            if (!name) return;
            const res = await fetch(API_BASE + '/albums', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value, 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            if (res.ok) {
                showToast('相册创建成功', 'success');
                loadAlbums();
            } else {
                const err = await res.json();
                showToast('创建失败: ' + (err.detail || '未知错误'), 'error');
            }
        };
        
        // 照片预览
        const openPhotoPreview = (photo) => {
            previewPhoto.value = photo;
            showPhotoPreview.value = true;
        };
        
        const closePhotoPreview = () => {
            previewPhoto.value = null;
            showPhotoPreview.value = false;
        };
        
        const deletePhoto = async (photoId) => {
            if (!confirm('确定要删除这张照片吗？')) return;
            try {
                await fetch(API_BASE + '/photos/' + photoId, {
                    method: 'DELETE',
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                showToast('删除成功', 'success');
                closePhotoPreview();
                if (currentAlbumId.value) {
                    viewAlbum(currentAlbumId.value);
                }
            } catch(e) {
                showToast('删除失败', 'error');
            }
        };
        
        // ========== 任务管理 ==========
        
        let jobsRefreshInterval = null;
        
        const loadJobs = async () => {
            jobsLoading.value = true;
            try {
                const res = await fetch(API_BASE + '/jobs', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (!res.ok) {
                    jobs.value = [];
                    jobsLoading.value = false;
                    return;
                }
                const data = await res.json();
                jobs.value = Array.isArray(data) ? data : [];
            } catch(e) { 
                console.error(e); 
                jobs.value = [];
            }
            jobsLoading.value = false;
            
            // 设置定时刷新 (每5秒刷新一次正在运行的任务)
            if (jobsRefreshInterval) clearInterval(jobsRefreshInterval);
            jobsRefreshInterval = setInterval(() => {
                const hasRunning = jobs.value.some(j => j.status === 'RUNNING');
                if (hasRunning && currentPage.value === 'jobs') {
                    loadJobs();
                }
            }, 5000);
        };
        
        const cancelJob = async (jobId) => {
            if (!confirm('确定要取消这个任务吗？')) return;
            try {
                const res = await fetch(API_BASE + '/jobs/' + jobId + '/cancel', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (res.ok) {
                    showToast('任务已取消', 'success');
                    loadJobs();
                } else {
                    showToast('取消失败', 'error');
                }
            } catch(e) {
                showToast('取消失败', 'error');
            }
        };
        
        const getJobTypeIcon = (type) => {
            if (!type) return 'bi bi-question-circle';
            const t = type.toLowerCase();
            if (t.includes('upload')) return 'bi bi-cloud-upload';
            if (t.includes('download')) return 'bi bi-cloud-download';
            if (t.includes('backup')) return 'bi bi-save';
            if (t.includes('restore')) return 'bi bi-arrow-counterclockwise';
            if (t.includes('scrub')) return 'bi bi-arrow-repeat';
            if (t.includes('delete')) return 'bi bi-trash';
            return 'bi bi-gear';
        };
        
        const getJobStatusClass = (status) => {
            if (!status) return 'bg-secondary';
            switch(status) {
                case 'PENDING': return 'bg-warning';
                case 'RUNNING': return 'bg-primary';
                case 'SUCCESS': return 'bg-success';
                case 'FAILED': return 'bg-danger';
                case 'CANCELLED': return 'bg-secondary';
                default: return 'bg-secondary';
            }
        };
        
        const getJobStatusText = (status) => {
            if (!status) return '未知';
            switch(status) {
                case 'PENDING': return '等待中';
                case 'RUNNING': return '运行中';
                case 'SUCCESS': return '完成';
                case 'FAILED': return '失败';
                case 'CANCELLED': return '已取消';
                default: return status;
            }
        };
        
        // ========== 用户管理 ==========
        
        const loadUsers = async () => {
            loading.value = true;
            try {
                const res = await fetch(API_BASE + '/users', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (!res.ok) {
                    users.value = [];
                    loading.value = false;
                    return;
                }
                const data = await res.json();
                users.value = Array.isArray(data) ? data : [];
                systemStatus.value.users = (users.value && users.value.length) || 0;
            } catch(e) { 
                console.error(e); 
                users.value = [];
            }
            loading.value = false;
        };
        
        const createUser = async () => {
            if (!token.value) {
                alert('登录已过期，请重新登录'); return;
            }
            
            if (!userForm.value.email || !userForm.value.username || !userForm.value.password) {
                alert('请填写完整信息'); return;
            }
            
            const pwd = userForm.value.password;
            if (pwd.length < 8) {
                alert('密码至少需要8个字符'); return;
            }
            
            const res = await fetch(API_BASE + '/users', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token.value, 'Content-Type': 'application/json' },
                body: JSON.stringify(userForm.value)
            });
            
            if (res.ok) {
                showUserModal.value = false;
                userForm.value = { email: '', username: '', password: '', role: 'user' };
                loadUsers();
                showToast('用户创建成功', 'success');
            } else if (res.status === 401) {
                alert('登录已过期，请重新登录');
            } else {
                const err = await res.json();
                const msg = err.detail || err.message || JSON.stringify(err);
                alert('创建失败: ' + msg);
            }
        };
        
        const deleteUser = async (id) => {
            if (!confirm('确定要删除用户吗？')) return;
            
            const res = await fetch(API_BASE + '/users/' + id, {
                method: 'DELETE',
                headers: { 'Authorization': 'Bearer ' + token.value }
            });
            
            if (res.ok) {
                loadUsers();
                alert('删除成功');
            } else {
                alert('删除失败');
            }
        };
        
        // ========== 个人资料 ==========
        
        const updateProfile = async () => {
            alert('功能开发中');
        };
        
        const changePassword = async () => {
            if (!profileForm.value.oldPassword || !profileForm.value.newPassword) {
                alert('请填写密码'); return;
            }
            
            const res = await fetch(API_BASE + '/users/me/password', {
                method: 'PUT',
                headers: { 'Authorization': 'Bearer ' + token.value, 'Content-Type': 'application/json' },
                body: JSON.stringify({ old_password: profileForm.value.oldPassword, new_password: profileForm.value.newPassword })
            });
            
            if (res.ok) {
                alert('密码修改成功');
                profileForm.value.oldPassword = '';
                profileForm.value.newPassword = '';
            } else {
                alert('修改失败，请检查当前密码');
            }
        };
        
        // 加载系统配置
        const loadConfig = async () => {
            if (currentUser.value?.role !== 'admin') return;
            try {
                const res = await fetch(API_BASE + '/config', {
                    headers: { 'Authorization': 'Bearer ' + token.value }
                });
                if (res.ok) {
                    const data = await res.json();
                    allowedExtensionsInput.value = (data.allowed_extensions || []).join(', ');
                }
            } catch(e) { console.error(e); }
        };
        
        // 保存允许上传的文件类型配置
        const saveAllowedExtensions = async () => {
            if (currentUser.value?.role !== 'admin') return;
            const extensions = allowedExtensionsInput.value.split(',').map(e => e.trim()).filter(e => e);
            try {
                const res = await fetch(API_BASE + '/config', {
                    method: 'PUT',
                    headers: { 
                        'Authorization': 'Bearer ' + token.value,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ allowed_extensions: extensions })
                });
                if (res.ok) {
                    showToast('配置保存成功', 'success');
                } else {
                    showToast('配置保存失败', 'error');
                }
            } catch(e) {
                showToast('配置保存失败', 'error');
            }
        };
        
        // ========== 返回所有响应式数据和方法 ==========
        
        return {
            // 基础状态
            token, isLoggedIn, currentUser, currentPage, currentFolderId, currentFolderName, 
            loading, sidebarShow, btnLoading,
            
            // 数据
            pools, shares, shareLinks, snapshots, trashItems, users, files, selectedFiles, 
            jobs, jobsLoading, searchQuery, systemStatus,
            
            // 表单
            loginForm, profileForm, allowedExtensionsInput, poolForm, shareForm, snapshotForm, userForm, 
            newFolderName, createLinkForm, renameForm,
            
            // 模态框
            showCreatePool, showSmbModal, showNfsModal, showSnapshotModal, showUserModal, 
            showFolderModal, showShareModal, showCreateLinkModal, showRenameModal, showMoveModal, moveForm,
            
            // 照片预览
            showPhotoPreview, previewPhoto, openPhotoPreview, closePhotoPreview, deletePhoto,
            
            // 相册
            currentAlbumId, currentAlbumPhotos,
            
            // Toast
            toasts, showToast, setBtnLoading,
            
            // 认证
            handleLogin, logout,
            
            // 导航
            navigateTo, loadData,
            
            // 存储池
            loadPools, createPool, deletePool, scrubPool,
            
            // 共享
            loadShares, createSmbShare, createNfsShare, deleteShare, copyShareLink,
            
            // 分享链接
            loadShareLinks, getShareUrl, copyShareUrl, createShareLink, createShareLinkFromModal, deleteShareLink,
            
            // 快照
            loadSnapshots, createSnapshot, deleteSnapshot, rollbackSnapshot,
            
            // 回收站
            loadTrash, restoreTrash, permanentDelete, emptyTrash,
            
            // 相册
            loadAlbums, handlePhotoUpload, createAlbum, viewAlbum,
            
            // 用户
            loadUsers, createUser, deleteUser, updateProfile, changePassword, loadConfig, saveAllowedExtensions, canAccess,
            
            // 任务
            loadJobs, cancelJob, getJobTypeIcon, getJobStatusClass, getJobStatusText,
            
            // 文件操作
            loadFiles, getFileIcon, handleFileClick, toggleSelect, clearSelection, 
            formatSize, formatDate, goHome, goParent, refreshFiles, searchFiles, sortFiles, viewMode,
            handleUpload, triggerUpload, createFolder, deleteSelected, previewFile, uploadProgress, uploadStatus, 
            renameFile, prepareRename, loadFolders, showMoveDialog, moveSelected,
            
            // 系统监控
            wsConnected, wsConnection, eventLogs, connectedClients, storageWarning,
            connectWebSocket, disconnectWebSocket, loadEventLogs
        };
    }
}).mount('#app');