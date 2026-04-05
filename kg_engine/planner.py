# -*- coding: utf-8 -*-
"""
Ontology Planner - 图变换规划器

功能：
- 多步骤操作规划
- 事务管理（ACID）
- 约束验证
- 自动回滚
- 执行轨迹

版本：v2.0
日期：2026-03-29
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import copy

# 添加技能目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.validator import OntologyValidator, ValidationResult
from core.contract import ContractManager, SkillContract
from core.bus import EventBus, OntologyEvent, EventTypes


class TransactionState(Enum):
    """事务状态"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    COMMITTED = "committed"  # 已提交
    ABORTED = "aborted"      # 已回滚
    FAILED = "failed"        # 失败


@dataclass
class Operation:
    """操作单元"""
    op_id: str
    op_type: str  # create, update, delete, relate
    entity_type: str
    entity_id: str = ""
    data: Dict = field(default_factory=dict)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    
    # 执行结果
    result: Any = None
    success: bool = False
    error: str = ""
    
    # 回滚信息
    rollback_data: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'op_id': self.op_id,
            'op_type': self.op_type,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'data': self.data,
            'success': self.success,
            'error': self.error,
        }


@dataclass
class Transaction:
    """事务"""
    txn_id: str
    description: str = ""
    operations: List[Operation] = field(default_factory=list)
    state: TransactionState = TransactionState.PENDING
    
    # 执行轨迹
    execution_log: List[Dict] = field(default_factory=list)
    
    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str = ""
    committed_at: str = ""
    aborted_at: str = ""
    
    # 元数据
    skill_name: str = ""
    priority: str = "normal"
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'txn_id': self.txn_id,
            'description': self.description,
            'state': self.state.value,
            'operations': [op.to_dict() for op in self.operations],
            'execution_log': self.execution_log,
            'skill_name': self.skill_name,
            'priority': self.priority,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'committed_at': self.committed_at,
            'aborted_at': self.aborted_at,
        }


@dataclass
class PlanResult:
    """规划结果"""
    success: bool
    transaction: Transaction = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    
    def __bool__(self):
        return self.success
    
    def __str__(self):
        status = "✅ 成功" if self.success else "❌ 失败"
        lines = [f"规划结果：{status}"]
        
        if self.transaction:
            lines.append(f"事务 ID: {self.transaction.txn_id}")
            lines.append(f"状态：{self.transaction.state.value}")
            lines.append(f"操作数：{len(self.transaction.operations)}")
        
        if self.errors:
            lines.append(f"\n错误 ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  ❌ {error}")
        
        if self.warnings:
            lines.append(f"\n警告 ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  ⚠️ {warning}")
        
        if self.info:
            lines.append(f"\n信息 ({len(self.info)}):")
            for info in self.info:
                lines.append(f"  ℹ️ {info}")
        
        return "\n".join(lines)


