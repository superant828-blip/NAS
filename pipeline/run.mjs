#!/usr/bin/env node
/**
 * pipeline/run.mjs - 流水线运行入口 v3
 * 
 * 改进：
 * - P3: 异步执行，单阶段失败不阻塞
 * - P3: 错误策略配置（continue/abort）
 * - 支持 stage 选择执行
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
import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const execAsync = promisify(exec);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

const args = process.argv.slice(2);
const mode = args[0];

// 错误策略：'continue' = 继续下一阶段，'abort' = 停止
const ERROR_STRATEGY = 'continue';

async function runScript(script) {
  const label = script.split('.')[0];
  console.log(`\n🚀 运行: ${script}\n${'─'.repeat(50)}`);
  
  try {
    await execAsync(`node ${path.join(__dirname, script)}`, { 
      cwd: __dirname,
      timeout: 120000, // 2分钟超时
    });
    console.log(`✅ ${script} 完成`);
    return { success: true, script };
  } catch (e) {
    const msg = e.stderr || e.message;
    console.error(`❌ ${script} 失败:\n${msg.slice(0, 500)}`);
    
    if (ERROR_STRATEGY === 'abort') {
      console.error(`🛑 错误策略: abort，终止流水线`);
      process.exit(1);
    }
    
    console.log(`⏭️ 错误策略: continue，继续下一阶段`);
    return { success: false, script, error: msg.slice(0, 200) };
  }
}

function reset() {
  const files = ['state.json', 'topics.json', 'collected.json', 'report.json', 'url-cache.json'];
  let count = 0;
  for (const f of files) {
    const p = path.join(DATA_DIR, f);
    if (fs.existsSync(p)) {
      fs.unlinkSync(p);
      count++;
    }
  }
  console.log(`✅ 流水线状态已重置 (${count} 个文件)`);
}

if (mode === 'reset') {
  reset();
  process.exit(0);
}

const stage = mode ? String(mode) : 'all';
const results = [];

async function main() {
  // Stage 1: 选题
  if (stage === 'all' || stage === '1') {
    results.push(await runScript('stage1-topics.js'));
  }

  // 2c 需要先跑 Stage 1
  if (stage === '2c' && !fs.existsSync(path.join(DATA_DIR, 'topics.json'))) {
    console.log('\n⚠️ 没有选题数据，先跑 Stage 1...');
    results.push(await runScript('stage1-topics.js'));
  }

  // Stage 2: 采集
  if (stage === 'all' || stage === '2' || stage === '2c') {
    results.push(await runScript('stage2-collect.js'));
  }

  // Stage 2b: 正文抓取
  if (stage === 'all' || stage === '2b' || stage === '2c') {
    results.push(await runScript('stage2b-content.js'));
  }

  // Stage 3: 报告
  if (stage === 'all' || stage === '3') {
    results.push(await runScript('stage3-report.js'));
  }

  // 打印汇总
  console.log(`\n${'═'.repeat(50)}`);
  console.log('📊 流水线执行汇总');
  console.log('═'.repeat(50));
  
  const failed = results.filter(r => !r.success);
  const passed = results.filter(r => r.success);
  
  for (const r of results) {
    const icon = r.success ? '✅' : '❌';
    console.log(`  ${icon} ${r.script}`);
  }
  
  console.log(`\n总计: ${passed.length} 成功, ${failed.length} 失败`);
  
  if (failed.length > 0) {
    console.log(`\n⚠️ 以下阶段失败:`);
    for (const f of failed) {
      console.log(`  ❌ ${f.script}: ${f.error || 'unknown error'}`);
    }
  }

  // 打印状态摘要
  const collectedFile = path.join(DATA_DIR, 'collected.json');
  if (fs.existsSync(collectedFile)) {
    const data = JSON.parse(fs.readFileSync(collectedFile, 'utf-8'));
    const withContent = (data.articles || []).filter(a => a.content).length;
    console.log(`\n📊 数据摘要:`);
    console.log(`   资讯总量: ${data.stats.total} 条`);
    console.log(`   已核实(API): ${data.stats.by_confidence?.verified || 0} 条`);
    console.log(`   仅标题: ${data.stats.by_confidence?.title_only || 0} 条`);
    console.log(`   有正文: ${withContent} 条`);
    for (const [src, cnt] of Object.entries(data.stats.by_source || {})) {
      console.log(`   ${src}: ${cnt} 条`);
    }
  }
}

main().catch(e => {
  console.error(`💥 流水线异常: ${e.message}`);
  process.exit(1);
});
