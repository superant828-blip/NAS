#!/usr/bin/env node

/**
 * Hermes Model Bridge
 * 
 * 将 OpenClaw 当前配置的大模型分享给 Hermes Agent 使用
 * 
 * 支持两种模式:
 * 1. MCP Server 模式 - 作为 MCP 工具供 Hermes 调用
 * 2. OpenAI 兼容 API 模式 - 兼容 OpenAI API 的 HTTP 服务
 * 
 * 使用方式:
 *   node hermes-model-bridge.js [mcp|api]
 * 
 * 默认 MCP 模式
 */

const http = require('http');
const https = require('https');

// 配置 - 从环境变量或配置文件读取
const CONFIG = {
  // 模型配置 (与 openclaw.json 保持一致)
  model: process.env.OPENCLAW_MODEL || 'qwen/MiniMax-M2.5',
  apiKey: process.env.DASHSCOPE_API_KEY || process.env.OPENAI_API_KEY || '',
  baseUrl: process.env.BASE_URL || 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  
  // 服务配置
  port: parseInt(process.env.PORT || '3456'),
  host: process.env.HOST || 'localhost',
  
  // 模型参数
  maxTokens: parseInt(process.env.MAX_TOKENS || '65536'),
  temperature: parseFloat(process.env.TEMPERATURE || '0.7'),
};

// ============== API 调用 ==============

/**
 * 调用大模型 API
 */
