"""
智能助手 Agent
自然语言交互 + 智能推荐 + 自动运维
"""
import re
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from ..base import AgentBase, AgentResult, AgentContext


class IntentType(str, Enum):
    """意图类型"""
    FILE_OPERATION = "file_operation"      # 文件操作
    SEARCH = "search"                     # 搜索
    SYSTEM_QUERY = "system_query"          # 系统查询
    RECOMMEND = "recommend"              # 智能推荐
    AUTOMATION = "automation"             # 自动化任务
    HELP = "help"                        # 帮助
    UNKNOWN = "unknown"                  # 未知


@dataclass
class Intent:
    """用户意图"""
    type: IntentType
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    original_text: str = ""


class SmartAssistantAgent(AgentBase):
    """
    智能助手 Agent
    
    功能:
    - 自然语言理解
    - 智能意图识别
    - 自动任务执行
    - 智能推荐
    - 上下文记忆
    """
    
    def __init__(self):
        super().__init__()
        self.definition = type('AgentDefinition', (), {
            'name': 'smart-assistant',
            'description': '智能助手 - 自然语言交互+智能推荐',
            'capabilities': {'FILE_READ', 'FILE_WRITE', 'SHELL_EXEC', 'TASK_CREATE'},
            'tools': ['file_list', 'file_read', 'file_write', 'shell', 'task_create'],
            'max_turns': 50,
            'model': 'claude-sonnet'
        })()
        
        # 上下文记忆
        self.conversation_history: List[Dict] = []
        self.max_history = 10
    
    async def run(self, task: str, context: AgentContext) -> AgentResult:
        """执行智能助手任务"""
        
        # 1. 意图识别
        intent = await self._recognize_intent(task)
        
        # 2. 记录对话历史
        self._add_to_history(task, intent)
        
        # 3. 执行对应操作
        if intent.type == IntentType.FILE_OPERATION:
            result = await self._handle_file_operation(task, intent, context)
        elif intent.type == IntentType.SEARCH:
            result = await self._handle_search(task, intent, context)
        elif intent.type == IntentType.SYSTEM_QUERY:
            result = await self._handle_system_query(task, intent, context)
        elif intent.type == IntentType.RECOMMEND:
            result = await self._handle_recommend(task, intent, context)
        elif intent.type == IntentType.AUTOMATION:
            result = await self._handle_automation(task, intent, context)
        elif intent.type == IntentType.HELP:
            result = await self._handle_help(task, intent, context)
        else:
            result = AgentResult(
                success=False,
                error="我无法理解您的请求，请尝试更清晰地描述"
            )
        
        return result
    
    async def _recognize_intent(self, text: str) -> Intent:
        """识别用户意图"""
        text_lower = text.lower()
        
        # 文件操作意图
        file_keywords = ['打开', '读取', '写入', '创建', '删除', '移动', '复制', 
                        'list', 'read', 'write', 'create', 'delete', 'open', 'show']
        if any(kw in text_lower for kw in file_keywords):
            return Intent(
                type=IntentType.FILE_OPERATION,
                confidence=0.8,
                original_text=text
            )
        
        # 搜索意图
        search_keywords = ['搜索', '查找', '找', 'search', 'find', 'grep']
        if any(kw in text_lower for kw in search_keywords):
            return Intent(
                type=IntentType.SEARCH,
                confidence=0.9,
                original_text=text
            )
        
        # 系统查询
        system_keywords = ['状态', '怎么样', '如何', '多少', '查看', 
                         'status', 'how', 'much', 'check']
        if any(kw in text_lower for kw in system_keywords):
            return Intent(
                type=IntentType.SYSTEM_QUERY,
                confidence=0.7,
                original_text=text
            )
        
        # 智能推荐
        recommend_keywords = ['推荐', '建议', '帮我', '最好', 
                            'recommend', 'suggest', 'best']
        if any(kw in text_lower for kw in recommend_keywords):
            return Intent(
                type=IntentType.RECOMMEND,
                confidence=0.8,
                original_text=text
            )
        
        # 自动化
        auto_keywords = ['自动', '定时', '批量', '批量处理',
                       'auto', 'schedule', 'batch']
        if any(kw in text_lower for kw in auto_keywords):
            return Intent(
                type=IntentType.AUTOMATION,
                confidence=0.8,
                original_text=text
            )
        
        # 帮助
        help_keywords = ['帮助', 'help', '命令', 'commands', '怎么用']
        if any(kw in text_lower for kw in help_keywords):
            return Intent(
                type=IntentType.HELP,
                confidence=0.9,
                original_text=text
            )
        
        return Intent(
            type=IntentType.UNKNOWN,
            confidence=0.0,
            original_text=text
        )
    
    async def _handle_file_operation(
        self, 
        task: str, 
        intent: Intent, 
        context: AgentContext
    ) -> AgentResult:
        """处理文件操作"""
        from ...tools import get_tool
        
        # 提取路径
        path = self._extract_path(task)
        
        tool_name = 'file_list'
        if '读' in task or 'read' in task.lower():
            tool_name = 'file_read'
        elif '写' in task or '创建' in task:
            tool_name = 'file_write'
        
        tool = get_tool(tool_name)
        result = await tool.execute({'path': path or '/'}, context)
        
        return AgentResult(
            success=result.success,
            data=result.data,
            steps=[{'action': 'file_operation', 'tool': tool_name}]
        )
    
    async def _handle_search(
        self, 
        task: str, 
        intent: Intent, 
        context: AgentContext
    ) -> AgentResult:
        """处理搜索"""
        # 提取搜索关键词
        keywords = self._extract_keywords(task)
        
        return AgentResult(
            success=True,
            data={
                'keywords': keywords,
                'message': f'搜索关键词: {keywords}',
                'placeholder': '搜索功能需要文件索引支持'
            }
        )
    
    async def _handle_system_query(
        self, 
        task: str, 
        intent: Intent, 
        context: AgentContext
    ) -> AgentResult:
        """处理系统查询"""
        from ...agents.multi_agent.coordinator import get_coordinator
        from ...tools import list_tools
        
        # 获取系统状态
        coord = get_coordinator()
        stats = coord.get_stats()
        tools = list_tools()
        
        status = {
            'tools_count': len(tools),
            'workers': stats['workers'],
            'total_tasks': stats['total_tasks'],
            'completed_tasks': stats['completed'],
            'system_health': '正常' if stats['failed'] < 5 else '需关注'
        }
        
        return AgentResult(
            success=True,
            data=status,
            message='系统状态查询完成'
        )
    
    async def _handle_recommend(
        self, 
        task: str, 
        intent: Intent, 
        context: AgentContext
    ) -> AgentResult:
        """智能推荐"""
        recommendations = []
        
        task_lower = task.lower()
        
        # 根据上下文推荐
        if '文件' in task or 'file' in task_lower:
            recommendations.extend([
                '使用 file_list 查看目录结构',
                '使用 file_read 读取文件内容',
                '使用 file_write 创建新文件'
            ])
        
        if '存储' in task or 'storage' in task_lower or '空间' in task:
            recommendations.extend([
                '定期清理回收站释放空间',
                '创建快照保护重要数据',
                '使用压缩减少存储占用'
            ])
        
        if '备份' in task or 'backup' in task_lower:
            recommendations.extend([
                '建议开启自动快照',
                '定期导出重要配置',
                '使用ZFS快照进行增量备份'
            ])
        
        if not recommendations:
            recommendations = [
                '尝试说 \"列出文件\" 查看目录',
                '尝试说 \"查看系统状态\"',
                '尝试说 \"推荐备份方案\"'
            ]
        
        return AgentResult(
            success=True,
            data={'recommendations': recommendations},
            message='智能推荐完成'
        )
    
    async def _handle_automation(
        self, 
        task: str, 
        intent: Intent, 
        context: AgentContext
    ) -> AgentResult:
        """自动化任务"""
        # 提取自动化类型
        automation_type = 'general'
        
        if '清理' in task or 'clean' in task.lower():
            automation_type = 'clean'
        elif '备份' in task or 'backup' in task.lower():
            automation_type = 'backup'
        elif '监控' in task or 'monitor' in task.lower():
            automation_type = 'monitor'
        
        return AgentResult(
            success=True,
            data={
                'automation_type': automation_type,
                'message': f'自动化任务已创建: {automation_type}',
                'note': '调度功能开发中'
            }
        )
    
    async def _handle_help(
        self, 
        task: str, 
        intent: Intent, 
        context: AgentContext
    ) -> AgentResult:
        """帮助信息"""
        help_info = """
# 智能助手命令帮助

## 文件操作
- "列出 /path 目录"
- "读取 /path/to/file"
- "创建新文件"

## 系统查询
- "查看系统状态"
- "检查存储空间"
- "查看任务列表"

## 智能推荐
- "推荐备份方案"
- "给我一些建议"

## 自动化
- "自动清理"
- "定时备份"

## 帮助
- "帮助"
- "查看命令"
"""
        
        return AgentResult(
            success=True,
            data={'help': help_info}
        )
    
    def _extract_path(self, text: str) -> Optional[str]:
        """提取路径"""
        # 匹配 /path 格式
        match = re.search(r'(/[a-zA-Z0-9_/.-]+)', text)
        if match:
            return match.group(1)
        return None
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单提取
        words = re.findall(r'[\w]+', text)
        return [w for w in words if len(w) > 1]
    
    def _add_to_history(self, task: str, intent: Intent):
        """添加到历史"""
        self.conversation_history.append({
            'task': task,
            'intent': intent.type.value,
            'timestamp': time.time()
        })
        
        # 保持历史长度
        if len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)
    
    async def execute_step(self, step: Dict[str, Any], context) -> Dict[str, Any]:
        """执行步骤"""
        return {"success": True}


# 注册为智能助手
SmartAssistant = SmartAssistantAgent