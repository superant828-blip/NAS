#!/usr/bin/env node
/**
 * pipeline/stage3-report.js - 分析报告生成
 * 
 * 读取 collected.json，生成结构化报告
 * 输出到 pipeline/data/report.json 和 pipeline/output/
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');
const OUTPUT_DIR = path.join(__dirname, 'output');

if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

function generateReport(collected) {
  const { articles, stats, date } = collected;
  const now = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });

  // 分离数据
  const stocks = articles.filter(a => a.stock);
  const news36kr = articles.filter(a => a.source === '36氪');
  const newsWscn = articles.filter(a => a.source === '华尔街见闻');
  const newsGov = articles.filter(a => a.source === '发改委');
  const newsNda = articles.filter(a => a.source === '国家数据局');

  // 构建报告
  let report = `# AI/科技资讯日报 | ${date}\n\n`;
  report += `**生成时间：${now}**\n`;
  report += `**数据来源：36氪 · 华尔街见闻 · 发改委 · 国家数据局 · 新浪财经API**\n\n`;

  // 数据概览
  report += `## 📊 数据概览\n\n`;
  report += `| 指标 | 数据 |\n|------|------|\n`;
  report += `| 采集时间 | ${now} |\n`;
  report += `| 资讯总量 | **${stats.total} 条**（去重后）|\n`;
  report += `| ✅ 已核实 | ${stats.by_confidence?.verified || 0} 条 |\n`;
  report += `| ⚠️ 仅标题 | ${stats.by_confidence?.title_only || 0} 条 |\n\n`;

  // 股市行情（100%核实）
  if (stocks.length > 0) {
    report += `## 📈 股市行情（新浪API实时核实）\n\n`;
    report += `| 名称 | 代码 | 现价 | 涨跌幅 | 成交额 | 状态 |\n|------|------|------|--------|--------|------|\n`;
    for (const s of stocks) {
      const st = s.stock;
      const status = st.isLimitUp ? '🔴涨停' : st.changePct >= 0 ? '🟢涨' : '🔴跌';
      report += `| ${st.name} | ${st.code} | ¥${st.current} | ${st.change > 0 ? '+' : ''}${st.changePct}% | ¥${st.turnoverYi}亿 | ${status} |\n`;
    }
    report += `\n`;
  }

  // 36氪资讯
  if (news36kr.length > 0) {
    report += `## 📰 36氪（${news36kr.length}条）\n\n`;
    for (let i = 0; i < Math.min(news36kr.length, 15); i++) {
      const a = news36kr[i];
      const meta = a.meta ? ` (${a.meta})` : '';
      report += `${i + 1}. **${a.title}**${meta}\n`;
    }
    report += `\n`;
  }

  // 华尔街见闻
  if (newsWscn.length > 0) {
    report += `## 💰 华尔街见闻（${newsWscn.length}条）\n\n`;
    for (let i = 0; i < newsWscn.length; i++) {
      const a = newsWscn[i];
      report += `${i + 1}. ${a.title}\n`;
    }
    report += `\n`;
  }

  // 政策
  if (newsGov.length > 0) {
    report += `## 🏛️ 发改委（${newsGov.length}条）\n\n`;
    for (let i = 0; i < newsGov.length; i++) {
      report += `${i + 1}. ${newsGov[i].title}\n`;
    }
    report += `\n`;
  }

  if (newsNda.length > 0) {
    report += `## 📊 国家数据局（${newsNda.length}条）\n\n`;
    for (let i = 0; i < newsNda.length; i++) {
      report += `${i + 1}. ${newsNda[i].title}\n`;
    }
    report += `\n`;
  }

  // 可信度声明
  report += `---\n`;
  report += `## ⚠️ 数据可信度说明\n\n`;
  report += `- ✅ **已核实**：新浪行情API直接调用，100%准确\n`;
  report += `- ⚠️ **仅标题**：36氪/华尔街见闻/政府站仅获取标题，正文未核实\n`;
  report += `- ❌ **未采集**：36氪/华尔街见闻为SPA页面，正文内容无法抓取\n`;

  report += `\n*报告由 OpenClaw 三阶段资讯流水线自动生成*\n`;

  return { report, stocks, news36kr, newsWscn };
}

// 独立运行
if (process.argv[1]?.includes('stage3')) {
  const collectedFile = path.join(DATA_DIR, 'collected.json');
  if (!fs.existsSync(collectedFile)) {
    console.log('❌ 没有采集数据，请先运行 Stage 2');
    process.exit(1);
  }

  const collected = JSON.parse(fs.readFileSync(collectedFile, 'utf-8'));
  const { report } = generateReport(collected);

  // 保存报告
  const date = collected.date || new Date().toISOString().slice(0, 10);
  const reportData = {
    generatedAt: new Date().toISOString(),
    date,
    report,
    stats: collected.stats,
  };

  fs.writeFileSync(path.join(DATA_DIR, 'report.json'), JSON.stringify(reportData, null, 2));
  
  // 同时输出到 output/
  const outputFile = path.join(OUTPUT_DIR, `report-${date}.md`);
  fs.writeFileSync(outputFile, report);

  console.log(report);
  console.log(`\n✅ 报告已保存: ${outputFile}`);
}

export { generateReport };
