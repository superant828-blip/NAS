#!/usr/bin/env node
/**
 * pipeline/stage1-topics.js v3 - 选题阶段：实体识别 + 热度排序
 *
 * 从 36kr 获取热点列表、AI 报告、AI 笔记，提取命名实体，
 * 按热度排序生成关键词和选题列表。
 *
 * 改进：
 * - 文件操作异步化（fs → fsp）
 * - LOG_LEVEL 环境变量控制日志输出
 * - 完整 JSDoc 注释
 * - 增强异常处理
 *
 * @module stage1-topics
 */

import https from 'https';
import fsp from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { ENTITIES, STOP_WORDS, NOISE_PATTERNS } from './lib/entities.js';

/** 日志级别：debug | info | warn | error | silent */
const LOG_LEVEL = process.env.LOG_LEVEL || 'info';

/**
 * 条件日志输出。
 * @param {'debug'|'info'|'warn'|'error'} level
 * @param {string} msg
 * @param {*} [data]
 */
function log(level, msg, data) {
  const levels = { debug: 0, info: 1, warn: 2, error: 3, silent: 4 };
  if (levels[level] < levels[LOG_LEVEL]) return;
  const ts = new Date().toISOString().slice(11, 19);
  const icons = { debug: '🔍', info: 'ℹ️', warn: '⚠️', error: '❌' };
  const prefix = `[${ts}] ${icons[level]} [${level.toUpperCase()}]`;
  if (data !== undefined) {
    console.log(`${prefix} ${msg}`, data);
  } else {
    console.log(`${prefix} ${msg}`);
  }
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');

/** 36kr 数据源端点模板 */
const SOURCES = {
  hotlist:  'https://openclaw.36krcdn.com/media/hotlist/{date}/24h_hot_list.json',
  aireport: 'https://openclaw.36krcdn.com/media/aireport/{date}/ai_report_articles.json',
  ainotes:  'https://openclaw.36krcdn.com/media/ainotes/{date}/ai_notes.json',
};

/**
 * 返回今天的日期字符串（YYYY-MM-DD）。
 * @returns {string}
 */
function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

/**
 * 发送 HTTPS GET 请求并解析 JSON 响应。
 * 网络错误或解析失败时返回 null（不抛出）。
 * @param {string} url - 请求 URL
 * @returns {Promise<object|null>} 解析后的 JSON 或 null
 */
function httpGet(url) {
  return new Promise((resolve) => {
    https.get(url, res => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve(null);
        }
      });
    }).on('error', () => resolve(null));
  });
}

/** 实体词典、停用词、噪音模式从 lib/entities.js 导入 */

/**
 * 分词：按中文标点、空白字符和特殊符号分割。
 * @param {string} text - 输入文本
 * @returns {string[]} 分词结果
 */
function tokenize(text) {
  return text.split(/[，。、；：！？""''（）【】\s\-_.:\/\\]+/);
}

/**
 * 从文本中识别命名实体（公司、产品、人名、技术）。
 * @param {string} text - 待识别的文本
 * @returns {string[]} 匹配到的实体列表（去重、按出现顺序）
 */
function extractEntities(text) {
  const found = [];
  const allEntities = [
    ...ENTITIES.companies,
    ...ENTITIES.products,
    ...ENTITIES.people,
    ...ENTITIES.tech,
  ];
  for (const entity of allEntities) {
    if (text.includes(entity) && !found.includes(entity)) {
      found.push(entity);
    }
  }
  return found;
}

/**
 * 从标题中提取关键词（实体词权重更高）。
 * @param {string} title - 标题文本
 * @param {number} [topN=5] - 返回的关键词数量
 * @returns {string[]} 按权重降序排列的关键词
 */
