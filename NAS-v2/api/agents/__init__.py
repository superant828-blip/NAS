"""
AI Agent 系统
基于 Claude Code AgentTool 设计
"""
from .base import AgentBase, AgentDefinition, AgentResult
from .file_agent import FileAgent
from .multi_agent import (
    AgentCoordinator,
    CoordinationMode,
    TestAgent,
    TestType,
    CodingAgent,
    TuningAgent
)

__all__ = [
    'AgentBase',
    'AgentDefinition', 
    'AgentResult',
    'FileAgent',
    'AgentCoordinator',
    'CoordinationMode',
    'TestAgent',
    'TestType',
    'CodingAgent',
    'TuningAgent'
]