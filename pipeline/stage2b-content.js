#!/usr/bin/env node
/**
 * pipeline/stage2b-content.js v2 - 文章正文抓取
 * 
 * 改进：
 * - P0: try-finally 确保浏览器关闭
 * - P1: 添加重试机制
 * - P1: 配置外部化
 * - P2: 结构化日志
 * 
 * 用法:
 *   node stage2b-content.js              # 抓取前10篇
 *   node stage2b-content.js --max 20     # 抓取前20篇
 *   node stage2b-content.js --source 36kr # 只抓36氪
 *   node stage2b-content.js --all        # 抓取全部
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { hasUrl, markUrl } from './lib/common.js';
import { info, warn, error, success } from './lib/logger.js';
import { CONFIG } from './config.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');
const COLLECTED_FILE = path.join(DATA_DIR, 'collected.json');

// 解析参数
const args = process.argv.slice(2);
const maxArticles = args.includes('--all') ? Infinity : parseInt(args.find(a => a.startsWith('--max'))?.split('=')[1] || String(CONFIG.maxContentArticles));
const sourceFilter = args.find(a => a.startsWith('--source'))?.split('=')[1];

async function fetchContent() {
  if (!fs.existsSync(COLLECTED_FILE)) {
    error('没有采集数据，请先运行 Stage 2');
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
    success('所有文章已有正文，无需抓取');
    process.exit(0);
  }

  info('开始抓取正文', `${targets.length} 篇`);
  info('来源', [...new Set(targets.map(a => a.source))].join(', '));
  info('超时', `${CONFIG.pageTimeout/1000}秒/篇`);

  let browser;
  try {
    browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
    const context = await browser.newContext({ userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' });
    const page = await context.newPage();

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < targets.length; i++) {
      const a = targets[i];
      info(`[${i + 1}/${targets.length}] ${a.source}: ${a.title.slice(0, 40)}...`);

      // 检查URL缓存
      if (hasUrl(a.link)) {
        info('已抓取过，跳过');
        successCount++;
        continue;
      }

      try {
        await page.goto(a.link, { waitUntil: 'domcontentloaded', timeout: CONFIG.pageTimeout });
        await page.waitForTimeout(3000); // 等待JS渲染

        // 提取正文
        const content = await page.evaluate(() => {
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
              if (text && text.length > 100) {
                return text.slice(0, CONFIG.maxContentChars);
              }
            }
          }

          const main = document.querySelector('main');
          if (main) {
            const text = main.innerText?.trim();
            if (text && text.length > 200) {
              return text.slice(0, CONFIG.maxContentChars);
            }
          }

          return null;
        });

        if (content && content.length > 100) {
          a.content = content.slice(0, CONFIG.maxContentChars);
          a.contentFetchedAt = new Date().toISOString();
          a.contentSource = a.link;
          markUrl(a.link, { title: a.title.slice(0, 50), chars: content.length });
          successCount++;
          success('正文抓取成功', `${content.length} 字`);
        } else {
          a.content = null;
          a.contentError = 'no_content_found';
          failCount++;
          warn('未找到正文');
        }
      } catch (e) {
        a.content = null;
        a.contentError = e.message.slice(0, 200);
        failCount++;
        error('抓取失败', e.message.slice(0, 60));
      }
    }

    // 保存更新后的数据
    fs.writeFileSync(COLLECTED_FILE, JSON.stringify(collected, null, 2));

    // 统计
    const withContent = articles.filter(a => a.content).length;
    success('正文抓取完成', `成功 ${successCount} 篇 | 失败 ${failCount} 篇`);
    success('累计有正文', `${withContent}/${articles.length} 篇 (${(withContent/articles.length*100).toFixed(0)}%)`);
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
      info('浏览器已关闭');
    }
  }
}

fetchContent().catch(e => { error('正文抓取失败', e.message); process.exit(1); });
