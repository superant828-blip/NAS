# NAS 前端模块化结构

## 文件结构

```
ui/
├── index.html          # 主页面 (精简后 2064 行)
├── mobile.html         # 移动端页面
└── js/
    ├── api.js          # API 封装模块 (288 行)
    └── app.js          # Vue 应用主逻辑 (1191 行)
```

## 模块说明

### api.js
- API 请求封装
- 包含所有后端 API 调用方法
- 提供统一的请求/响应处理
- 支持文件上传的 FormData 处理

### app.js  
- Vue 3 应用入口
- 包含所有响应式状态定义 (ref/reactive)
- 包含所有业务逻辑函数
- 页面导航、数据加载、文件操作等

### index.html
- 保留 HTML 模板结构
- 保留所有 CSS 样式
- 引入外部 JS 模块

## 加载顺序

1. Vue 3 (CDN)
2. api.js (API 封装)
3. app.js (应用逻辑)

## 注意事项

- 所有现有功能保持不变
- 仅做结构拆分，无功能变更
- index.html 引用路径使用相对路径 `js/`