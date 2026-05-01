/**
 * pipeline/lib/common.js - 共享工具函数
 *
 * 提供文件读写、URL缓存、去重、统计等流水线通用功能。
 * 所有文件操作均已异步化，通过 LOG_LEVEL 环境变量控制日志输出。
 *
 * @module common
 */

import fs from 'fs';
import fsp from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

/** 日志级别：debug | info | warn | error | silent */
const LOG_LEVEL = process.env.LOG_LEVEL || 'info';

/**
 * 条件日志输出，仅在当前 LOG_LEVEL 允许时打印。
 * @param {'debug'|'info'|'warn'|'error'} level - 日志级别
 * @param {string} msg - 日志消息
 * @param {*} [data] - 附加数据
 */
function log(level, msg, data) {
  const levels = { debug: 0, info: 1, warn: 2, error: 3, silent: 4 };
  if (levels[level] < levels[LOG_LEVEL]) return;
  const ts = new Date().toISOString().slice(11, 19);
  const icons = { debug: '🔍', info: 'ℹ️', warn: '⚠️', error: '❌' };
  const prefix = `[${ts}] ${icons[level] || '📝'} [${level.toUpperCase()}]`;
  if (data !== undefined) {
    console.log(`${prefix} ${msg}`, data);
  } else {
    console.log(`${prefix} ${msg}`);
  }
}

export const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const DATA_DIR = path.join(__dirname, '..', 'data');

/**
 * 确保 data 目录存在，不存在则创建。
 * @returns {Promise<string>} 目录路径
 */
export async function ensureDataDir() {
  try {
    await fsp.mkdir(DATA_DIR, { recursive: true });
    log('debug', `数据目录已确认: ${DATA_DIR}`);
  } catch (err) {
    log('error', `创建数据目录失败: ${err.message}`);
    throw err;
  }
  return DATA_DIR;
}

/**
 * 从 data 目录读取并解析 JSON 文件。
 * @param {string} file - 文件名（相对 DATA_DIR）
 * @returns {Promise<*>} 解析后的 JSON 数据
 */
