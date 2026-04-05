# -*- coding: utf-8 -*-
"""
Ontology Event Bus - 本体事件总线

功能：
- 事件发布/订阅
- 事件过滤
- 异步处理
- 事件日志

版本：v2.0
日期：2026-03-29
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import threading
import queue

# 添加技能目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class OntologyEvent:
    """本体事件"""
    event_type: str  # 事件类型（如 entity_created, relation_deleted）
    entity_type: str  # 实体类型（如 Task, Knowledge）
    entity_id: str = ""  # 实体 ID
    action: str = ""  # 操作（create, update, delete）
    data: Dict = field(default_factory=dict)  # 事件数据
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source_skill: str = ""  # 源技能
    priority: str = "normal"  # 优先级（low, normal, high, urgent）
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'event_type': self.event_type,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'action': self.action,
            'data': self.data,
            'timestamp': self.timestamp,
            'source_skill': self.source_skill,
            'priority': self.priority,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'OntologyEvent':
        """从字典创建"""
        return cls(
            event_type=data.get('event_type', ''),
            entity_type=data.get('entity_type', ''),
            entity_id=data.get('entity_id', ''),
            action=data.get('action', ''),
            data=data.get('data', {}),
            timestamp=data.get('timestamp', datetime.now().isoformat()),
            source_skill=data.get('source_skill', ''),
            priority=data.get('priority', 'normal'),
        )
    
    def __str__(self):
        return f"OntologyEvent({self.event_type}, {self.entity_type}/{self.entity_id}, {self.action})"


@dataclass
class EventSubscription:
    """事件订阅"""
    subscriber_id: str  # 订阅者 ID
    callback: Callable[[OntologyEvent], None]  # 回调函数
    event_types: Set[str] = field(default_factory=set)  # 感兴趣的事件类型
    entity_types: Set[str] = field(default_factory=set)  # 感兴趣的实体类型
    active: bool = True  # 是否激活


class EventBus:
    """事件总线"""
    
    def __init__(self, enable_async: bool = True, log_events: bool = True):
        """
        初始化事件总线
        
        Args:
            enable_async: 是否启用异步处理
            log_events: 是否记录事件日志
        """
        self.subscriptions: Dict[str, List[EventSubscription]] = defaultdict(list)
        self.event_log: List[OntologyEvent] = []
        self.enable_async = enable_async
        self.log_events = log_events
        
        # 异步处理
        if self.enable_async:
            self.event_queue = queue.Queue()
            self.worker_thread = threading.Thread(target=self._process_events, daemon=True)
            self.worker_thread.start()
        
        # 事件计数器
        self.event_count = 0
    
    def subscribe(self, subscriber_id: str, callback: Callable, 
                  event_types: List[str] = None, entity_types: List[str] = None):
        """
        订阅事件
        
        Args:
            subscriber_id: 订阅者 ID
            callback: 回调函数
            event_types: 感兴趣的事件类型（可选，None=所有）
            entity_types: 感兴趣的实体类型（可选，None=所有）
        """
        subscription = EventSubscription(
            subscriber_id=subscriber_id,
            callback=callback,
            event_types=set(event_types) if event_types else set(),
            entity_types=set(entity_types) if entity_types else set(),
            active=True,
        )
        
        # 根据事件类型订阅
        if event_types:
            for event_type in event_types:
                self.subscriptions[event_type].append(subscription)
        else:
            # 订阅所有事件
            self.subscriptions['*'].append(subscription)
        
        print(f"✅ 订阅事件：{subscriber_id} -> {event_types or '所有事件'}")
    
    def unsubscribe(self, subscriber_id: str, event_type: str = None):
        """
        取消订阅
        
        Args:
            subscriber_id: 订阅者 ID
            event_type: 事件类型（可选，None=所有）
        """
        if event_type:
            self.subscriptions[event_type] = [
                s for s in self.subscriptions[event_type]
                if s.subscriber_id != subscriber_id
            ]
        else:
            # 取消所有订阅
            for event_type in self.subscriptions:
                self.subscriptions[event_type] = [
                    s for s in self.subscriptions[event_type]
                    if s.subscriber_id != subscriber_id
                ]
        
        print(f"✅ 取消订阅：{subscriber_id}")
    
    def publish(self, event: OntologyEvent):
        """
        发布事件
        
        Args:
            event: 事件对象
        """
        self.event_count += 1
        
        # 记录事件日志
        if self.log_events:
            self.event_log.append(event)
        
        # 异步处理
        if self.enable_async:
            self.event_queue.put(event)
        else:
            self._dispatch_event(event)
    
    def _dispatch_event(self, event: OntologyEvent):
        """分发事件给订阅者"""
        # 获取订阅者（通用 + 特定）
        subscribers = []
        subscribers.extend(self.subscriptions.get('*', []))
        subscribers.extend(self.subscriptions.get(event.event_type, []))
        
        # 过滤和分发
        for subscription in subscribers:
            if not subscription.active:
                continue
            
            # 过滤事件类型
            if subscription.event_types and event.event_type not in subscription.event_types:
                continue
            
            # 过滤实体类型
            if subscription.entity_types and event.entity_type not in subscription.entity_types:
                continue
            
            # 调用回调
            try:
                subscription.callback(event)
            except Exception as e:
                print(f"❌ 事件回调错误 {subscription.subscriber_id}: {e}")
    
    def _process_events(self):
        """异步处理事件（工作线程）"""
        while True:
            event = self.event_queue.get()
            if event is None:
                break
            
            self._dispatch_event(event)
            self.event_queue.task_done()
    
    def shutdown(self):
        """关闭事件总线"""
        if self.enable_async:
            self.event_queue.put(None)
            self.worker_thread.join(timeout=5.0)
    
    def get_event_log(self, limit: int = 100) -> List[OntologyEvent]:
        """获取事件日志"""
        return self.event_log[-limit:]
    
    def get_event_count(self) -> int:
        """获取事件总数"""
        return self.event_count
    
    def get_subscribers(self, event_type: str = None) -> List[str]:
        """获取订阅者列表"""
        subscribers = set()
        
        if event_type:
            for sub in self.subscriptions.get(event_type, []):
                subscribers.add(sub.subscriber_id)
        else:
            for subs in self.subscriptions.values():
                for sub in subs:
                    subscribers.add(sub.subscriber_id)
        
        return list(subscribers)


# ==================== 事件类型常量 ====================

class EventTypes:
    """事件类型常量"""
    # 实体事件
    ENTITY_CREATED = "entity_created"
    ENTITY_UPDATED = "entity_updated"
    ENTITY_DELETED = "entity_deleted"
    
    # 关系事件
    RELATION_CREATED = "relation_created"
    RELATION_UPDATED = "relation_updated"
    RELATION_DELETED = "relation_deleted"
    
    # 知识事件
    KNOWLEDGE_CREATED = "knowledge_created"
    EXPERIENCE_LEARNED = "experience_learned"
    DECISION_MADE = "decision_made"
    
    # 任务事件
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    
    # 技能事件
    SKILL_EXECUTED = "skill_executed"
    CONTRACT_VIOLATED = "contract_violated"
    
    # 系统事件
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"
    ERROR_OCCURRED = "error_occurred"


# ==================== 便捷函数 ====================

def create_event_bus(enable_async: bool = True) -> EventBus:
    """创建事件总线"""
    return EventBus(enable_async=enable_async)


# ==================== 主函数（CLI 测试） ====================

if __name__ == '__main__':
    print("=" * 60)
    print("Ontology Event Bus 测试")
    print("=" * 60)
    
    # 创建事件总线
    bus = EventBus(enable_async=True, log_events=True)
    
    # 定义回调
    def on_knowledge_created(event: OntologyEvent):
        print(f"   📝 收到知识创建事件：{event.entity_id}")
    
    def on_task_event(event: OntologyEvent):
        print(f"   ✅ 收到任务事件：{event.event_type} - {event.entity_id}")
    
    def on_all_events(event: OntologyEvent):
        print(f"   🔔 收到事件：{event}")
    
    # 订阅事件
    print("\n📋 订阅事件:")
    bus.subscribe("smart_reminder", on_knowledge_created, 
                  event_types=[EventTypes.KNOWLEDGE_CREATED])
    bus.subscribe("task_tracker", on_task_event,
                  event_types=[EventTypes.TASK_CREATED, EventTypes.TASK_COMPLETED])
    bus.subscribe("logger", on_all_events)
    
    # 获取订阅者
    print(f"\n订阅者列表：{bus.get_subscribers()}")
    print(f"KNOWLEDGE_CREATED 订阅者：{bus.get_subscribers(EventTypes.KNOWLEDGE_CREATED)}")
    
    # 发布事件
    print("\n📢 发布事件:")
    
    event1 = OntologyEvent(
        event_type=EventTypes.KNOWLEDGE_CREATED,
        entity_type="Knowledge",
        entity_id="k_001",
        action="create",
        data={"category": "experience"},
        source_skill="self_evolution",
    )
    print(f"   发布：{event1}")
    bus.publish(event1)
    
    # 等待异步处理
    import time
    time.sleep(0.1)
    
    event2 = OntologyEvent(
        event_type=EventTypes.TASK_CREATED,
        entity_type="Task",
        entity_id="t_001",
        action="create",
        data={"status": "open"},
        source_skill="smart_reminder",
    )
    print(f"   发布：{event2}")
    bus.publish(event2)
    
    # 等待异步处理
    time.sleep(0.1)
    
    event3 = OntologyEvent(
        event_type=EventTypes.TASK_COMPLETED,
        entity_type="Task",
        entity_id="t_001",
        action="update",
        data={"status": "done"},
        source_skill="smart_reminder",
    )
    print(f"   发布：{event3}")
    bus.publish(event3)
    
    # 等待异步处理
    time.sleep(0.1)
    
    # 获取事件日志
    print(f"\n📊 事件统计:")
    print(f"   总事件数：{bus.get_event_count()}")
    print(f"   日志记录：{len(bus.get_event_log())}")
    
    # 取消订阅
    print("\n📋 取消订阅:")
    bus.unsubscribe("logger")
    
    # 关闭事件总线
    bus.shutdown()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)
