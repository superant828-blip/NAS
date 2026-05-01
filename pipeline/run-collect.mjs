#!/usr/bin/env node
/**
 * pipeline/run-collect.mjs - 纯采集脚本（无LLM）
 * 
 * 只跑 Stage 1+2+2b，生成 collected.json
 * 用于 cron 定时任务快速采集，后续由 agent 分析推送
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

async function runScript(script) {
  try {
    await execAsync(`node ${path.join(__dirname, script)}`, { 
      cwd: __dirname,
      timeout: 120000,
    });
    return true;
  } catch (e) {
    console.error(`❌ ${script} 失败: ${e.message.slice(0, 200)}`);
    return false;
  }
}

async function main() {
  console.log('🔄 开始采集流程...');
  
  await runScript('stage1-topics.js');
  await runScript('stage2-collect.js');
  await runScript('stage2b-content.js');
  
  // 打印摘要
  const collectedFile = path.join(DATA_DIR, 'collected.json');
  if (fs.existsSync(collectedFile)) {
    const data = JSON.parse(fs.readFileSync(collectedFile, 'utf-8'));
    console.log(`\n✅ 采集完成: ${data.stats.total} 条`);
    console.log(`   关键词: ${(data.keywords || []).slice(0, 5).join(', ')}`);
    for (const [src, cnt] of Object.entries(data.stats.by_source || {})) {
      console.log(`   ${src}: ${cnt} 条`);
    }
  }
}

main().catch(e => {
  console.error(`💥 采集异常: ${e.message}`);
  process.exit(1);
});
