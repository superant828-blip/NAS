/**
 * pipeline/lib/common.js - 共享工具函数
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

export const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const DATA_DIR = path.join(__dirname, '..', 'data');

export function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

export function readJSON(file) {
  return JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), 'utf-8'));
}

export function writeJSON(file, data) {
  ensureDataDir();
  fs.writeFileSync(path.join(DATA_DIR, file), JSON.stringify(data, null, 2));
}

/**
 * URL 缓存：记录已抓取的 URL，避免重复抓取
 */
const CACHE_FILE = 'url-cache.json';
let cache = null;

export function loadUrlCache() {
  if (cache) return cache;
  const p = path.join(DATA_DIR, CACHE_FILE);
  if (fs.existsSync(p)) {
    cache = JSON.parse(fs.readFileSync(p, 'utf-8'));
  } else {
    cache = { urls: {}, version: 1 };
  }
  return cache;
}

export function hasUrl(url) {
  const c = loadUrlCache();
  const key = url.split('?')[0];
  return !!c.urls[key];
}

export function markUrl(url, meta = {}) {
  const c = loadUrlCache();
  const key = url.split('?')[0];
  c.urls[key] = { fetchedAt: new Date().toISOString(), ...meta };
  fs.writeFileSync(path.join(DATA_DIR, CACHE_FILE), JSON.stringify(c, null, 2));
}

export function clearUrlCache() {
  cache = { urls: {}, version: 1 };
  fs.writeFileSync(path.join(DATA_DIR, CACHE_FILE), JSON.stringify(cache, null, 2));
  console.log('✅ URL缓存已清除');
}

/**
 * 通用重试包装
 */
export async function withRetry(fn, label, maxRetries = 2, delayMs = 2000) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (e) {
      if (attempt === maxRetries) throw e;
      console.log(`    ⏳ 重试 ${label} (${attempt}/${maxRetries})...`);
      await new Promise(r => setTimeout(r, delayMs));
    }
  }
}

/**
 * 按标题前40字去重
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
 * 按URL去重（优先保留有meta/keyword的条目）
 */
export function deduplicateByUrl(items) {
  const seen = new Map(); // url -> best item
  for (const a of items) {
    const url = (a.link || '').split('?')[0]; // 忽略query参数
    const existing = seen.get(url);
    if (!existing) {
      seen.set(url, a);
    } else if (a.meta || a.keyword) {
      // 优先保留有元数据的
      seen.set(url, a);
    }
  }
  return Array.from(seen.values());
}

/**
 * 统计来源和置信度
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
