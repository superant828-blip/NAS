"""
初始化智能体和工具系统
在 main.py 启动时调用
"""
import sys
from pathlib import Path

# 添加项目路径
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def init_agent_system():
    """初始化智能体系统"""
    print("初始化智能体系统...")
    
    # 导入智能体模块
    try:
        # 导入工具系统
        from api.tools import initialize_tools
        initialize_tools()
        print("✓ 工具系统初始化完成")
    except Exception as e:
        print(f"⚠ 工具系统初始化失败: {e}")
    
    try:
        # 导入并初始化协调器
        from api.agents.multi_agent.coordinator import get_coordinator, WorkerAgent
        
        coordinator = get_coordinator()
        
        # 注册默认工作智能体
        workers = [
            WorkerAgent(
                id="test-worker-1",
                name="测试工作器",
                agent_type="test",
                capabilities={"test"},
                tools=["file_read", "shell"]
            ),
            WorkerAgent(
                id="coding-worker-1", 
                name="编程工作器",
                agent_type="coding",
                capabilities={"coding"},
                tools=["file_read", "file_write", "file_edit"]
            ),
            WorkerAgent(
                id="tuning-worker-1",
                name="调优工作器", 
                agent_type="tuning",
                capabilities={"tuning"},
                tools=["shell", "file_read"]
            )
        ]
        
        for worker in workers:
            coordinator.register_worker(worker)
        
        print(f"✓ 已注册 {len(workers)} 个工作智能体")
        
    except Exception as e:
        print(f"⚠ 智能体协调器初始化失败: {e}")
    
    # 初始化事件系统
    try:
        from api.events import get_event_dispatcher, EventType
        
        dispatcher = get_event_dispatcher()
        
        # 注册简单的事件处理（非装饰器风格）
        # 避免异步装饰器问题
        print("✓ 事件系统初始化完成")
        
    except Exception as e:
        print(f"⚠ 事件系统初始化失败: {e}")
    
    print("智能体系统初始化完成 ✓")


def init_tools():
    """初始化工具系统"""
    print("初始化工具系统...")
    
    try:
        from api.tools import initialize_tools
        initialize_tools()
        print("✓ 工具系统初始化完成")
    except Exception as e:
        print(f"⚠ 工具系统初始化失败: {e}")


if __name__ == "__main__":
    init_agent_system()
    init_tools()