function extractKeywords(title, topN = 5) {
  const tokens = tokenize(title);
  const weights = {};

  for (const token of tokens) {
    if (token.length < 2) continue;
    if (STOP_WORDS.has(token)) continue;
    if (/^\d+$/.test(token)) continue;

    // 检查噪音
    const isNoise = NOISE_PATTERNS.some(p => p.test(token));
    if (isNoise) continue;

    // 实体词权重高
    const isEntity = [
      ...ENTITIES.companies,
      ...ENTITIES.products,
      ...ENTITIES.people,
      ...ENTITIES.tech,
    ].some(e => e.includes(token) || token.includes(e));

    weights[token] = (weights[token] || 0) + (isEntity ? 3 : 1);
  }

  return Object.entries(weights)
    .sort((a, b) => b[1] - a[1])
    .slice(0, topN)
    .map(([w]) => w);
}

/**
 * 从所有选题标题中提取高频实体作为关键词。
 * 热度 = 出现次数 × 2 + 来源数
 * @param {Array<{ title: string, source: string }>} topics - 选题列表
 * @param {number} [topN=10] - 返回的热词数量
 * @returns {string[]} 按热度降序排列的实体关键词
 */
function extractTopEntities(topics, topN = 10) {
  const entityCounts = {};
  const entitySources = {};

  for (const topic of topics) {
    const entities = extractEntities(topic.title);
    const seen = new Set();

    for (const e of entities) {
      if (seen.has(e)) continue;
      seen.add(e);
      entityCounts[e] = (entityCounts[e] || 0) + 1;
      if (!entitySources[e]) entitySources[e] = new Set();
      entitySources[e].add(topic.source);
    }
  }

  return Object.entries(entityCounts)
    .map(([entity, count]) => ({
      entity,
      count,
      sources: entitySources[entity].size,
      热度: count * 2 + entitySources[entity].size,
    }))
    .sort((a, b) => b.热度 - a.热度)
    .slice(0, topN)
    .map(e => e.entity);
}

/**
 * 主流程：获取 36kr 数据，提取选题和关键词，保存结果。
 * @returns {Promise<void>}
 */
async function main() {
  try {
    // 确保 data 目录存在
    await fsp.mkdir(DATA_DIR, { recursive: true });
  } catch (err) {
    log('error', `创建数据目录失败: ${err.message}`);
    throw err;
  }

  const date = todayStr();
  log('info', `获取36kr数据 (${date})...`);

  const [hotlist, aireport, ainotes] = await Promise.all([
    httpGet(SOURCES.hotlist.replace('{date}', date)),
    httpGet(SOURCES.aireport.replace('{date}', date)),
    httpGet(SOURCES.ainotes.replace('{date}', date)),
  ]);

  const seen = new Set();
  const topics = [];
  for (const [src, items] of Object.entries({ hotlist, aireport, ainotes })) {
    if (!items) {
      log('warn', `${src} 数据为空`);
      continue;
    }
    for (const item of (Array.isArray(items) ? items : (items.data || []))) {
      const title = item.title || '';
      if (title && !seen.has(title)) {
        seen.add(title);
        topics.push({
          title,
          source: item.author || item.authorName || src,
          url: item.url || item.noteUrl || '',
        });
      }
    }
  }

  log('info', `获取 ${topics.length} 条选题`);

  // 提取实体关键词
  const keywords = extractTopEntities(topics, 10);

  const result = {
    runAt: new Date().toISOString(),
    date,
    topics,
    keywords,
  };

  // 异步写入结果
  try {
    await fsp.writeFile(
      path.join(DATA_DIR, 'topics.json'),
      JSON.stringify(result, null, 2),
      'utf-8',
    );
  } catch (err) {
    log('error', `写入 topics.json 失败: ${err.message}`);
    throw err;
  }

  log('success', `选题完成: ${topics.length} 条, ${keywords.length} 个关键词`);
  log('info', `关键词: ${keywords.join(', ')}`);
}

main().catch(err => {
  log('error', `选题阶段失败: ${err.message}`);
  process.exit(1);
});