export async function readJSON(file) {
  const filePath = path.join(DATA_DIR, file);
  try {
    const raw = await fsp.readFile(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch (err) {
    log('error', `读取 JSON 失败: ${file} - ${err.message}`);
    throw err;
  }
}

/**
 * 将数据写入 data 目录的 JSON 文件。
 * @param {string} file - 文件名（相对 DATA_DIR）
 * @param {*} data - 要序列化的数据
 * @returns {Promise<void>}
 */
export async function writeJSON(file, data) {
  await ensureDataDir();
  const filePath = path.join(DATA_DIR, file);
  try {
    await fsp.writeFile(filePath, JSON.stringify(data, null, 2), 'utf-8');
    log('debug', `写入 JSON: ${file}`);
  } catch (err) {
    log('error', `写入 JSON 失败: ${file} - ${err.message}`);
    throw err;
  }
}

/**
 * URL 缓存：记录已抓取的 URL，避免重复抓取。
 * 使用内存缓存减少磁盘 I/O，生命周期与进程一致。
 * @type {{ urls: Record<string, object>, version: number } | null}
 */
const CACHE_FILE = 'url-cache.json';
let cache = null;

/**
 * 加载 URL 缓存（惰性加载，带内存缓存）。
 * @returns {Promise<{ urls: Record<string, object>, version: number }>}
 */
export async function loadUrlCache() {
  if (cache) return cache;
  const p = path.join(DATA_DIR, CACHE_FILE);
  try {
    const raw = await fsp.readFile(p, 'utf-8');
    cache = JSON.parse(raw);
    log('debug', `URL缓存已加载: ${Object.keys(cache.urls || {}).length} 条`);
  } catch {
    cache = { urls: {}, version: 1 };
    log('debug', 'URL缓存初始化（空）');
  }
  return cache;
}

/**
 * 检查 URL 是否已在缓存中（忽略 query 参数）。
 * @param {string} url - 待检查的 URL
 * @returns {Promise<boolean>} 是否已缓存
 */
export async function hasUrl(url) {
  const c = await loadUrlCache();
  const key = url.split('?')[0];
  return !!c.urls[key];
}

/**
 * 将 URL 标记为已抓取，存入缓存并持久化。
 * @param {string} url - 已抓取的 URL
 * @param {object} [meta={}] - 附加元数据（标题、字符数等）
 * @returns {Promise<void>}
 */
export async function markUrl(url, meta = {}) {
  const c = await loadUrlCache();
  const key = url.split('?')[0];
  c.urls[key] = { fetchedAt: new Date().toISOString(), ...meta };
  try {
    await fsp.writeFile(
      path.join(DATA_DIR, CACHE_FILE),
      JSON.stringify(c, null, 2),
      'utf-8',
    );
    log('debug', `URL已标记: ${key}`);
  } catch (err) {
    log('error', `写入 URL 缓存失败: ${err.message}`);
  }
}

/**
 * 清空 URL 缓存（内存 + 磁盘）。
 * @returns {Promise<void>}
 */
export async function clearUrlCache() {
  cache = { urls: {}, version: 1 };
  try {
    await fsp.writeFile(
      path.join(DATA_DIR, CACHE_FILE),
      JSON.stringify(cache, null, 2),
      'utf-8',
    );
    log('info', 'URL缓存已清除');
  } catch (err) {
    log('error', `清除 URL 缓存失败: ${err.message}`);
  }
}

/**
 * 通用重试包装器：对异步函数进行重试。
 *
 * @template T
 * @param {() => Promise<T>} fn - 要执行的异步函数
 * @param {string} label - 操作标签（用于日志）
 * @param {number} [maxRetries=2] - 最大重试次数（含首次）
 * @param {number} [delayMs=2000] - 重试间隔（毫秒）
 * @returns {Promise<T>} 执行结果
 */
export async function withRetry(fn, label, maxRetries = 2, delayMs = 2000) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (e) {
      if (attempt === maxRetries) throw e;
      log('warn', `重试 ${label} (${attempt}/${maxRetries})...`);
      await new Promise(r => setTimeout(r, delayMs));
    }
  }
}

/**
 * 按标题前 40 个字符去重。
 * @param {Array<{ title?: string }>} items - 待去重条目
 * @returns {Array<{ title?: string }>} 去重后的条目
 */
export function deduplicateByTitle(items) {
  const seen = new Set();
  const unique = [];
  for (const a of items) {
    const key = (a.title || '').slice(0, 40);
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(a);
    }
  }
  return unique;
}

/**
 * 按 URL 去重（忽略 query 参数），优先保留有 meta/keyword 的条目。
 * @param {Array<{ link?: string, meta?: string, keyword?: string }>} items - 待去重条目
 * @returns {Array<{ link?: string, meta?: string, keyword?: string }>} 去重后的条目
 */
export function deduplicateByUrl(items) {
  const seen = new Map(); // url -> best item
  for (const a of items) {
    const url = (a.link || '').split('?')[0];
    const existing = seen.get(url);
    if (!existing) {
      seen.set(url, a);
    } else if (a.meta || a.keyword) {
      seen.set(url, a);
    }
  }
  return Array.from(seen.values());
}

/**
 * 统计文章来源分布和置信度分布。
 * @param {Array<{ source?: string, confidence?: string }>} articles - 文章列表
 * @returns {{ bySource: Record<string, number>, byConfidence: Record<string, number> }}
 */
export function stats(articles) {
  const bySource = {};
  const byConfidence = { verified: 0, title_only: 0 };
  for (const a of articles) {
    bySource[a.source] = (bySource[a.source] || 0) + 1;
    byConfidence[a.confidence] = (byConfidence[a.confidence] || 0) + 1;
  }
  return { bySource, byConfidence };
}
