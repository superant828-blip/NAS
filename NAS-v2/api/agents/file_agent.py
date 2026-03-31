"""
文件管理 Agent
"""
from typing import Dict, Any, List
from .base import AgentBase, AgentDefinition, AgentResult, AgentContext, AgentCapability, BUILT_IN_AGENTS


class FileAgent(AgentBase):
    """
    文件管理 AI Agent
    
    功能：
    - 理解自然语言文件操作请求
    - 自动规划工具调用步骤
    - 执行文件操作
    - 返回结构化结果
    """
    
    definition = BUILT_IN_AGENTS["file-manager"]
    
    async def run(self, task: str, context: AgentContext) -> AgentResult:
        """执行文件管理任务"""
        
        # 1. 任务规划
        steps = await self.plan(task)
        
        if not steps:
            return AgentResult(
                success=False,
                error="Could not understand the task. Try using commands like 'list files in /path' or 'read /path/to/file'"
            )
        
        # 2. 执行步骤
        results = []
        tools_used = []
        
        for step in steps:
            if context.current_turn >= context.max_turns:
                break
            
            # 执行步骤
            result = await self.execute_step(step, context)
            results.append({
                "step": step,
                "result": result
            })
            
            if result.get("success"):
                tools_used.append(step.get("tool"))
            else:
                # 步骤失败，停止执行
                return AgentResult(
                    success=False,
                    error=f"Step failed: {result.get('error')}",
                    steps=results,
                    tools_used=tools_used,
                    total_turns=context.current_turn
                )
            
            context.current_turn += 1
        
        # 3. 返回结果
        return AgentResult(
            success=True,
            data={
                "task": task,
                "results": results
            },
            steps=results,
            tools_used=tools_used,
            total_turns=context.current_turn
        )
    
    async def plan(self, task: str) -> List[Dict[str, Any]]:
        """任务规划 - 将自然语言转换为工具调用"""
        
        steps = []
        task_lower = task.lower()
        
        # === 文件列表 ===
        if any(kw in task_lower for kw in ["list", "ls", "show", "显示", "列出", "查看"]):
            # 提取路径
            path = self._extract_path(task) or "/"
            
            # 确定是显示文件还是其他
            if "folder" in task_lower or "directory" in task_lower or "目录" in task_lower:
                pass  # 继续
            
            steps.append({
                "tool": "file_list",
                "input": {
                    "path": path,
                    "show_hidden": "hidden" in task_lower
                }
            })
        
        # === 文件读取 ===
        elif any(kw in task_lower for kw in ["read", "cat", "查看内容", "读取"]):
            path = self._extract_path(task)
            
            if path:
                # 检查是否有行号限制
                limit = None
                if "first" in task_lower or "前" in task_lower:
                    import re
                    match = re.search(r'(\d+)', task)
                    if match:
                        limit = int(match.group(1))
                
                steps.append({
                    "tool": "file_read",
                    "input": {
                        "path": path,
                        "limit": limit or 100
                    }
                })
        
        # === 文件写入/创建 ===
        elif any(kw in task_lower for kw in ["write", "create", "新建", "创建", "写入"]):
            # 复杂提取，需要更智能的解析
            path = self._extract_path(task)
            
            if path:
                # 尝试提取内容（简化版本）
                content = " "  # 占位
                
                steps.append({
                    "tool": "file_write",
                    "input": {
                        "path": path,
                        "content": content
                    }
                })
        
        # === ZFS 操作 ===
        if "zfs" in task_lower or "pool" in task_lower or "存储池" in task_lower:
            if "snapshot" in task_lower or "快照" in task_lower:
                # 快照操作
                dataset = self._extract_dataset(task)
                if dataset:
                    steps.append({
                        "tool": "zfs_snapshot",
                        "input": {
                            "action": "list",
                            "dataset": dataset
                        }
                    })
            else:
                # 列出数据集
                steps.append({
                    "tool": "zfs_list",
                    "input": {}
                })
        
        return steps
    
    def _extract_path(self, text: str) -> str:
        """提取路径"""
        import re
        
        # 匹配 /path/to/file 格式
        match = re.search(r'(/[a-zA-Z0-9_\-./]+)', text)
        if match:
            return match.group(1)
        
        # 匹配引号内的路径
        match = re.search(r'["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_dataset(self, text: str) -> str:
        """提取 ZFS 数据集名"""
        import re
        
        # 匹配池名/数据集格式
        match = re.search(r'([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+)', text)
        if match:
            return match.group(1)
        
        return "nas-pool"