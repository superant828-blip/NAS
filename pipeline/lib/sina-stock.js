#!/usr/bin/env node
/**
 * pipeline/lib/sina-stock.js - 新浪行情API封装
 * 
 * 实时获取A股行情数据
 * 
 * 用法:
 *   node lib/sina-stock.js                    # 默认7只科技股
 *   node lib/sina-stock.js sh688256,sh000001  # 指定代码
 */
import https from 'https';
import iconv from 'iconv-lite';

const SINA_API = 'https://hq.sinajs.cn/list={codes}';

function httpGet(url, headers = {}) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers, timeout: 10000 }, res => {
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => {
        const buf = Buffer.concat(chunks);
        const text = iconv.decode(buf, 'GBK');
        resolve({ status: res.statusCode, data: text });
      });
    }).on('error', reject);
  });
}

function parseSinaLine(code, raw) {
  if (!raw || raw === '""') return null;
  const fields = raw.split(',');
  if (fields.length < 32) return null;

  const yesterdayClose = parseFloat(fields[2]);
  const current = parseFloat(fields[3]);
  const change = current - yesterdayClose;
  const changePct = yesterdayClose > 0 ? (change / yesterdayClose * 100) : 0;

  return {
    code,
    name: fields[0],
    open: parseFloat(fields[1]),
    yesterdayClose,
    current,
    high: parseFloat(fields[4]),
    low: parseFloat(fields[5]),
    change: +change.toFixed(2),
    changePct: +changePct.toFixed(2),
    volume: parseInt(fields[8]),
    turnoverYi: +(parseFloat(fields[9]) / 1e8).toFixed(2),
    date: fields[30],
    time: fields[31],
    isLimitUp: changePct >= 19.95, // 科创板20%涨停
    source: '新浪财经API',
  };
}

// 默认监控列表
const DEFAULT_STOCKS = [
  'sh688256', // 寒武纪 - AI芯片
  'sh688041', // 海光信息 - 国产CPU/GPU
  'sh688111', // 金山办公 - 办公软件
  'sz300750', // 宁德时代 - 锂电池
  'sh000688', // 科创50指数
  'sh000001', // 上证指数
  'sz399006', // 创业板指
];

// 批量查询
export async function getStockQuotes(codes) {
  const url = SINA_API.replace('{codes}', codes);
  const { data } = await httpGet(url, { Referer: 'https://finance.sina.com.cn' });
  
  const results = [];
  for (const line of data.trim().split('\n')) {
    const match = line.match(/hq_str_(\w+)="(.*)"/);
    if (match) {
      const parsed = parseSinaLine(match[1], match[2]);
      if (parsed) results.push(parsed);
    }
  }
  return results;
}

// 获取默认监控列表
export async function getTechStocks() {
  return getStockQuotes(DEFAULT_STOCKS.join(','));
}

// 格式化输出
export function formatStock(s) {
  const emoji = s.isLimitUp ? '🔴涨停' : s.changePct >= 0 ? '🟢' : '🔴';
  const sign = s.change >= 0 ? '+' : '';
  return `${s.name.padEnd(6, ' ')} (${s.code.padEnd(8, ' ')}) ¥${String(s.current).padEnd(10)} ${sign}${String(s.changePct).padStart(6)}%  成交¥${s.turnoverYi}亿 ${emoji}`;
}

// 独立运行
if (process.argv[1]?.includes('sina-stock')) {
  const codes = process.argv.slice(2).join(',');
  const target = codes || DEFAULT_STOCKS.join(',');
  
  getStockQuotes(target).then(results => {
    if (results.length === 0) {
      console.log('❌ 未获取到行情数据');
      return;
    }
    console.log(`📈 新浪行情API | ${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}\n`);
    for (const r of results) {
      console.log(formatStock(r));
    }
  }).catch(e => {
    console.error(`❌ 新浪API请求失败: ${e.message}`);
    process.exit(1);
  });
}
