#!/usr/bin/env node
/**
 * pipeline/stage2-collect.js v3 - 采集阶段（重构版）
 *
 * 改进：
 * - 提取通用采集函数，消除重复代码
 * - 添加重试机制
 * - 动态等待代替固定延时
 * - 新浪API：实时获取7只科技股/指数行情
 * - 去重：按标题前40字去重
 * - 置信度标注：每条数据标注可信度
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { getTechStocks } from './lib/sina-stock.js';
import { withRetry, deduplicateByTitle, stats, writeJSON, DATA_DIR } from './lib/common.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// 36氪搜索关键词（取前3个）
const MAX_36KR_KEYWORDS = 3;
const MAX_ARTICLES_PER_KEYWORD = 10;

/**
 * 通用站点采集函数
 * 提取页面所有 <a> 链接，过滤有效标题
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
    links.forEach(a => {
      const t = a.innerText?.trim();
      const href = a.href || '';
      if (t && t.length > 8 && !t.includes('javascript') && (!domain || href.includes(domain))) {
        results.push({ title: t, link: href });
      }
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
 * 36氪搜索采集
 * 使用专用选择器提取搜索结果卡片
 */
async function collect36kr(page, keyword) {
  const url = `https://www.36kr.com/search/articles/${encodeURIComponent(keyword)}`;
  console.log(`  🔍 36氪: "${keyword}"`);

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

    const items = articles.slice(0, MAX_ARTICLES_PER_KEYWORD).map(a => ({
      title: a.title,
      source: '36氪',
      keyword,
      meta: a.meta,
      link: a.link,
      confidence: 'title_only',
      date: new Date().toISOString(),
    }));

    console.log(`    ✅ ${items.length} 条`);
    return items;
  } catch (e) {
    console.log(`    ⚠️ ${e.message}`);
    return [];
  }
}

async function collect() {
  const topicsFile = path.join(DATA_DIR, 'topics.json');
  if (!fs.existsSync(topicsFile)) {
    console.log('❌ 没有选题数据，请先运行 Stage 1');
    process.exit(1);
  }
  const topics = JSON.parse(fs.readFileSync(topicsFile, 'utf-8'));
  const keywords = topics.keywords || [];
  console.log(`📡 开始采集: ${keywords.length} 个关键词`);

  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  const allArticles = [];

  // === 36氪搜索 ===
  for (const kw of keywords.slice(0, MAX_36KR_KEYWORDS)) {
    const items = await collect36kr(page, kw);
    allArticles.push(...items);
  }

  // === 通用站点采集（消除重复代码）===
  const sites = [
    { url: 'https://wallstreetcn.com/', name: '华尔街见闻', maxItems: 50, delay: 2000 },
    { url: 'https://www.ndrc.gov.cn/', name: '发改委', maxItems: 8, domain: 'ndrc' },
    { url: 'https://www.nda.gov.cn/', name: '国家数据局', maxItems: 8, domain: 'nda' },
  ];

  for (const site of sites) {
    console.log(`  🔍 ${site.name}`);
    try {
      const items = await collectSite(page, site);
      allArticles.push(...items);
      console.log(`    ✅ ${items.length} 条`);
    } catch (e) {
      console.log(`    ⚠️ ${e.message}`);
    }
  }

  await browser.close();

  // === 新浪行情API（100%可核实）===
  console.log(`  📈 新浪行情API`);
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
    console.log(`    ✅ ${stocks.length} 条行情`);
    for (const s of stocks) {
      const emoji = s.isLimitUp ? '🔴涨停' : s.changePct >= 0 ? '🟢' : '🔴';
      console.log(`      ${s.name}: ¥${s.current} ${s.change > 0 ? '+' : ''}${s.changePct}% ${emoji}`);
    }
  } catch (e) {
    console.log(`    ⚠️ ${e.message}`);
  }

  // 去重
  const unique = deduplicateByTitle(allArticles);

  // 统计
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

  writeJSON('collected.json', result);

  console.log(`\n✅ 采集完成: ${unique.length} 条（原始${allArticles.length}条，去重${allArticles.length - unique.length}条）`);
  for (const [src, cnt] of Object.entries(bySource)) {
    console.log(`   ${src}: ${cnt} 条`);
  }
  console.log(`\n📊 可信度: ✅已核实 ${byConfidence.verified} 条 | ⚠️仅标题 ${byConfidence.title_only} 条`);
}

collect().catch(e => { console.error(e); process.exit(1); });
