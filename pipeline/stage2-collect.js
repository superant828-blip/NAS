#!/usr/bin/env node
/**
 * pipeline/stage2-collect.js v5 - 采集阶段（优化版）
 *
 * 基于选题关键词，从 36氪搜索、通用站点、新浪行情API 采集资讯，
 * 去重后保存到 collected.json。
 *
 * 改进：
 * - 文件操作异步化（fs → fsp）
 * - LOG_LEVEL 环境变量控制日志输出
 * - 完整 JSDoc 注释
 * - 增强异常处理
 * - try-finally 确保浏览器关闭（防泄漏）
 *
 * @module stage2-collect
 */

import { chromium } from 'playwright';
import fsp from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { getTechStocks } from './lib/sina-stock.js';
import { withRetry, deduplicateByTitle, deduplicateByUrl, stats, writeJSON, DATA_DIR } from './lib/common.js';
import { info, warn, error, success } from './lib/logger.js';
import { CONFIG } from './config.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * 通用站点采集函数：提取页面所有 <a> 链接，过滤有效标题。
 *
 * @param {import('playwright').Page} page - Playwright 页面实例
 * @param {object} options - 采集配置
 * @param {string} options.url - 目标 URL
 * @param {string} options.name - 站点名称
 * @param {number} options.maxItems - 最大采集数量
 * @param {string} [options.domain] - 域名过滤（可选）
 * @param {string} [options.wait='networkidle'] - 等待策略
 * @param {number} [options.timeout=15000] - 超时（毫秒）
 * @param {number} [options.delay=1000] - 加载后等待（毫秒）
 * @returns {Promise<Array<{title: string, source: string, keyword: string, meta: string, link: string, confidence: string, date: string}>>}
 */
async function collectSite(page, { url, name, maxItems, domain, wait = 'networkidle', timeout = 15000, delay = 1000 }) {
  await withRetry(
    () => page.goto(url, { waitUntil: wait, timeout }),
    name,
  );
  await page.waitForTimeout(delay);

  const articles = await page.evaluate((domain) => {
    const links = document.querySelectorAll('a');
    const results = [];
    const navWords = /^(首页|登录|注册|关于|帮助|政策|条款|更多|全部|分类|频道|导航|菜单|搜索|切换|返回|顶部|底部|侧边)/;
    const noisePattern = /^(\S{1,6})\s*(刚刚|\d{1,2}:\d{2}|\d{1,2}小时前|\d{4}-\d{2}-\d{2})\s*$/;
    links.forEach(a => {
      const raw = a.innerText?.trim();
      if (!raw || raw.length < 8) return;
      const href = a.href || '';
      if (raw.includes('javascript') || (domain && !href.includes(domain))) return;
      const title = raw.split('\n')[0].trim();
      if (title.length < 8) return;
      if (navWords.test(title)) return;
      if (noisePattern.test(title)) return;
      results.push({ title, link: href });
    });
    return results;
  }, domain);

  const items = [];
  for (const a of articles.slice(0, maxItems)) {
    items.push({
      title: a.title,
      source: name,
      keyword: '',
      meta: '',
      link: a.link,
      confidence: 'title_only',
      date: new Date().toISOString(),
    });
  }
  return items;
}

/**
 * 36氪搜索采集：使用专用选择器提取搜索结果卡片。
 *
 * @param {import('playwright').Page} page - Playwright 页面实例
 * @param {string} keyword - 搜索关键词
 * @returns {Promise<Array<{title: string, source: string, keyword: string, meta: string, link: string, confidence: string, date: string}>>}
 */
