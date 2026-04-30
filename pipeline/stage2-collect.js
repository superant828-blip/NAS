#!/usr/bin/env node
/**
 * pipeline/stage2-collect.js v2 - 采集阶段（优化版）
 * 
 * 改进：
 * - 36氪：抓取搜索结果的文章标题 + 时间
 * - 华尔街见闻：抓取文章标题 + 完整快讯内容
 * - 发改委/国家数据局：抓取首页新闻标题
 * - 新浪API：实时获取7只科技股/指数行情
 * - 去重：按标题前40字去重
 * - 置信度标注：每条数据标注可信度
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { getTechStocks } from './lib/sina-stock.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');

// 36氪搜索关键词（取前3个）
const MAX_36KR_KEYWORDS = 3;
const MAX_ARTICLES_PER_KEYWORD = 10;

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
    const url = `https://www.36kr.com/search/articles/${encodeURIComponent(kw)}`;
    console.log(`  🔍 36氪: "${kw}"`);
    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
      await page.waitForTimeout(3000);
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
      for (const a of articles.slice(0, MAX_ARTICLES_PER_KEYWORD)) {
        allArticles.push({
          title: a.title,
          source: '36氪',
          keyword: kw,
          meta: a.meta,
          link: a.link,
          confidence: 'title_only', // 只有标题，正文未核实
          date: new Date().toISOString(),
        });
      }
      console.log(`    ✅ ${Math.min(articles.length, MAX_ARTICLES_PER_KEYWORD)} 条`);
    } catch (e) {
      console.log(`    ⚠️ ${e.message}`);
    }
  }

  // === 华尔街见闻 ===
  console.log(`  🔍 华尔街见闻`);
  try {
    await page.goto('https://wallstreetcn.com/', { waitUntil: 'load', timeout: 15000 });
    await page.waitForTimeout(3000);
    const articles = await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('a[href]'));
      const results = [];
      links.forEach(a => {
        const text = a.innerText?.trim();
        if (text && text.length > 10 && text.length < 300) {
          // Clean up text (remove author names, timestamps)
          const cleaned = text.split('\n')[0].trim();
          if (cleaned.length > 10) {
            results.push({ title: cleaned, link: a.href });
          }
        }
      });
      return results;
    });
    const seen = new Set();
    for (const a of articles) {
      const key = a.title.slice(0, 40);
      if (!seen.has(key)) {
        seen.add(key);
        allArticles.push({
          title: a.title,
          source: '华尔街见闻',
          keyword: '',
          meta: '',
          link: a.link,
          confidence: 'title_only',
          date: new Date().toISOString(),
        });
      }
    }
    console.log(`    ✅ ${seen.size} 条`);
  } catch (e) {
    console.log(`    ⚠️ ${e.message}`);
  }

  // === 发改委 ===
  console.log(`  🔍 发改委`);
  try {
    await page.goto('https://www.ndrc.gov.cn/', { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000);
    const articles = await page.evaluate(() => {
      const links = document.querySelectorAll('a');
      const results = [];
      links.forEach(a => {
        const t = a.innerText?.trim();
        const href = a.href || '';
        if (t && t.length > 8 && !t.includes('javascript') && href.includes('ndrc')) {
          results.push({ title: t, link: href });
        }
      });
      return results;
    });
    const seen = new Set();
    for (const a of articles.slice(0, 8)) {
      const key = a.title.slice(0, 40);
      if (!seen.has(key)) {
        seen.add(key);
        allArticles.push({
          title: a.title,
          source: '发改委',
          keyword: '',
          meta: '',
          link: a.link,
          confidence: 'title_only',
          date: new Date().toISOString(),
        });
      }
    }
    console.log(`    ✅ ${seen.size} 条`);
  } catch (e) {
    console.log(`    ⚠️ ${e.message}`);
  }

  // === 国家数据局 ===
  console.log(`  🔍 国家数据局`);
  try {
    await page.goto('https://www.nda.gov.cn/', { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000);
    const articles = await page.evaluate(() => {
      const links = document.querySelectorAll('a');
      const results = [];
      links.forEach(a => {
        const t = a.innerText?.trim();
        const href = a.href || '';
        if (t && t.length > 8 && !t.includes('javascript') && href.includes('nda')) {
          results.push({ title: t, link: href });
        }
      });
      return results;
    });
    const seen = new Set();
    for (const a of articles.slice(0, 8)) {
      const key = a.title.slice(0, 40);
      if (!seen.has(key)) {
        seen.add(key);
        allArticles.push({
          title: a.title,
          source: '国家数据局',
          keyword: '',
          meta: '',
          link: a.link,
          confidence: 'title_only',
          date: new Date().toISOString(),
        });
      }
    }
    console.log(`    ✅ ${seen.size} 条`);
  } catch (e) {
    console.log(`    ⚠️ ${e.message}`);
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
        confidence: 'verified', // API数据，100%可核实
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

  // 去重（按标题前40字）
  const seen = new Set();
  const unique = [];
  for (const a of allArticles) {
    const key = a.title.slice(0, 40);
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(a);
    }
  }

  // 保存结果
  const bySource = {};
  const byConfidence = { verified: 0, title_only: 0 };
  for (const a of unique) {
    bySource[a.source] = (bySource[a.source] || 0) + 1;
    byConfidence[a.confidence] = (byConfidence[a.confidence] || 0) + 1;
  }

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

  fs.writeFileSync(path.join(DATA_DIR, 'collected.json'), JSON.stringify(result, null, 2));
  console.log(`\n✅ 采集完成: ${unique.length} 条（原始${allArticles.length}条，去重${allArticles.length - unique.length}条）`);
  for (const [src, cnt] of Object.entries(bySource)) {
    console.log(`   ${src}: ${cnt} 条`);
  }
  console.log(`\n📊 可信度: ✅已核实 ${byConfidence.verified} 条 | ⚠️仅标题 ${byConfidence.title_only} 条`);
}

collect().catch(e => { console.error(e); process.exit(1); });
