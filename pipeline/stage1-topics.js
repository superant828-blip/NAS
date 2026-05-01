#!/usr/bin/env node
/**
 * pipeline/stage1-topics.js v2 - 选题阶段：实体识别 + 热度排序
 * 
 * 改进：
 * - 维护命名实体词典（公司/产品/人名/技术）
 * - 从标题中提取实体作为关键词
 * - 按热度排序（出现频率 × 来源权重）
 * - 过滤噪音词（品牌栏目/时间标签/运营词）
 */
import https from 'https';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { ENTITIES, STOP_WORDS, NOISE_PATTERNS } from './lib/entities.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

const SOURCES = {
  hotlist:  'https://openclaw.36krcdn.com/media/hotlist/{date}/24h_hot_list.json',
  aireport: 'https://openclaw.36krcdn.com/media/aireport/{date}/ai_report_articles.json',
  ainotes:  'https://openclaw.36krcdn.com/media/ainotes/{date}/ai_notes.json',
};

function todayStr() { return new Date().toISOString().slice(0, 10); }

function httpGet(url) {
  return new Promise((resolve, reject) => {
    https.get(url, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => { try { resolve(JSON.parse(data)); } catch { resolve(null); } });
    }).on('error', () => resolve(null));
  });
}

// 实体词典、停用词、噪音模式从 lib/entities.js 导入

/**
 * 分词
 */
function tokenize(text) {
  return text.split(/[，。、；：！？""''（）【】\s\-_.:\/\\]+/);
}

/**
 * 识别命名实体
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
 * 提取关键词（从标题中，实体优先）
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
 * 从所有标题中提取高频实体作为关键词
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
  
  // 热度 = 出现次数 × 2 + 来源数
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
 * 主流程
 */
async function main() {
  const date = todayStr();
  console.log(`📡 获取36kr数据 (${date})...`);

  const [hotlist, aireport, ainotes] = await Promise.all([
    httpGet(SOURCES.hotlist.replace('{date}', date)),
    httpGet(SOURCES.aireport.replace('{date}', date)),
    httpGet(SOURCES.ainotes.replace('{date}', date)),
  ]);

  const seen = new Set();
  const topics = [];
  for (const [src, items] of Object.entries({hotlist, aireport, ainotes})) {
    if (!items) continue;
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

  console.log(`📊 获取 ${topics.length} 条选题`);

  // 提取实体关键词
  const keywords = extractTopEntities(topics, 10);

  const result = {
    runAt: new Date().toISOString(),
    date,
    topics,
    keywords,
  };

  fs.writeFileSync(path.join(DATA_DIR, 'topics.json'), JSON.stringify(result, null, 2));

  console.log(`\n✅ 选题完成: ${topics.length} 条, ${keywords.length} 个关键词`);
  console.log(`\n关键词: ${keywords.join(', ')}`);
}

main().catch(console.error);