async function collect36kr(page, keyword) {
  const url = `https://www.36kr.com/search/articles/${encodeURIComponent(keyword)}`;
  info(`36氪搜索: "${keyword}"`);

  try {
    await withRetry(
      () => page.goto(url, { waitUntil: 'networkidle', timeout: 20000 }),
      `36氪-${keyword}`,
    );
    await page.waitForTimeout(1000);

    const articles = await page.evaluate(() => {
      const cards = document.querySelectorAll('.article-card, .flow-item, [class*="article"], [class*="flow-item"]');
      const results = [];
      cards.forEach(card => {
        const titleEl = card.querySelector('h3, .article-title, a');
        const metaEl = card.querySelector('.time, .meta, [class*="time"], .kr-meta');
        const title = titleEl?.innerText?.trim();
        const meta = metaEl?.innerText?.trim();
        const link = titleEl?.href || '';
        if (title && title.length > 3) {
          results.push({ title, meta: meta || '', link });
        }
      });
      return results;
    });

    const items = articles.slice(0, CONFIG.maxArticlesPerKeyword).map(a => ({
      title: a.title,
      source: '36氪',
      keyword,
      meta: a.meta,
      link: a.link,
      confidence: 'title_only',
      date: new Date().toISOString(),
    }));

    success(`36氪 "${keyword}"`, `${items.length} 条`);
    return items;
  } catch (e) {
    warn(`36氪 "${keyword}" 失败`, e.message);
    return [];
  }
}

/**
 * 主采集流程：读取选题 → 36氪搜索 → 通用站点 → 新浪行情 → 去重 → 保存。
 * @returns {Promise<void>}
 */
async function collect() {
  const topicsFile = path.join(DATA_DIR, 'topics.json');

  // 异步检查并读取选题数据
  let topics;
  try {
    const raw = await fsp.readFile(topicsFile, 'utf-8');
    topics = JSON.parse(raw);
  } catch (err) {
    error('没有选题数据或读取失败', `请先运行 Stage 1: ${err.message}`);
    process.exit(1);
  }

  const keywords = topics.keywords || [];
  info('开始采集', `${keywords.length} 个关键词`);

  let browser;
  try {
    browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
    const page = await browser.newPage();
    const allArticles = [];

    // === 36氪搜索 ===
    for (const kw of keywords.slice(0, CONFIG.max36krKeywords)) {
      const items = await collect36kr(page, kw);
      allArticles.push(...items);
    }

    // === 通用站点采集 ===
    for (const site of CONFIG.sites) {
      info(`采集 ${site.name}`);
      try {
        const items = await collectSite(page, site);
        allArticles.push(...items);
        success(`${site.name} 采集完成`, `${items.length} 条`);
      } catch (e) {
        warn(`${site.name} 采集失败`, e.message);
      }
    }

    // === 新浪行情API ===
    info('新浪行情API');
    try {
      const stocks = await getTechStocks();
      for (const s of stocks) {
        const emoji = s.isLimitUp ? '🔴涨停' : s.changePct >= 0 ? '🟢' : '🔴';
        allArticles.push({
          title: `${s.name}(${s.code}) ¥${s.current} ${s.change > 0 ? '+' : ''}${s.changePct}% 成交¥${s.turnoverYi}亿 ${emoji}`,
          source: '新浪财经API',
          keyword: '',
          meta: `${s.date} ${s.time}`,
          link: `https://finance.sina.com.cn/realstock/company/${s.code}/nc.shtml`,
          confidence: 'verified',
          date: new Date().toISOString(),
          stock: s,
        });
      }
      success('新浪行情API', `${stocks.length} 条行情`);
    } catch (e) {
      error('新浪行情API失败', e.message);
    }

    // 去重
    const byUrl = deduplicateByUrl(allArticles);
    const unique = deduplicateByTitle(byUrl);
    const { bySource, byConfidence } = stats(unique);

    const result = {
      runAt: new Date().toISOString(),
      date: new Date().toISOString().slice(0, 10),
      keywords: keywords,
      sources: Object.keys(bySource),
      articles: unique,
      stats: {
        total: unique.length,
        total_raw: allArticles.length,
        by_source: bySource,
        by_confidence: byConfidence,
      },
    };

    await writeJSON('collected.json', result);

    success('采集完成', `${unique.length} 条（原始${allArticles.length}条，去重${allArticles.length - unique.length}条）`);
    for (const [src, cnt] of Object.entries(bySource)) {
      console.log(`   ${src}: ${cnt} 条`);
    }
    success('可信度', `✅已核实 ${byConfidence.verified} 条 | ⚠️仅标题 ${byConfidence.title_only} 条`);
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
      info('浏览器已关闭');
    }
  }
}

collect().catch(e => {
  error('采集失败', e.message);
  process.exit(1);
});
