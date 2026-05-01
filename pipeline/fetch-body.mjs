#!/usr/bin/env node
/**
 * pipeline/fetch-body.mjs - 按序号/关键词抓取单篇文章正文
 * 
 * 用法:
 *   node fetch-body.mjs 3              # 按collected.json序号抓取
 *   node fetch-body.mjs "AI创业"       # 按标题关键词模糊匹配
 *   node fetch-body.mjs "https://..."  # 直接传入URL
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { markUrl } from './lib/common.js';
import { CONFIG } from './config.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');
const COLLECTED_FILE = path.join(DATA_DIR, 'collected.json');

// 解析参数
const query = process.argv.slice(2).join(' ');
if (!query) {
  console.log('用法: node fetch-body.mjs <序号/关键词/URL>');
  console.log('示例:');
  console.log('  node fetch-body.mjs 3              # 第3篇文章');
  console.log('  node fetch-body.mjs "AI创业"        # 标题含"AI创业"');
  console.log('  node fetch-body.mjs "https://..."   # 直接URL');
  process.exit(1);
}

async function findArticle() {
  if (!fs.existsSync(COLLECTED_FILE)) {
    return null;
  }
  const data = JSON.parse(fs.readFileSync(COLLECTED_FILE, 'utf-8'));
  const articles = data.articles || [];

  // 1. 数字序号
  const num = parseInt(query);
  if (!isNaN(num) && num > 0 && num <= articles.length) {
    return { article: articles[num - 1], index: num - 1 };
  }

  // 2. URL
  if (query.startsWith('http')) {
    const match = articles.find(a => a.link && a.link.includes(query.slice(0, 50)));
    if (match) return { article: match, index: articles.indexOf(match) };
    return { article: { title: query, link: query, source: 'URL', confidence: 'title_only' }, index: -1 };
  }

  // 3. 标题关键词模糊匹配
  const matches = articles.filter(a => a.title && a.title.toLowerCase().includes(query.toLowerCase()));
  if (matches.length > 0) {
    return { article: matches[0], index: articles.indexOf(matches[0]), totalMatches: matches.length };
  }

  return null;
}

async function fetchBody(url, title) {
  let browser;
  try {
    browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
    const page = await browser.newPage();
    
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: CONFIG.pageTimeout });
    await page.waitForTimeout(3000);

    const content = await page.evaluate((maxChars) => {
      const selectors = [
        '.article-content', '.article-body', '.post-content',
        '.entry-content', '.news_content', '.detail-content',
        '.article-detail', '[class*="article-content"]', '[class*="article-body"]',
        '[class*="post-content"]', '[class*="detail-content"]',
        'article', '.rich_media_content', '#artibody',
      ];

      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) {
          const text = el.innerText?.trim();
          if (text && text.length > 100) return text.slice(0, maxChars);
        }
      }

      const main = document.querySelector('main');
      if (main) {
        const text = main.innerText?.trim();
        if (text && text.length > 200) return text.slice(0, maxChars);
      }

      return null;
    }, CONFIG.maxContentChars);

    return content;
  } finally {
    if (browser) await browser.close().catch(() => {});
  }
}

async function main() {
  console.log(`🔍 查找: ${query}`);
  const result = await findArticle();

  if (!result) {
    console.log(`❌ 未找到匹配的文章`);
    process.exit(1);
  }

  const { article, index, totalMatches } = result;
  console.log(`\n📄 找到: ${article.title}`);
  console.log(`   来源: ${article.source}`);
  console.log(`   链接: ${article.link || '无'}`);
  if (totalMatches > 1) console.log(`   共${totalMatches}条匹配，取第1条`);

  if (!article.link || !article.link.startsWith('http')) {
    console.log(`\n⚠️ 无有效链接，无法抓取正文`);
    process.exit(1);
  }

  if (article.content) {
    console.log(`\n✅ 已有正文 (${article.content.length} 字):\n`);
    console.log(article.content.slice(0, 1000));
    if (article.content.length > 1000) console.log('\n...(省略)');
    return;
  }

  console.log(`\n📖 正在抓取正文...`);
  const content = await fetchBody(article.link, article.title);

  if (content && content.length > 100) {
    console.log(`\n✅ 正文抓取成功 (${content.length} 字):\n`);
    console.log(content.slice(0, 2000));
    if (content.length > 2000) console.log('\n...(省略)');

    // 更新 collected.json
    if (index >= 0 && fs.existsSync(COLLECTED_FILE)) {
      const data = JSON.parse(fs.readFileSync(COLLECTED_FILE, 'utf-8'));
      data.articles[index].content = content.slice(0, CONFIG.maxContentChars);
      data.articles[index].contentFetchedAt = new Date().toISOString();
      data.articles[index].contentSource = article.link;
      fs.writeFileSync(COLLECTED_FILE, JSON.stringify(data, null, 2));
    }
    markUrl(article.link, { title: article.title.slice(0, 50), chars: content.length });
  } else {
    console.log(`\n❌ 未能提取正文`);
  }
}

main().catch(e => {
  console.error(`💥 抓取失败: ${e.message}`);
  process.exit(1);
});
