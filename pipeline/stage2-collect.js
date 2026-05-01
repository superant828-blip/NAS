#!/usr/bin/env node
/**
 * pipeline/stage2-collect.js v6 - 采集阶段
 *
 * 改进：
 * - 用Stage1选题URL直接抓正文（36氪搜索是纯SPA无法渲染）
 * - 点击标题进入正文页，新开标签页抓取正文
 * - 限制抓正文数量防超时
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
 * 提取正文内容
 */
async function extractBody(page) {
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
  return content && content.length > 100 ? content : null;
}

/**
 * 点击标题进入正文页，提取内容（新开标签页）
 */
async function fetchArticleBody(context, article) {
  if (!article.link || !article.link.startsWith('http')) {
    article.confidence = 'title_only';
    return article;
  }
  let newPage;
  try {
    newPage = await context.newPage();
    await newPage.goto(article.link, { waitUntil: 'domcontentloaded', timeout: CONFIG.pageTimeout });
    await newPage.waitForTimeout(2000);
    const content = await extractBody(newPage);
    if (content) {
      article.content = content;
      article.contentFetchedAt = new Date().toISOString();
      article.contentSource = article.link;
      article.confidence = 'verified';
    } else {
      article.confidence = 'title_only';
    }
  } catch (e) {
    article.confidence = 'title_only';
    article.contentError = e.message.slice(0, 200);
  } finally {
    if (newPage) await newPage.close().catch(() => {});
  }
  return article;
}

/**
 * 批量抓取正文（限制数量防超时）
 */
async function fetchBodies(context, items, maxBody = 5) {
  const targets = items.filter(a => a.link && a.link.startsWith('http')).slice(0, maxBody);
  for (const item of targets) {
    await fetchArticleBody(context, item);
  }
  return items;
}

/**
 * 通用站点采集
 */
async function collectSite(context, page, { url, name, maxItems, domain, wait = 'networkidle', timeout = 15000, delay = 1000 }) {
  await withRetry(() => page.goto(url, { waitUntil: wait, timeout }), name);
  await page.waitForTimeout(delay);

  const links = await page.evaluate((domain) => {
    const els = document.querySelectorAll('a');
    const results = [];
    const navWords = /^(首页|登录|注册|关于|帮助|政策|条款|更多|全部|分类|频道|导航|菜单|搜索|切换|返回|顶部|底部|侧边)/;
    const noisePattern = /^(\S{1,6})\s*(刚刚|\d{1,2}:\d{2}|\d{1,2}小时前|\d{4}-\d{2}-\d{2})\s*$/;
    els.forEach(a => {
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

  const items = links.slice(0, maxItems).map(a => ({
    title: a.title, source: name, keyword: '', meta: '',
    link: a.link, confidence: 'title_only', date: new Date().toISOString(),
  }));

  return await fetchBodies(context, items, 3);
}

/**
 * 主采集流程
 */
async function collect() {
  const topicsFile = path.join(DATA_DIR, 'topics.json');
  let topicsData;
  try {
    const raw = await fsp.readFile(topicsFile, 'utf-8');
    topicsData = JSON.parse(raw);
  } catch (err) {
    error('没有选题数据', `请先运行 Stage 1: ${err.message}`);
    process.exit(1);
  }

  const keywords = topicsData.keywords || [];
  info('开始采集', `${keywords.length} 个关键词`);

  let browser;
  try {
    browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
    const context = await browser.newContext();
    const page = await context.newPage();
    const allArticles = [];

    // === 36氪选题（直接用Stage1的URL抓正文）===
    const topics = topicsData.topics || [];
    const krItems = topics.slice(0, 15).map(t => ({
      title: t.title, source: '36氪', keyword: '', meta: '',
      link: (t.url && t.url.startsWith('http')) ? t.url : '',
      confidence: 'title_only', date: new Date().toISOString(),
    }));
    await fetchBodies(context, krItems, 5);
    allArticles.push(...krItems);
    const withBody = krItems.filter(i => i.content).length;
    success('36氪选题', `${krItems.length} 条（正文${withBody}篇）`);

    // === 通用站点采集 ===
    for (const site of CONFIG.sites) {
      info(`采集 ${site.name}`);
      try {
        const items = await collectSite(context, page, site);
        allArticles.push(...items);
        const withBody = items.filter(i => i.content).length;
        success(`${site.name}`, `${items.length} 条（正文${withBody}篇）`);
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
          source: '新浪财经API', keyword: '', meta: `${s.date} ${s.time}`,
          link: `https://finance.sina.com.cn/realstock/company/${s.code}/nc.shtml`,
          confidence: 'verified', date: new Date().toISOString(), stock: s,
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
      keywords, sources: Object.keys(bySource), articles: unique,
      stats: { total: unique.length, total_raw: allArticles.length, by_source: bySource, by_confidence: byConfidence },
    };

    await writeJSON('collected.json', result);

    success('采集完成', `${unique.length} 条（原始${allArticles.length}条，去重${allArticles.length - unique.length}条）`);
    for (const [src, cnt] of Object.entries(bySource)) console.log(`   ${src}: ${cnt} 条`);
    success('可信度', `✅已核实 ${byConfidence.verified} 条 | ⚠️仅标题 ${byConfidence.title_only} 条`);
  } finally {
    if (browser) { await browser.close().catch(() => {}); info('浏览器已关闭'); }
  }
}

collect().catch(e => { error('采集失败', e.message); process.exit(1); });