async function callChatAPI(messages, options = {}) {
  const url = `${CONFIG.baseUrl}/chat/completions`;
  
  const body = JSON.stringify({
    model: options.model || CONFIG.model,
    messages: messages,
    max_tokens: options.maxTokens || CONFIG.maxTokens,
    temperature: options.temperature || CONFIG.temperature,
    stream: options.stream || false,
    ...options
  });

  return new Promise((resolve, reject) => {
    const isHttps = url.startsWith('https://');
    const client = isHttps ? https : http;
    
    const urlObj = new URL(url);
    
    const req = client.request({
      hostname: urlObj.hostname,
      port: urlObj.port || (isHttps ? 443 : 80),
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${CONFIG.apiKey}`,
        'Content-Length': Buffer.byteLength(body)
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.error) {
            reject(new Error(json.error.message || JSON.stringify(json.error)));
          } else {
            resolve(json);
          }
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

/**
 * 流式调用大模型 API
 */
async function* streamChatAPI(messages, options = {}) {
  const url = `${CONFIG.baseUrl}/chat/completions`;
  
  const body = JSON.stringify({
    model: options.model || CONFIG.model,
    messages: messages,
    max_tokens: options.maxTokens || CONFIG.maxTokens,
    temperature: options.temperature || CONFIG.temperature,
    stream: true,
    ...options
  });

  const isHttps = url.startsWith('https://');
  const client = isHttps ? https : http;
  
  const urlObj = new URL(url);
  
  // 简化实现：返回 Promise 而不是 generator
  return new Promise((resolve, reject) => {
    const req = client.request({
      hostname: urlObj.hostname,
      port: urlObj.port || (isHttps ? 443 : 80),
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${CONFIG.apiKey}`,
        'Content-Length': Buffer.byteLength(body)
      }
    }, (res) => {
      let buffer = '';
      const chunks = [];
      
      res.on('data', (chunk) => {
        buffer += chunk;
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              chunks.push({ done: true });
              return;
            }
            try {
              const json = JSON.parse(data);
              chunks.push(json);
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      });
      
      res.on('end', () => {
        resolve(chunks);
      });
      
      res.on('error', reject);
    });
    
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

// ============== MCP Server 模式 ==============

/**
 * MCP Server 实现
 */
class MCPServer {
  constructor() {
    this.tools = this.registerTools();
  }
  
  registerTools() {
    return {
      'chat': {
        description: '使用 OpenClaw 配置的模型进行对话',
        inputSchema: {
          type: 'object',
          properties: {
            messages: {
              type: 'array',
              description: '对话消息数组',
              items: {
                type: 'object',
                properties: {
                  role: { type: 'string', enum: ['system', 'user', 'assistant'] },
                  content: { type: 'string' }
                }
              }
            },
            model: { type: 'string', description: '模型名称 (可选)' },
            temperature: { type: 'number', description: '温度参数 (可选)' },
            maxTokens: { type: 'number', description: '最大 tokens (可选)' }
          },
          required: ['messages']
        }
      },
      'chat_stream': {
        description: '使用 OpenClaw 配置的模型进行流式对话',
        inputSchema: {
          type: 'object',
          properties: {
            messages: {
              type: 'array',
              description: '对话消息数组'
            },
            model: { type: 'string', description: '模型名称 (可选)' }
          },
          required: ['messages']
        }
      },
      'get_model_info': {
        description: '获取当前模型信息',
        inputSchema: {
          type: 'object',
          properties: {}
        }
      },
      'list_models': {
        description: '列出可用模型',
        inputSchema: {
          type: 'object',
          properties: {}
        }
      }
    };
  }
  
  async handleRequest(method, params) {
    switch (method) {
      case 'initialize':
        return {
          protocolVersion: '2024-11-05',
          capabilities: {
            tools: {}
          },
          serverInfo: {
            name: 'hermes-model-bridge',
            version: '1.0.0'
          }
        };
      
      case 'tools/list':
        return {
          tools: Object.entries(this.tools).map(([name, tool]) => ({
            name,
            description: tool.description,
            inputSchema: tool.inputSchema
          }))
        };
      
      case 'tools/call':
        return await this.handleToolCall(params.name, params.arguments);
      
      default:
        throw new Error(`Unknown method: ${method}`);
    }
  }
  
  async handleToolCall(name, args) {
    switch (name) {
      case 'chat': {
        const result = await callChatAPI(args.messages, {
          model: args.model,
          temperature: args.temperature,
          maxTokens: args.maxTokens
        });
        
        const content = result.choices[0]?.message?.content || '';
        
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                response: content,
                usage: result.usage,
                model: result.model,
                finishReason: result.choices[0]?.finish_reason
              }, null, 2)
            }
          ]
        };
      }
      
      case 'get_model_info': {
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                model: CONFIG.model,
                baseUrl: CONFIG.baseUrl,
                maxTokens: CONFIG.maxTokens,
                temperature: CONFIG.temperature,
                provider: 'qwen'
              }, null, 2)
            }
          ]
        };
      }
      
      case 'list_models': {
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify([
                'qwen/MiniMax-M2.5',
                'qwen/qwen3.5-plus',
                'qwen/qwen3-max-2026-01-23',
                'qwen/qwen3-coder-next',
                'qwen/qwen3-coder-plus',
                'qwen/glm-5',
                'qwen/glm-4.7',
                'qwen/kimi-k2.5'
              ], null, 2)
            }
          ]
        };
      }
      
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  }
  
  runStdio() {
    let buffer = '';
    
    process.stdin.on('data', (chunk) => {
      buffer += chunk;
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      
      for (const line of lines) {
        if (!line.trim()) continue;
        
        try {
          const request = JSON.parse(line);
          
          this.handleRequest(request.method, request.params)
            .then(result => {
              const response = {
                jsonrpc: '2.0',
                id: request.id,
                result
              };
              console.log(JSON.stringify(response));
            })
            .catch(error => {
              const response = {
                jsonrpc: '2.0',
                id: request.id,
                error: {
                  code: -32603,
                  message: error.message
                }
              };
              console.log(JSON.stringify(response));
            });
        } catch (e) {
          // 忽略解析错误
        }
      }
    });
  }
}

// ============== OpenAI 兼容 API ==============

/**
 * OpenAI 兼容 API 服务器
 */
class APIServer {
  constructor() {
    this.server = null;
  }
  
