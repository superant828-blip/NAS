"""
多智能体系统
基于 Claude Code AgentTool + Coordinator 架构设计

功能：
- 多Agent协调
- 测试Agent
- 编程Agent
- 性能调优Agent
"""
from .coordinator import AgentCoordinator, CoordinationMode
from .test_agent import TestAgent, TestType, TestResult
from .coding_agent import CodingAgent, CodeTask, CodeResult
from .tuning_agent import TuningAgent, TuningTarget, TuningResult

__all__ = [
    'AgentCoordinator',
    'CoordinationMode',
    'TestAgent',
    'TestType',
    'TestResult',
    'CodingAgent',
    'CodeTask',
    'CodeResult',
    'TuningAgent',
    'TuningTarget',
    'TuningResult'
]