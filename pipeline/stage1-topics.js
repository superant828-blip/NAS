#!/usr/bin/env node
/**
 * pipeline/stage1-topics.js - 选题阶段：抓取36kr数据 → 生成选题清单
 */
import https from 'https';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

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

function extractKeywords(titles, topN = 10) {
  const stopWords = new Set(['的','了','是','在','和','与','或','等','个','这','那','就','都','被','把','对','于','中','上','下','来','到','过','为','以','及','之','而','但','却','还','也','又','再','最','很','更','已','将','让','使','比','按','根据','关于','对于','随着','由于','因为','所以','如果','那么','第一','第二']);
  // 噪音关键词模式：品牌栏目/时间标签/无意义短语
  const noisePatterns = [
    /^(8点1氪|15点1氪|24点1氪|1氪|晚报|早报|午报)/,  // 品牌栏目
    /^(寻求报道|我要报道|投稿|合作)/,  // 运营标签
    /^(今天|今年|今年五一|这个五一|本周|本月|本月精选)/,  // 时间标签
    /^(官方通报|突发|快讯|独家|首发|重磅)/,  // 新闻标签
  ];
  const wc = {};
  for (const t of titles) {
    for (const w of t.split(/[，。、；：！？""''（）【】\s\-_.:\/\\]+/)) {
      if (w.length >= 2 && !stopWords.has(w) && !/^\d+$/.test(w)) {
        // 过滤噪音关键词
        const isNoise = noisePatterns.some(p => p.test(w));
        if (!isNoise) wc[w] = (wc[w]||0)+1;
      }
    }
  }
  return Object.entries(wc).sort((a,b)=>b[1]-a[1]).slice(0,topN).map(([w])=>w);
}

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
        topics.push({ title, source: item.author || item.authorName || src, url: item.url || item.noteUrl || '' });
      }
    }
  }

  const keywords = extractKeywords(topics.map(t=>t.title), 10);
  const result = { runAt: new Date().toISOString(), date, topics, keywords };
  fs.writeFileSync(path.join(DATA_DIR, 'topics.json'), JSON.stringify(result, null, 2));

  console.log(`✅ 选题完成: ${topics.length} 条, ${keywords.length} 个关键词`);
  console.log(`关键词: ${keywords.join(', ')}`);
}

main().catch(console.error);
