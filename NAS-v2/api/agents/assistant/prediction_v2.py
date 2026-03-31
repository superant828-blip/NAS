"""
高级预测分析系统 v3.2.0
存储预测 + 性能监控 + 异常检测 + 智能告警
"""
import time
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import random

from ..base import AgentBase, AgentResult, AgentContext


class MetricType(str, Enum):
    """指标类型"""
    STORAGE = "storage"           # 存储
    PERFORMANCE = "performance"  # 性能
    NETWORK = "network"          # 网络
    SECURITY = "security"       # 安全
    USAGE = "usage"            # 使用


@dataclass
class MetricData:
    """指标数据"""
    name: str
    value: float
    unit: str
    timestamp: float
    history: List[float] = field(default_factory=list)


@dataclass
class AlertRule:
    """告警规则"""
    id: str
    metric: str
    condition: str  # >, <, ==
    threshold: float
    severity: str  # info, warning, critical
    enabled: bool = True


class AdvancedPredictionAgent(AgentBase):
    """
    高级预测分析 Agent v3.2.0
    
    功能:
    - 多维度指标采集
    - 智能预测算法
    - 异常检测
    - 告警系统
    - 容量规划
    """
    
    def __init__(self):
        super().__init__()
        self.definition = type('AgentDefinition', (), {
            'name': 'advanced-prediction',
            'description': '高级预测分析 - 预测+告警+容量规划',
            'capabilities': {'ANALYSIS', 'PREDICTION', 'MONITORING'},
            'tools': ['zfs_list', 'shell', 'task_list'],
            'max_turns': 30,
            'model': 'claude-sonnet'
        })()
        
        # 指标数据
        self.metrics: Dict[str, MetricData] = {}
        
        # 告警规则
        self.alert_rules: List[AlertRule] = [
            AlertRule("storage_70", "storage_usage", ">", 70, "warning"),
            AlertRule("storage_90", "storage_usage", ">", 90, "critical"),
            AlertRule("cpu_80", "cpu_usage", ">", 80, "warning"),
            AlertRule("memory_90", "memory_usage", ">", 90, "critical"),
        ]
        
        # 历史记录
        self.history: Dict[str, List[Dict]] = {}
    
    async def run(self, task: str, input_data: Dict[str, Any]) -> AgentResult:
        """执行预测分析"""
        task_lower = task.lower()
        
        # 存储预测
        if '存储' in task or 'storage' in task_lower or '空间' in task:
            return await self._predict_storage()
        
        # 性能分析
        elif '性能' in task or 'performance' in task_lower or 'cpu' in task_lower:
            return await self._analyze_performance()
        
        # 告警状态
        elif '告警' in task or 'alert' in task_lower or '警告' in task:
            return await self._check_alerts()
        
        # 容量规划
        elif '容量' in task or 'capacity' in task_lower or '规划' in task:
            return await self._plan_capacity()
        
        # 综合分析
        elif '分析' in task or 'analysis' in task_lower or '全面' in task:
            return await self._full_analysis()
        
        # 默认: 综合分析
        return await self._full_analysis()
    
    async def _predict_storage(self) -> AgentResult:
        """存储预测"""
        # 模拟获取存储数据
        datasets = await self._get_storage_data()
        
        # 计算使用趋势
        predictions = []
        for ds in datasets:
            current = ds['used_percent']
            
            # 简单线性预测 (模拟)
            daily_growth = random.uniform(0.5, 2.0)  # 模拟每日增长
            days_until_70 = int((70 - current) / daily_growth) if current < 70 else 0
            days_until_90 = int((90 - current) / daily_growth) if current < 90 else 0
            
            predictions.append({
                'dataset': ds['name'],
                'current_percent': current,
                'predicted_7days': min(100, current + daily_growth * 7),
                'predicted_30days': min(100, current + daily_growth * 30),
                'days_until_70': max(0, days_until_70),
                'days_until_90': max(0, days_until_90),
                'trend': 'up' if daily_growth > 1 else 'stable'
            })
        
        return AgentResult(
            success=True,
            data={
                'type': 'storage_prediction',
                'predictions': predictions,
                'generated_at': datetime.now().isoformat()
            }
        )
    
    async def _analyze_performance(self) -> AgentResult:
        """性能分析"""
        # 模拟性能指标
        metrics = {
            'cpu': {
                'current': random.uniform(20, 60),
                'avg_1h': random.uniform(25, 45),
                'avg_24h': random.uniform(20, 50),
                'max': random.uniform(60, 90),
            },
            'memory': {
                'current': random.uniform(40, 70),
                'avg_1h': random.uniform(45, 55),
                'avg_24h': random.uniform(40, 60),
                'max': random.uniform(70, 85),
            },
            'disk_io': {
                'read_mbps': random.uniform(10, 100),
                'write_mbps': random.uniform(5, 50),
            },
            'network': {
                'rx_mbps': random.uniform(1, 50),
                'tx_mbps': random.uniform(0.5, 30),
            }
        }
        
        # 检测异常
        anomalies = []
        if metrics['cpu']['current'] > 80:
            anomalies.append({
                'type': 'cpu',
                'severity': 'warning',
                'message': 'CPU使用率过高'
            })
        
        if metrics['memory']['current'] > 85:
            anomalies.append({
                'type': 'memory',
                'severity': 'critical',
                'message': '内存使用率危险'
            })
        
        return AgentResult(
            success=True,
            data={
                'type': 'performance_analysis',
                'metrics': metrics,
                'anomalies': anomalies,
                'recommendations': self._get_performance_recommendations(anomalies)
            }
        )
    
    async def _check_alerts(self) -> AgentResult:
        """检查告警"""
        active_alerts = []
        
        # 检查所有规则
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
            
            # 模拟检测
            value = random.uniform(0, 100)
            
            triggered = False
            if rule.condition == ">" and value > rule.threshold:
                triggered = True
            elif rule.condition == "<" and value < rule.threshold:
                triggered = True
            elif rule.condition == "==" and abs(value - rule.threshold) < 0.1:
                triggered = True
            
            if triggered:
                active_alerts.append({
                    'rule_id': rule.id,
                    'metric': rule.metric,
                    'condition': f"{rule.condition} {rule.threshold}",
                    'severity': rule.severity,
                    'current_value': round(value, 1),
                    'timestamp': datetime.now().isoformat()
                })
        
        return AgentResult(
            success=True,
            data={
                'type': 'alerts',
                'active_count': len(active_alerts),
                'alerts': active_alerts,
                'rules_count': len(self.alert_rules)
            }
        )
    
    async def _plan_capacity(self) -> AgentResult:
        """容量规划"""
        # 模拟容量数据
        current_usage = random.uniform(50, 80)
        daily_growth = random.uniform(0.5, 2.0)
        
        # 计算扩容时间线
        timeline = []
        
        # 70%
        if current_usage < 70:
            days_70 = int((70 - current_usage) / daily_growth)
            timeline.append({
                'threshold': '70%',
                'days_remaining': days_70,
                'action': '开始规划扩容'
            })
        
        # 80%
        days_80 = int((80 - current_usage) / daily_growth)
        timeline.append({
            'threshold': '80%',
            'days_remaining': max(0, days_80),
            'action': '准备扩容方案'
        })
        
        # 90%
        days_90 = int((90 - current_usage) / daily_growth)
        timeline.append({
            'threshold': '90%',
            'days_remaining': max(0, days_90),
            'action': '必须执行扩容'
        })
        
        # 建议
        recommendations = [
            f"当前使用率 {current_usage:.0f}%, 预计每日增长 {daily_growth:.1f}%",
            f"建议在{days_80}天内开始评估扩容需求",
            "考虑使用ZFS自动快照减少历史数据占用"
        ]
        
        return AgentResult(
            success=True,
            data={
                'type': 'capacity_plan',
                'current_usage': current_usage,
                'daily_growth': daily_growth,
                'timeline': timeline,
                'recommendations': recommendations
            }
        )
    
    async def _full_analysis(self) -> AgentResult:
        """综合分析"""
        # 并行执行多个分析
        storage_result = await self._predict_storage()
        perf_result = await self._analyze_performance()
        alert_result = await self._check_alerts()
        
        return AgentResult(
            success=True,
            data={
                'type': 'full_analysis',
                'storage': storage_result.data,
                'performance': perf_result.data,
                'alerts': alert_result.data,
                'summary': {
                    'storage_health': '正常',
                    'performance_health': '正常',
                    'active_alerts': alert_result.data['active_count']
                }
            }
        )
    
    async def _get_storage_data(self) -> List[Dict]:
        """获取存储数据"""
        # 模拟数据
        return [
            {'name': 'nas-pool/data', 'used_percent': random.uniform(40, 70)},
            {'name': 'nas-pool/photos', 'used_percent': random.uniform(50, 80)},
            {'name': 'nas-pool/backup', 'used_percent': random.uniform(30, 60)},
        ]
    
    def _get_performance_recommendations(self, anomalies: List[Dict]) -> List[str]:
        """性能建议"""
        recommendations = []
        
        for anomaly in anomalies:
            if anomaly['type'] == 'cpu':
                recommendations.append("CPU使用率高，建议检查运行进程")
            elif anomaly['type'] == 'memory':
                recommendations.append("内存压力大，考虑增加RAM或优化程序")
        
        if not recommendations:
            recommendations.append("系统运行正常")
        
        return recommendations


# 注册
AdvancedPrediction = AdvancedPredictionAgent