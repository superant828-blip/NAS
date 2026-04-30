#!/usr/bin/env node
/**
 * pipeline/run.mjs - 流水线运行入口 v2
 * 
 * 用法:
 *   node pipeline/run.mjs              # 完整运行
 *   node pipeline/run.mjs 1            # 只跑Stage 1
 *   node pipeline/run.mjs 2            # 只跑Stage 2
 *   node pipeline/run.mjs 2b           # 只跑Stage 2b(正文抓取)
 *   node pipeline/run.mjs 2c           # Stage 2+2b(采集+正文)
 *   node pipeline/run.mjs 3            # 只跑Stage 3(报告)
 *   node pipeline/run.mjs reset        # 重置状态
 */
import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

const args = process.argv.slice(2);
const mode = args[0];

function runScript(script, cwd) {
  console.log(`\n🚀 运行: ${script}\n${'─'.repeat(50)}`);
  execSync(`node ${path.join(__dirname, script)}`, { stdio: 'inherit', cwd: cwd || __dirname });
}

function reset() {
  const files = ['state.json', 'topics.json', 'collected.json', 'report.json'];
  for (const f of files) {
    const p = path.join(DATA_DIR, f);
    if (fs.existsSync(p)) fs.unlinkSync(p);
  }
  console.log('✅ 流水线状态已重置');
}

if (mode === 'reset') {
  reset();
  process.exit(0);
}

const stage = mode ? String(mode) : 'all';

if (stage === 'all' || stage === '1') {
  runScript('stage1-topics.js');
}

// 2c 需要先跑 Stage 1
if (stage === '2c' && !fs.existsSync(path.join(DATA_DIR, 'topics.json'))) {
  console.log('\n⚠️ 没有选题数据，先跑 Stage 1...');
  runScript('stage1-topics.js');
}

if (stage === 'all' || stage === '2' || stage === '2c') {
  runScript('stage2-collect.js');
}

if (stage === 'all' || stage === '2b' || stage === '2c') {
  runScript('stage2b-content.js');
}

if (stage === 'all' || stage === '3') {
  runScript('stage3-report.js');
}

// 打印状态摘要
const collectedFile = path.join(DATA_DIR, 'collected.json');
if (fs.existsSync(collectedFile)) {
  const data = JSON.parse(fs.readFileSync(collectedFile, 'utf-8'));
  const withContent = (data.articles || []).filter(a => a.content).length;
  console.log(`\n📊 状态摘要:`);
  console.log(`   资讯总量: ${data.stats.total} 条`);
  console.log(`   已核实(API): ${data.stats.by_confidence?.verified || 0} 条`);
  console.log(`   仅标题: ${data.stats.by_confidence?.title_only || 0} 条`);
  console.log(`   有正文: ${withContent} 条`);
  for (const [src, cnt] of Object.entries(data.stats.by_source || {})) {
    console.log(`   ${src}: ${cnt} 条`);
  }
}