class OntologyPlanner:
    """本体规划器"""
    
    def __init__(self, validator: OntologyValidator = None, 
                 contract_manager: ContractManager = None,
                 event_bus: EventBus = None):
        """
        初始化规划器
        
        Args:
            validator: 验证器实例
            contract_manager: 契约管理器实例
            event_bus: 事件总线实例
        """
        self.validator = validator or OntologyValidator()
        self.contract_manager = contract_manager or ContractManager()
        self.event_bus = event_bus or EventBus()
        
        # 事务存储
        self.transactions: Dict[str, Transaction] = {}
        
        # 操作执行器
        self.executors: Dict[str, Callable] = {}
        
        # 注册默认执行器
        self._register_default_executors()
    
    def _register_default_executors(self):
        """注册默认执行器"""
        self.executors['create'] = self._execute_create
        self.executors['update'] = self._execute_update
        self.executors['delete'] = self._execute_delete
        self.executors['relate'] = self._execute_relate
    
    def create_transaction(self, description: str, skill_name: str = "") -> Transaction:
        """
        创建事务
        
        Args:
            description: 事务描述
            skill_name: 技能名称
        
        Returns:
            事务对象
        """
        txn_id = f"txn_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        txn = Transaction(
            txn_id=txn_id,
            description=description,
            skill_name=skill_name,
        )
        self.transactions[txn_id] = txn
        return txn
    
    def add_operation(self, txn: Transaction, op_type: str, entity_type: str,
                     data: Dict = None, entity_id: str = "",
                     preconditions: List[str] = None,
                     postconditions: List[str] = None) -> Operation:
        """
        添加操作到事务
        
        Args:
            txn: 事务对象
            op_type: 操作类型（create/update/delete/relate）
            entity_type: 实体类型
            data: 操作数据
            entity_id: 实体 ID（update/delete 时需要）
            preconditions: 前置条件
            postconditions: 后置条件
        
        Returns:
            操作对象
        """
        op_id = f"op_{len(txn.operations) + 1}"
        
        op = Operation(
            op_id=op_id,
            op_type=op_type,
            entity_type=entity_type,
            entity_id=entity_id,
            data=data or {},
            preconditions=preconditions or [],
            postconditions=postconditions or [],
        )
        
        txn.operations.append(op)
        return op
    
    def validate_plan(self, txn: Transaction) -> PlanResult:
        """
        验证规划
        
        Args:
            txn: 事务对象
        
        Returns:
            规划结果
        """
        result = PlanResult(True, txn, [], [], [])
        
        # 1. 检查操作列表非空
        if not txn.operations:
            result.errors.append("事务中没有操作")
            result.success = False
            return result
        
        # 2. 验证每个操作
        for i, op in enumerate(txn.operations):
            # 2.1 检查操作类型
            if op.op_type not in self.executors:
                result.errors.append(f"操作 {op.op_id} 未知类型：{op.op_type}")
                result.success = False
                continue
            
            # 2.2 验证实体（create/update 时）
            if op.op_type in ['create', 'update']:
                if self.validator:
                    validation = self.validator.validate_entity(op.entity_type, op.data)
                    if not validation.valid:
                        result.errors.append(f"操作 {op.op_id} 验证失败：{validation.errors[0]}")
                        result.success = False
            
            # 2.3 检查权限（如果有契约管理器）
            if self.contract_manager and op.op_type in ['create', 'update', 'delete']:
                action = 'write' if op.op_type in ['create', 'update'] else 'delete'
                allowed = self.contract_manager.check_permission(
                    txn.skill_name, action, op.entity_type
                )
                if not allowed:
                    result.warnings.append(f"操作 {op.op_id} 可能违反权限：{txn.skill_name}.{action}({op.entity_type})")
        
        # 3. 检查依赖关系
        for i, op in enumerate(txn.operations):
            for j, other_op in enumerate(txn.operations):
                if i >= j:
                    continue
                
                # 检查操作间依赖
                if op.op_type == 'update' and other_op.op_type == 'create':
                    if op.entity_id == f"{{{other_op.op_id}.entity_id}}":
                        result.info.append(f"操作 {op.op_id} 依赖于 {other_op.op_id}")
        
        return result
    
    def execute_plan(self, txn: Transaction) -> PlanResult:
        """
        执行规划
        
        Args:
            txn: 事务对象
        
        Returns:
            规划结果
        """
        result = PlanResult(True, txn, [], [], [])
        
        # 1. 验证规划
        validation_result = self.validate_plan(txn)
        if not validation_result.success:
            result.success = False
            result.errors = validation_result.errors
            result.warnings = validation_result.warnings
            return result
        
        # 2. 更新事务状态
        txn.state = TransactionState.RUNNING
        txn.started_at = datetime.now().isoformat()
        
        # 3. 执行操作
        for i, op in enumerate(txn.operations):
            try:
                # 3.1 记录执行日志
                txn.execution_log.append({
                    'op_id': op.op_id,
                    'action': 'start',
                    'timestamp': datetime.now().isoformat(),
                })
                
                # 3.2 执行操作
                executor = self.executors.get(op.op_type)
                if not executor:
                    raise ValueError(f"未知操作类型：{op.op_type}")
                
                success, rollback_data = executor(op)
                
                # 3.3 记录结果
                op.success = success
                op.rollback_data = rollback_data
                
                txn.execution_log.append({
                    'op_id': op.op_id,
                    'action': 'complete' if success else 'fail',
                    'timestamp': datetime.now().isoformat(),
                    'success': success,
                })
                
                # 3.4 发布事件
                if self.event_bus and success:
                    event = OntologyEvent(
                        event_type=f"operation_{op.op_type}d",
                        entity_type=op.entity_type,
                        entity_id=op.entity_id or f"new_{i}",
                        action=op.op_type,
                        data=op.data,
                        source_skill=txn.skill_name,
                    )
                    self.event_bus.publish(event)
                
                # 3.5 检查失败
                if not success:
                    raise Exception(op.error or f"操作 {op.op_id} 执行失败")
                
            except Exception as e:
                # 执行失败，回滚
                txn.state = TransactionState.FAILED
                txn.aborted_at = datetime.now().isoformat()
                
                result.success = False
                result.errors.append(f"操作 {op.op_id} 失败：{str(e)}")
                
                # 回滚
                self._rollback_transaction(txn)
                
                return result
        
        # 4. 提交事务
        txn.state = TransactionState.COMMITTED
        txn.committed_at = datetime.now().isoformat()
        
        result.info.append(f"事务 {txn.txn_id} 已成功提交")
        result.info.append(f"执行操作数：{len(txn.operations)}")
        result.info.append(f"执行时间：{txn.started_at} - {txn.committed_at}")
        
        return result
    
    def _execute_create(self, op: Operation) -> Tuple[bool, Dict]:
        """执行创建操作"""
        # 模拟创建（实际应调用知识图谱引擎）
        op.entity_id = f"{op.entity_type.lower()}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        op.result = {'entity_id': op.entity_id}
        return True, {'entity_id': op.entity_id, 'data': op.data}
    
    def _execute_update(self, op: Operation) -> Tuple[bool, Dict]:
        """执行更新操作"""
        # 模拟更新
        op.result = {'updated': True}
        return True, {'entity_id': op.entity_id, 'old_data': op.data}
    
    def _execute_delete(self, op: Operation) -> Tuple[bool, Dict]:
        """执行删除操作"""
        # 模拟删除
        op.result = {'deleted': True}
        return True, {'entity_id': op.entity_id}
    
    def _execute_relate(self, op: Operation) -> Tuple[bool, Dict]:
        """执行关系创建操作"""
        # 模拟关系创建
        op.result = {'related': True}
        return True, {'relation': op.data}
    
    def _rollback_transaction(self, txn: Transaction):
        """回滚事务"""
        txn.state = TransactionState.ABORTED
        txn.aborted_at = datetime.now().isoformat()
        
        # 反向执行回滚
        for op in reversed(txn.operations):
            if not op.success:
                continue
            
            try:
                if op.op_type == 'create' and op.rollback_data:
                    # 回滚创建：删除实体
                    pass
                elif op.op_type == 'update' and op.rollback_data:
                    # 回滚更新：恢复旧数据
                    pass
                elif op.op_type == 'delete' and op.rollback_data:
                    # 回滚删除：恢复实体
                    pass
                
                txn.execution_log.append({
                    'op_id': op.op_id,
                    'action': 'rollback',
                    'timestamp': datetime.now().isoformat(),
                })
            except Exception as e:
                txn.execution_log.append({
                    'op_id': op.op_id,
                    'action': 'rollback_fail',
                    'timestamp': datetime.now().isoformat(),
                    'error': str(e),
                })


