# -*- coding: utf-8 -*-
"""
Ontology Event-Driven Skill Coordinator - 事件驱动技能协调器

功能：
- 技能生命周期管理
- 事件路由与分发
- 依赖解析与加载
- 技能热插拔
- 执行优先级调度

版本：v2.0
日期：2026-03-29
"""

import sys
import json
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
import queue

# 添加技能目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import EventBus, OntologyEvent, EventTypes, EventHandler
from core.contract import ContractManager, SkillContract


class SkillState(Enum):
    """技能状态"""
    UNLOADED = "unloaded"      # 未加载
    LOADING = "loading"        # 加载中
    READY = "ready"            # 就绪
    RUNNING = "running"        # 运行中
    ERROR = "error"            # 错误
    DISABLED = "disabled"      # 已禁用


@dataclass
class SkillInfo:
    """技能信息"""
    name: str
    version: str
    path: Path
    state: SkillState = SkillState.UNLOADED
    contract: Optional[SkillContract] = None
    instance: Any = None
    last_executed: Optional[datetime] = None
    execution_count: int = 0
    error_count: int = 0
    dependencies: List[str] = field(default_factory=list)
    subscribers: List[str] = field(default_factory=list)
    publishers: List[str] = field(default_factory=list)


class SkillCoordinator:
    """技能协调器"""
    
    def __init__(self, event_bus: EventBus, contract_manager: ContractManager,
                 skills_dir: Optional[Path] = None):
        """
        初始化技能协调器
        
        Args:
            event_bus: 事件总线实例
            contract_manager: 契约管理器实例
            skills_dir: 技能目录路径
        """
        self.event_bus = event_bus
        self.contract_manager = contract_manager
        self.skills_dir = skills_dir or Path(__file__).parent.parent.parent / 'knowledge-graph'
        
        # 技能注册表
        self.skills: Dict[str, SkillInfo] = {}
        
        # 依赖图
        self.dependency_graph: Dict[str, Set[str]] = {}
        
        # 事件处理器缓存
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # 线程锁
        self._lock = threading.RLock()
        
        # 执行队列
        self._execution_queue: queue.PriorityQueue = queue.PriorityQueue()
        
        # 后台线程
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
    
    def discover_skills(self) -> List[str]:
        """
        发现可用技能
        
        Returns:
            技能名称列表
        """
        discovered = []
        
        if not self.skills_dir.exists():
            print(f"⚠️  技能目录不存在：{self.skills_dir}")
            return discovered
        
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            # 跳过隐藏目录和特殊目录
            if skill_dir.name.startswith('_') or skill_dir.name.startswith('.'):
                continue
            
            # 检查是否有 SKILL.md 或 contracts 目录
            skill_md = skill_dir / 'SKILL.md'
            contracts_dir = skill_dir / 'contracts'
            
            if skill_md.exists() or contracts_dir.exists():
                discovered.append(skill_dir.name)
        
        return discovered
    
    def load_skill(self, skill_name: str) -> bool:
        """
        加载技能
        
        Args:
            skill_name: 技能名称
            
        Returns:
            是否加载成功
        """
        with self._lock:
            if skill_name in self.skills:
                print(f"ℹ️  技能已加载：{skill_name}")
                return True
            
            skill_path = self.skills_dir / skill_name
            
            if not skill_path.exists():
                print(f"❌ 技能目录不存在：{skill_path}")
                return False
            
            # 加载契约
            contract = self.contract_manager.load_contract(skill_name)
            
            if not contract:
                print(f"⚠️  技能 {skill_name} 没有契约文件，使用默认契约")
                contract = SkillContract(
                    skill_name=skill_name,
                    version="1.0",
                    description=f"技能 {skill_name}"
                )
            
            # 创建技能信息
            skill_info = SkillInfo(
                name=skill_name,
                version=contract.version,
                path=skill_path,
                state=SkillState.LOADING,
                contract=contract,
                dependencies=contract.depends_on if contract else []
            )
            
            # 检查依赖
            missing_deps = []
            for dep in skill_info.dependencies:
                if dep not in self.skills and dep != 'memorycoreclaw':
                    missing_deps.append(dep)
            
            if missing_deps:
                print(f"⚠️  技能 {skill_name} 缺少依赖：{missing_deps}")
                # 不阻止加载，记录警告
            
            # 注册技能
            self.skills[skill_name] = skill_info
            self.dependency_graph[skill_name] = set(skill_info.dependencies)
            
            # 订阅事件
            if contract and contract.subscribes_to:
                for event_type in contract.subscribes_to:
                    self._register_event_handler(skill_name, event_type)
            
            # 更新状态
            skill_info.state = SkillState.READY
            
            print(f"✅ 技能已加载：{skill_name} v{skill_info.version}")
            return True
    
    def _register_event_handler(self, skill_name: str, event_type: str):
        """注册事件处理器"""
        
        def handler(event: OntologyEvent):
            """通用事件处理器"""
            skill_info = self.skills.get(skill_name)
            if not skill_info or skill_info.state != SkillState.READY:
                return
            
            try:
                # 调用技能的 on_event 方法（如果存在）
                if skill_info.instance and hasattr(skill_info.instance, 'on_event'):
                    skill_info.instance.on_event(event)
                
                # 记录执行
                skill_info.last_executed = datetime.now()
                skill_info.execution_count += 1
                
            except Exception as e:
                print(f"❌ 技能 {skill_name} 事件处理失败：{e}")
                skill_info.error_count += 1
        
        # 订阅事件
        self.event_bus.subscribe(skill_name, handler, [event_type])
        
        # 记录订阅关系
        if skill_name in self.skills:
            self.skills[skill_name].subscribers.append(event_type)
    
    def unload_skill(self, skill_name: str) -> bool:
        """
        卸载技能
        
        Args:
            skill_name: 技能名称
            
        Returns:
            是否卸载成功
        """
        with self._lock:
            if skill_name not in self.skills:
                print(f"⚠️  技能未加载：{skill_name}")
                return False
            
            skill_info = self.skills[skill_name]
            
            # 检查是否有其他技能依赖它
            dependents = []
            for name, deps in self.dependency_graph.items():
                if skill_name in deps:
                    dependents.append(name)
            
            if dependents:
                print(f"⚠️  技能 {skill_name} 被依赖：{dependents}")
                # 不阻止卸载，记录警告
            
            # 取消订阅
            if skill_info.contract and skill_info.contract.subscribes_to:
                for event_type in skill_info.contract.subscribes_to:
                    self.event_bus.unsubscribe(skill_name, [event_type])
            
            # 更新状态
            skill_info.state = SkillState.UNLOADED
            
            # 从注册表移除
            del self.skills[skill_name]
            if skill_name in self.dependency_graph:
                del self.dependency_graph[skill_name]
            
            print(f"✅ 技能已卸载：{skill_name}")
            return True
    
    def enable_skill(self, skill_name: str) -> bool:
        """启用技能"""
        with self._lock:
            if skill_name not in self.skills:
                print(f"⚠️  技能未加载：{skill_name}")
                return False
            
            self.skills[skill_name].state = SkillState.READY
            print(f"✅ 技能已启用：{skill_name}")
            return True
    
    def disable_skill(self, skill_name: str) -> bool:
        """禁用技能"""
        with self._lock:
            if skill_name not in self.skills:
                print(f"⚠️  技能未加载：{skill_name}")
                return False
            
            self.skills[skill_name].state = SkillState.DISABLED
            print(f"✅ 技能已禁用：{skill_name}")
            return True
    
    def get_skill_info(self, skill_name: str) -> Optional[SkillInfo]:
        """获取技能信息"""
        return self.skills.get(skill_name)
    
    def list_skills(self, state_filter: Optional[SkillState] = None) -> List[SkillInfo]:
        """
        列出技能
        
        Args:
            state_filter: 状态过滤
            
        Returns:
            技能信息列表
        """
        if state_filter:
            return [s for s in self.skills.values() if s.state == state_filter]
        return list(self.skills.values())
    
    def get_dependency_order(self) -> List[str]:
        """
        获取技能加载顺序（拓扑排序）
        
        Returns:
            技能名称列表（按依赖顺序）
        """
        # Kahn 算法
        in_degree = {name: 0 for name in self.skills}
        
        for name, deps in self.dependency_graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] += 1
        
        queue_list = [name for name, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue_list:
            name = queue_list.pop(0)
            result.append(name)
            
            for other_name, deps in self.dependency_graph.items():
                if name in deps:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue_list.append(other_name)
        
        if len(result) != len(self.skills):
            print("⚠️  检测到循环依赖")
        
        return result
    
    def start(self):
        """启动协调器后台线程"""
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        print("✅ 技能协调器已启动")
    
    def stop(self):
        """停止协调器后台线程"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
        print("✅ 技能协调器已停止")
    
    def _worker_loop(self):
        """后台工作线程"""
        while self._running:
            try:
                # 处理执行队列
                priority, skill_name, task = self._execution_queue.get(timeout=1.0)
                self._execute_task(skill_name, task)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ 协调器工作线程错误：{e}")
    
    def _execute_task(self, skill_name: str, task: dict):
        """执行任务"""
        skill_info = self.skills.get(skill_name)
        if not skill_info or skill_info.state != SkillState.READY:
            return
        
        # 执行任务逻辑
        # ...


def test_coordinator():
    """测试技能协调器"""
    print("=" * 60)
    print("Ontology 技能协调器测试")
    print("=" * 60)
    
    # 创建组件
    event_bus = EventBus(enable_async=True)
    contract_manager = ContractManager()
    
    # 创建协调器
    skills_dir = Path(__file__).parent.parent.parent / 'knowledge-graph'
    coordinator = SkillCoordinator(event_bus, contract_manager, skills_dir)
    
    # 发现技能
    print("\n🔍 发现技能:")
    discovered = coordinator.discover_skills()
    for skill in discovered:
        print(f"   📦 {skill}")
    
    # 加载技能
    print("\n📥 加载技能:")
    for skill_name in discovered[:3]:  # 加载前 3 个
        coordinator.load_skill(skill_name)
    
    # 列出技能
    print("\n📋 技能列表:")
    for skill in coordinator.list_skills():
        print(f"   {skill.name} v{skill.version} - {skill.state.value}")
    
    # 获取依赖顺序
    print("\n🔗 依赖顺序:")
    order = coordinator.get_dependency_order()
    for i, name in enumerate(order):
        print(f"   {i+1}. {name}")
    
    # 测试事件
    print("\n📢 测试事件:")
    event_bus.publish(OntologyEvent(
        event_type=EventTypes.KNOWLEDGE_CREATED,
        entity_id="Knowledge/test_001",
        action="create"
    ))
    
    # 卸载技能
    print("\n📤 卸载技能:")
    if discovered:
        coordinator.unload_skill(discovered[0])
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)


if __name__ == '__main__':
    test_coordinator()
