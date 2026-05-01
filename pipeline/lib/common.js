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
