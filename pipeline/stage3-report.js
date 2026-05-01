#!/usr/bin/env node
/**
 * pipeline/stage3-report.js v2 - 分析报告生成
 *
 * 读取 collected.json，生成结构化 Markdown 报告，
 * 输出到 pipeline/data/report.json 和 pipeline/output/report-{date}.md。
 *
 * 改进：
 * - 文件操作异步化（fs → fsp）
 * - LOG_LEVEL 环境变量控制日志输出
 * - 完整 JSDoc 注释
 * - 增强异常处理
 * - 独立的 report() 入口函数供外部调用
 *
 * @module stage3-report
 */

import fsp from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

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
const OUTPUT_DIR = path.join(__dirname, 'output');

/** 各来源在报告中最大显示条数 */
const MAX_DISPLAY = 20;

/**
 * 从采集数据生成报告内容（纯函数，无副作用）。
 *
 * @param {object} collected - 采集数据（collected.json 内容）
 * @param {Array} collected.articles - 文章列表
 * @param {object} collected.stats - 统计数据
 * @param {string} collected.date - 日期
 * @returns {{ report: string, stocks: Array, news36kr: Array, newsWscn: Array }}
 *   包含 Markdown 报告字符串及各分类数据
 */
function generateReport(collected) {
  const { articles, stats, date } = collected;
  const now = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });

  // 分离数据
  const stocks = articles.filter(a => a.stock);
  const news36kr = articles.filter(a => a.source === '36氪');
  const newsWscn = articles.filter(a => a.source === '华尔街见闻');
  const newsGov = articles.filter(a => a.source === '发改委');
  const newsNda = articles.filter(a => a.source === '国家数据局');

  // 构建报告（数组拼接）
  const lines = [];
  lines.push(`# AI/科技资讯日报 | ${date}`);
  lines.push('');
  lines.push(`**生成时间：${now}**`);
  lines.push('**数据来源：36氪 · 华尔街见闻 · 发改委 · 国家数据局 · 新浪财经API**');
  lines.push('');

  // 数据概览
  lines.push('## 📊 数据概览');
  lines.push('');
  lines.push('| 指标 | 数据 |');
  lines.push('|------|------|');
  lines.push(`| 采集时间 | ${now} |`);
  lines.push(`| 资讯总量 | **${stats.total} 条**（去重后）|`);
  lines.push(`| ✅ 已核实 | ${stats.by_confidence?.verified || 0} 条 |`);
  lines.push(`| ⚠️ 仅标题 | ${stats.by_confidence?.title_only || 0} 条 |`);
  lines.push('');

  // 股市行情（100%核实）
  if (stocks.length > 0) {
    lines.push('## 📈 股市行情（新浪API实时核实）');
    lines.push('');
    lines.push('| 名称 | 代码 | 现价 | 涨跌幅 | 成交额 | 状态 |');
    lines.push('|------|------|------|--------|--------|------|');
    for (const s of stocks) {
      const st = s.stock;
      const status = st.isLimitUp ? '🔴涨停' : st.changePct >= 0 ? '🟢涨' : '🔴跌';
      lines.push(`| ${st.name} | ${st.code} | ¥${st.current} | ${st.change > 0 ? '+' : ''}${st.changePct}% | ¥${st.turnoverYi}亿 | ${status} |`);
    }
    lines.push('');
  }

  // 36氪资讯
  if (news36kr.length > 0) {
    lines.push(`## 📰 36氪（${news36kr.length}条）`);
    lines.push('');
    for (let i = 0; i < Math.min(news36kr.length, MAX_DISPLAY); i++) {
      const a = news36kr[i];
      const meta = a.meta ? ` (${a.meta})` : '';
      lines.push(`${i + 1}. **${a.title}**${meta}`);
    }
    lines.push('');
  }

  // 华尔街见闻
  if (newsWscn.length > 0) {
    lines.push(`## 💰 华尔街见闻（${newsWscn.length}条）`);
    lines.push('');
    for (let i = 0; i < Math.min(newsWscn.length, MAX_DISPLAY); i++) {
      lines.push(`${i + 1}. ${newsWscn[i].title}`);
    }
    lines.push('');
  }

  // 政策
  if (newsGov.length > 0) {
    lines.push(`## 🏛️ 发改委（${newsGov.length}条）`);
    lines.push('');
    for (let i = 0; i < Math.min(newsGov.length, MAX_DISPLAY); i++) {
      lines.push(`${i + 1}. ${newsGov[i].title}`);
    }
    lines.push('');
  }

  if (newsNda.length > 0) {
    lines.push(`## 📊 国家数据局（${newsNda.length}条）`);
    lines.push('');
    for (let i = 0; i < Math.min(newsNda.length, MAX_DISPLAY); i++) {
      lines.push(`${i + 1}. ${newsNda[i].title}`);
    }
    lines.push('');
  }

  // 有正文的文章摘要
  const withContent = articles.filter(a => a.content);
  if (withContent.length > 0) {
    lines.push('## 📝 正文摘要');
    lines.push('');
    for (let i = 0; i < Math.min(withContent.length, 10); i++) {
      const a = withContent[i];
      const summary = a.content.slice(0, 200).replace(/\n+/g, ' ').trim();
      lines.push(`### ${i + 1}. ${a.title}`);
      lines.push(`> ${summary}...`);
      lines.push(`*来源: ${a.source}*`);
      lines.push('');
    }
  }

  // 可信度声明
  lines.push('---');
  lines.push('## ⚠️ 数据可信度说明');
  lines.push('');
  lines.push('- ✅ **已核实**：新浪行情API直接调用，100%准确');
  lines.push('- ⚠️ **仅标题**：36氪/华尔街见闻/政府站仅获取标题，正文未核实');
  lines.push('- ❌ **未采集**：36氪/华尔街见闻为SPA页面，正文内容无法抓取');
  lines.push('');
  lines.push('*报告由 OpenClaw 三阶段资讯流水线自动生成*');

  const report = lines.join('\n');
  return { report, stocks, news36kr, newsWscn };
}