  start() {
    this.server = http.createServer(async (req, res) => {
      // CORS
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
      
      if (req.method === 'OPTIONS') {
        res.writeHead(204);
        res.end();
        return;
      }
      
      const url = new URL(req.url, `http://${req.headers.host}`);
      
      // 模型列表
      if (url.pathname === '/v1/models' && req.method === 'GET') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          object: 'list',
          data: [
            {
              id: CONFIG.model,
              object: 'model',
              created: 1700000000,
              owned_by: 'qwen'
            }
          ]
        }));
        return;
      }
      
      // 模型信息
      if (url.pathname === `/v1/models/${CONFIG.model}` && req.method === 'GET') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          id: CONFIG.model,
          object: 'model',
          created: 1700000000,
          owned_by: 'qwen',
          permission: [],
          root: CONFIG.model,
          parent: null
        }));
        return;
      }
      
      // Chat Completions
      if (url.pathname === '/v1/chat/completions' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
          try {
            const data = JSON.parse(body);
            const isStream = data.stream;
            
            if (isStream) {
              res.writeHead(200, {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
              });
              
              // 获取流式响应
              const chunks = await streamChatAPI(data.messages, {
                model: data.model || CONFIG.model,
                temperature: data.temperature,
                maxTokens: data.max_tokens
              });
              
              for (const chunk of chunks) {
                if (chunk.done) {
                  res.write('data: [DONE]\n\n');
                  break;
                }
                
                const delta = chunk.choices?.[0]?.delta?.content || '';
                if (delta) {
                  res.write(`data: ${JSON.stringify({
                    id: `chatcmpl-${Date.now()}`,
                    object: 'chat.completion.chunk',
                    created: Math.floor(Date.now() / 1000),
                    model: data.model || CONFIG.model,
                    choices: [{
                      index: 0,
                      delta: { content: delta },
                      finish_reason: null
                    }]
                  })}\n\n`);
                }
              }
              
              res.end();
            } else {
              const result = await callChatAPI(data.messages, {
                model: data.model || CONFIG.model,
                temperature: data.temperature,
                maxTokens: data.max_tokens
              });
              
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({
                id: `chatcmpl-${Date.now()}`,
                object: 'chat.completion',
                created: Math.floor(Date.now() / 1000),
                model: data.model || CONFIG.model,
                choices: [{
                  index: 0,
                  message: result.choices[0].message,
                  finish_reason: result.choices[0].finish_reason
                }],
                usage: result.usage
              }));
            }
          } catch (e) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: { message: e.message } }));
          }
        });
        return;
      }
      
      // 404
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: { message: 'Not found' } }));
    });
    
    this.server.listen(CONFIG.port, CONFIG.host, () => {
      console.log(`
╔═══════════════════════════════════════════════════════════╗
║         Hermes Model Bridge 已启动                        ║
╠═══════════════════════════════════════════════════════════╣
║  模型: ${CONFIG.model.padEnd(50)}║
║  API:  http://${CONFIG.host}:${CONFIG.port}/v1/chat/completions║
║  MCP:  stdio 模式已就绪                                   ║
╚═══════════════════════════════════════════════════════════╝

使用方式:
  1. MCP 模式: node hermes-model-bridge.js mcp
  2. API 模式: node hermes-model-bridge.js api

Hermes Agent 配置示例:
  - API URL: http://${CONFIG.host}:${CONFIG.port}
  - Model: ${CONFIG.model}
  - API Key: ${CONFIG.apiKey ? '(已设置)' : '(请设置 DASHSCOPE_API_KEY 环境变量)'}
`);
    });
  }
}

// ============== 主程序 ==============

function main() {
  const mode = process.argv[2] || 'mcp';
  
  console.log(`
╔═══════════════════════════════════════════════════════════╗
║        Hermes Model Bridge - 模型共享程序                 ║
║        让 Hermes Agent 使用 OpenClaw 配置的大模型          ║
╚═══════════════════════════════════════════════════════════╝
当前配置:
  模型: ${CONFIG.model}
  API: ${CONFIG.baseUrl}
  端口: ${CONFIG.port}
`);
  
  if (!CONFIG.apiKey) {
    console.warn('\n⚠️  警告: 未设置 API Key (DASHSCOPE_API_KEY)\n');
  }
  
  if (mode === 'api') {
    const server = new APIServer();
    server.start();
  } else {
    const mcp = new MCPServer();
    mcp.runStdio();
    console.log('\nMCP Server 已就绪，通过 stdio 通信...\n');
  }
}

main();