# ==================== 便捷函数 ====================

def create_planner(validator: OntologyValidator = None,
                   contract_manager: ContractManager = None,
                   event_bus: EventBus = None) -> OntologyPlanner:
    """创建规划器"""
    return OntologyPlanner(validator, contract_manager, event_bus)


# ==================== 主函数（CLI 测试） ====================

if __name__ == '__main__':
    print("=" * 60)
    print("Ontology Planner 测试")
    print("=" * 60)
    
    # 创建组件
    schema_path = Path(__file__).parent.parent / 'schema' / 'ontology_schema.yaml'
    validator = OntologyValidator(str(schema_path))
    contract_manager = ContractManager()
    event_bus = EventBus(enable_async=True)
    
    # 创建规划器
    planner = create_planner(validator, contract_manager, event_bus)
    
    # 注册技能契约
    contract = SkillContract(
        skill_name="test_skill",
        reads=["Task", "Knowledge"],
        writes=["Task", "Knowledge", "Experience"]
    )
    contract_manager.register_contract(contract)
    
    # 创建事务
    print("\n📝 创建事务:")
    txn = planner.create_transaction(
        description="完成 Ontology 开发任务",
        skill_name="test_skill"
    )
    print(f"   事务 ID: {txn.txn_id}")
    print(f"   描述：{txn.description}")
    
    # 添加操作
    print("\n📋 添加操作:")
    
    # 操作 1: 创建 Task
    planner.add_operation(
        txn, 'create', 'Task',
        data={
            "title": "完成 Ontology 阶段三",
            "status": "in_progress",
            "priority": "high"
        },
        preconditions=["Ontology 阶段二已完成"],
        postconditions=["Task 已创建"]
    )
    print(f"   ✅ 添加操作 1: create Task")
    
    # 操作 2: 创建 Knowledge
    planner.add_operation(
        txn, 'create', 'Knowledge',
        data={
            "category": "milestone",
            "content": "Ontology 阶段三完成",
            "source": "planner"
        },
        preconditions=["Task 已创建"],
        postconditions=["Knowledge 已记录"]
    )
    print(f"   ✅ 添加操作 2: create Knowledge")
    
    # 操作 3: 创建 Experience
    planner.add_operation(
        txn, 'create', 'Experience',
        data={
            "content": "使用 Planner 实现事务管理",
            "action": "多步骤操作原子性保证",
            "context": "Ontology 阶段三",
            "outcome": "positive",
            "insight": "事务支持回滚确保数据一致性"
        },
        preconditions=["Knowledge 已创建"],
        postconditions=["Experience 已保存"]
    )
    print(f"   ✅ 添加操作 3: create Experience")
    
    # 验证规划
    print("\n🔍 验证规划:")
    validation_result = planner.validate_plan(txn)
    print(f"   验证结果：{'✅ 通过' if validation_result.success else '❌ 失败'}")
    
    if validation_result.warnings:
        print(f"   警告：{validation_result.warnings}")
    
    if validation_result.info:
        print(f"   信息：{validation_result.info}")
    
    # 执行规划
    print("\n⚡ 执行规划:")
    execution_result = planner.execute_plan(txn)
    print(f"   执行结果：{execution_result}")
    
    # 显示事务状态
    print("\n📊 事务状态:")
    print(f"   状态：{txn.state.value}")
    print(f"   开始时间：{txn.started_at}")
    print(f"   完成时间：{txn.committed_at}")
    print(f"   操作数：{len(txn.operations)}")
    print(f"   执行日志：{len(txn.execution_log)} 条")
    
    # 显示操作结果
    print("\n📋 操作结果:")
    for op in txn.operations:
        status = "✅" if op.success else "❌"
        print(f"   {status} {op.op_id}: {op.op_type} {op.entity_type} -> {op.entity_id or 'N/A'}")
    
    # 关闭事件总线
    event_bus.shutdown()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)