/**
 * 独立运行入口：读取 collected.json → 生成报告 → 保存到文件。
 * @returns {Promise<void>}
 */
async function report() {
  const collectedFile = path.join(DATA_DIR, 'collected.json');

  // 异步读取采集数据
  let collected;
  try {
    const raw = await fsp.readFile(collectedFile, 'utf-8');
    collected = JSON.parse(raw);
  } catch (err) {
    log('error', `没有采集数据，请先运行 Stage 2: ${err.message}`);
    process.exit(1);
  }

  const { report: reportText } = generateReport(collected);

  // 确保 output 目录存在
  try {
    await fsp.mkdir(OUTPUT_DIR, { recursive: true });
  } catch (err) {
    log('error', `创建输出目录失败: ${err.message}`);
    throw err;
  }

  const date = collected.date || new Date().toISOString().slice(0, 10);
  const reportData = {
    generatedAt: new Date().toISOString(),
    date,
    report: reportText,
    stats: collected.stats,
  };

  // 保存 report.json
  try {
    await fsp.writeFile(
      path.join(DATA_DIR, 'report.json'),
      JSON.stringify(reportData, null, 2),
      'utf-8',
    );
    log('debug', 'report.json 已保存');
  } catch (err) {
    log('error', `保存 report.json 失败: ${err.message}`);
  }

  // 同时输出 Markdown 到 output/
  const outputFile = path.join(OUTPUT_DIR, `report-${date}.md`);
  try {
    await fsp.writeFile(outputFile, reportText, 'utf-8');
    log('debug', `Markdown 报告已保存: ${outputFile}`);
  } catch (err) {
    log('error', `保存 Markdown 报告失败: ${err.message}`);
  }

  console.log(reportText);
  log('success', `报告已保存: ${outputFile}`);
}

// 独立运行检测
if (process.argv[1]?.includes('stage3')) {
  report().catch(err => {
    log('error', `报告生成失败: ${err.message}`);
    process.exit(1);
  });
}

export { generateReport, report };
