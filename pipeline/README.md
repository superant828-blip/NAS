# 三阶段资讯流水线 v2

## 架构

```
Stage 1: 脚本抓取36kr数据 → 提取关键词
    ↓
Stage 2: browser_navigate 访问各站搜索页采集
    ↓ (P0: 36氪搜索 → P1: 垂直站 → P2: 政府站)
Stage 3: 分析采集结果 → 生成报告 → 钉钉推送
```

## 数据源优先级（来自 Hermes 实测）

| 优先级 | 站点 | URL模式 | 状态 |
|:-----:|:-----|:--------|:----|
| P0 | **36氪搜索** | `https://www.36kr.com/search/articles/{关键词}` | ✅ 100% |
| P1 | 集微网 | `https://www.laoyaoba.com/` | ✅ 高价值 |
| P1 | 生物谷 | `https://www.bioon.com/` | ✅ 可用 |
| P2 | gov.cn/zhengce | `https://www.gov.cn/zhengce/` | ✅ 可用 |
| P2 | miit.gov.cn | `https://www.miit.gov.cn/` | ✅ 可用 |
| ❌ | 机器之心/雷锋网/动脉网等 | - | 不可用 |

## Cron 定时任务

| 时间 | 任务 |
|------|------|
| 08:00 | 早报（过去24h） |
| 09:15 | 早报补充 |
| 12:30 | 午报（当上午） |
| 14:00 | 午报补充 |
| 17:30 | 晚报（全天综合） |
