#!/usr/bin/env node
/**
 * pipeline/stage2b-content.js - 文章正文抓取
 * 
 * 读取 collected.json 中的链接，逐篇抓取正文内容
 * 支持分批执行，可指定批次范围和最大数量
 * 
 * 用法:
 *   node stage2b-content.js              # 抓取前5篇
 *   node stage2b-content.js --max 10     # 抓取前10篇
 *   node stage2b-content.js --source 36kr # 只抓36氪
 *   node stage2b-content.js --source wscn # 只抓华尔街见闻
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');
const COLLECTED_FILE = path.join(DATA_DIR, 'collected.json');

// 解析参数
const args = process.argv.slice(2);
const maxArticles = parseInt(args.find(a => a.startsWith('--max'))?.split('=')[1] || '5');
const sourceFilter = args.find(a => a.startsWith('--source'))?.split('=')[1];

async function fetchContent() {
  if (!fs.existsSync(COLLECTED_FILE)) {
    console.log('❌ 没有采集数据，请先运行 Stage 2');
    process.exit(1);
  }

  const collected = JSON.parse(fs.readFileSync(COLLECTED_FILE, 'utf-8'));
  let articles = collected.articles || [];

  // 过滤：有链接且还没有正文的
  let targets = articles.filter(a => a.link && !a.content);

  // 按来源过滤
  if (sourceFilter) {
    const sourceMap = { '36kr': '36氪', 'wscn': '华尔街见闻', 'ndrc': '发改委', 'nda': '国家数据局' };
    const targetSource = sourceMap[sourceFilter] || sourceFilter;
    targets = targets.filter(a => a.source === targetSource);
  }

  // 限制数量
  targets = targets.slice(0, maxArticles);

  if (targets.length === 0) {
    console.log('✅ 所有文章已有正文，无需抓取');
    process.exit(0);
  }

  console.log(`📖 开始抓取正文: ${targets.length} 篇`);
  console.log(`   来源: ${[...new Set(targets.map(a => a.source))].join(', ')}`);
  console.log(`   超时: 15秒/篇\n`);

  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext({ userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' });
  const page = await context.newPage();

  let successCount = 0;
  let failCount = 0;

  for (let i = 0; i < targets.length; i++) {
    const a = targets[i];
    console.log(`[${i + 1}/${targets.length}] ${a.source}: ${a.title.slice(0, 40)}...`);

    try {
      await page.goto(a.link, { waitUntil: 'domcontentloaded', timeout: 15000 });
      await page.waitForTimeout(3000); // 等待JS渲染

      // 提取正文
      const content = await page.evaluate(() => {
        // 尝试多种正文选择器
        const selectors = [
          '.article-content',           // 通用
          '.article-body',              // 通用
          '.post-content',              // WordPress
          '.entry-content',             // WordPress
          '.news_content',              // 新浪/网易
          '.detail-content',            // 通用
          '.article-detail',            // 通用
          '[class*="article-content"]', // 模糊匹配
          '[class*="article-body"]',
          '[class*="post-content"]',
          '[class*="detail-content"]',
          'article',                    // HTML5
          '.rich_media_content',        // 微信
          '#artibody',                  // 新浪
        ];

        for (const sel of selectors) {
          const el = document.querySelector(sel);
          if (el) {
            const text = el.innerText?.trim();
            if (text && text.length > 100) {
              return text;
            }
          }
        }

        // 如果找不到正文选择器，取 <main> 或页面核心内容
        const main = document.querySelector('main');
        if (main) {
          const text = main.innerText?.trim();
          if (text && text.length > 200) {
            return text.slice(0, 8000); // 限制长度
          }
        }

        return null;
      });

      if (content && content.length > 100) {
        a.content = content.slice(0, 8000); // 限制8000字
        a.contentFetchedAt = new Date().toISOString();
        a.contentSource = a.link;
        successCount++;
        console.log(`   ✅ ${content.length} 字`);
      } else {
        a.content = null;
        a.contentError = 'no_content_found';
        failCount++;
        console.log(`   ⚠️ 未找到正文`);
      }
    } catch (e) {
      a.content = null;
      a.contentError = e.message.slice(0, 200);
      failCount++;
      console.log(`   ❌ ${e.message.slice(0, 60)}`);
    }
  }

  await browser.close();

  // 保存更新后的数据
  fs.writeFileSync(COLLECTED_FILE, JSON.stringify(collected, null, 2));

  // 统计
  const withContent = articles.filter(a => a.content).length;
  console.log(`\n✅ 正文抓取完成: 成功 ${successCount} 篇 | 失败 ${failCount} 篇`);
  console.log(`   累计有正文: ${withContent}/${articles.length} 篇 (${(withContent/articles.length*100).toFixed(0)}%)`);
}

fetchContent().catch(e => { console.error(e); process.exit(1); });
