/**
 * pipeline/config.js - 流水线配置
 */
export const CONFIG = {
  // 采集配置
  max36krKeywords: 3,
  maxArticlesPerKeyword: 10,
  maxContentArticles: 10,
  maxContentChars: 8000,
  maxDisplayArticles: 20,
  
  // 重试配置
  retryMaxRetries: 2,
  retryDelayMs: 2000,
  pageTimeout: 15000,
  
  // 站点配置
  sites: [
    { url: 'https://wallstreetcn.com/', name: '华尔街见闻', maxItems: 50, delay: 2000 },
    { url: 'https://www.ndrc.gov.cn/', name: '发改委', maxItems: 8, domain: 'ndrc' },
    { url: 'https://www.nda.gov.cn/', name: '国家数据局', maxItems: 8, domain: 'nda' },
  ],
  
  // 股票配置
  stocks: [
    'sh688256', // 寒武纪 - AI芯片
    'sh688041', // 海光信息 - 国产CPU/GPU
    'sh688111', // 金山办公 - 办公软件
    'sz300750', // 宁德时代 - 锂电池
    'sh000688', // 科创50指数
    'sh000001', // 上证指数
    'sz399006', // 创业板指
  ],
};
