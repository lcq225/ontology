# -*- coding: utf-8 -*-
"""
Ontology Commitment - 承诺管理器

功能：
- 技能间承诺定义
- 承诺生命周期管理
- 承诺验证
- 承诺履行跟踪

版本：v2.0
日期：2026-03-29
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# 添加技能目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class CommitmentState(Enum):
    """承诺状态"""
    PROPOSED = "proposed"      # 提议中
    ACCEPTED = "accepted"      # 已接受
    IN_PROGRESS = "in_progress"  # 执行中
    FULFILLED = "fulfilled"    # 已履行
    VIOLATED = "violated"      # 已违反
    CANCELLED = "cancelled"    # 已取消


class CommitmentType(Enum):
    """承诺类型"""
    ACTION = "action"          # 行动承诺
    RESOURCE = "resource"      # 资源承诺
    CONSTRAINT = "constraint"  # 约束承诺
    QUALITY = "quality"        # 质量承诺


@dataclass
class Commitment:
    """技能承诺"""
    commitment_id: str
    type: CommitmentType
    description: str
    
    # 参与方
    debtor: str  # 承诺方（谁承诺）
    creditor: str  # 受诺方（对谁承诺）
    
    # 内容
    action: str = ""  # 承诺的行动
    resource: str = ""  # 承诺的资源
    constraint: str = ""  # 承诺的约束
    quality: str = ""  # 承诺的质量
    
    # 时间
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    due_date: str = ""  # 截止日期
    fulfilled_at: str = ""  # 履行时间
    
    # 状态
    state: CommitmentState = CommitmentState.PROPOSED
    
    # 上下文
    context: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    
    # 履行证据
    fulfillment_evidence: List[str] = field(default_factory=list)
    
    # 违反原因
    violation_reason: str = ""
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'commitment_id': self.commitment_id,
            'type': self.type.value,
            'description': self.description,
            'debtor': self.debtor,
            'creditor': self.creditor,
            'action': self.action,
            'resource': self.resource,
            'constraint': self.constraint,
            'quality': self.quality,
            'created_at': self.created_at,
            'due_date': self.due_date,
            'fulfilled_at': self.fulfilled_at,
            'state': self.state.value,
            'context': self.context,
            'metadata': self.metadata,
            'fulfillment_evidence': self.fulfillment_evidence,
            'violation_reason': self.violation_reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Commitment':
        """从字典创建"""
        return cls(
            commitment_id=data.get('commitment_id', ''),
            type=CommitmentType(data.get('type', 'action')),
            description=data.get('description', ''),
            debtor=data.get('debtor', ''),
            creditor=data.get('creditor', ''),
            action=data.get('action', ''),
            resource=data.get('resource', ''),
            constraint=data.get('constraint', ''),
            quality=data.get('quality', ''),
            created_at=data.get('created_at', datetime.now().isoformat()),
            due_date=data.get('due_date', ''),
            fulfilled_at=data.get('fulfilled_at', ''),
            state=CommitmentState(data.get('state', 'proposed')),
            context=data.get('context', {}),
            metadata=data.get('metadata', {}),
            fulfillment_evidence=data.get('fulfillment_evidence', []),
            violation_reason=data.get('violation_reason', ''),
        )


@dataclass
class CommitmentResult:
    """承诺操作结果"""
    success: bool
    commitment: Commitment = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    
    def __bool__(self):
        return self.success
    
    def __str__(self):
        status = "✅ 成功" if self.success else "❌ 失败"
        lines = [f"承诺操作：{status}"]
        
        if self.commitment:
            lines.append(f"承诺 ID: {self.commitment.commitment_id}")
            lines.append(f"状态：{self.commitment.state.value}")
        
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


class CommitmentManager:
    """承诺管理器"""
    
    def __init__(self):
        """初始化承诺管理器"""
        self.commitments: Dict[str, Commitment] = {}
        self.commitment_index: Dict[str, List[str]] = {
            'by_debtor': {},
            'by_creditor': {},
            'by_state': {},
            'by_type': {},
        }
    
    def create_commitment(self, type: CommitmentType, description: str,
                         debtor: str, creditor: str,
                         action: str = "", resource: str = "",
                         constraint: str = "", quality: str = "",
                         due_date: str = "",
                         context: Dict = None) -> Commitment:
        """
        创建承诺
        
        Args:
            type: 承诺类型
            description: 承诺描述
            debtor: 承诺方
            creditor: 受诺方
            action: 承诺行动
            resource: 承诺资源
            constraint: 承诺约束
            quality: 承诺质量
            due_date: 截止日期
            context: 上下文
        
        Returns:
            承诺对象
        """
        commitment_id = f"cmt_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        commitment = Commitment(
            commitment_id=commitment_id,
            type=type,
            description=description,
            debtor=debtor,
            creditor=creditor,
            action=action,
            resource=resource,
            constraint=constraint,
            quality=quality,
            due_date=due_date,
            context=context or {},
        )
        
        self.commitments[commitment_id] = commitment
        self._index_commitment(commitment)
        
        print(f"✅ 创建承诺：{commitment_id}")
        print(f"   类型：{type.value}")
        print(f"   描述：{description}")
        print(f"   承诺方：{debtor} → 受诺方：{creditor}")
        
        return commitment
    
    def _index_commitment(self, commitment: Commitment):
        """索引承诺"""
        # 按承诺方索引
        if commitment.debtor not in self.commitment_index['by_debtor']:
            self.commitment_index['by_debtor'][commitment.debtor] = []
        self.commitment_index['by_debtor'][commitment.debtor].append(commitment.commitment_id)
        
        # 按受诺方索引
        if commitment.creditor not in self.commitment_index['by_creditor']:
            self.commitment_index['by_creditor'][commitment.creditor] = []
        self.commitment_index['by_creditor'][commitment.creditor].append(commitment.commitment_id)
        
        # 按状态索引
        state = commitment.state.value
        if state not in self.commitment_index['by_state']:
            self.commitment_index['by_state'][state] = []
        self.commitment_index['by_state'][state].append(commitment.commitment_id)
        
        # 按类型索引
        type_ = commitment.type.value
        if type_ not in self.commitment_index['by_type']:
            self.commitment_index['by_type'][type_] = []
        self.commitment_index['by_type'][type_].append(commitment.commitment_id)
    
    def accept_commitment(self, commitment_id: str) -> CommitmentResult:
        """接受承诺"""
        commitment = self.commitments.get(commitment_id)
        
        if not commitment:
            return CommitmentResult(False, errors=[f"承诺不存在：{commitment_id}"])
        
        if commitment.state != CommitmentState.PROPOSED:
            return CommitmentResult(
                False,
                errors=[f"承诺状态不是 PROPOSED: {commitment.state.value}"]
            )
        
        commitment.state = CommitmentState.ACCEPTED
        self._update_index(commitment, "ACCEPTED")
        
        return CommitmentResult(True, commitment, info=["承诺已接受"])
    
    def start_commitment(self, commitment_id: str) -> CommitmentResult:
        """开始执行承诺"""
        commitment = self.commitments.get(commitment_id)
        
        if not commitment:
            return CommitmentResult(False, errors=[f"承诺不存在：{commitment_id}"])
        
        if commitment.state != CommitmentState.ACCEPTED:
            return CommitmentResult(
                False,
                errors=[f"承诺状态不是 ACCEPTED: {commitment.state.value}"]
            )
        
        commitment.state = CommitmentState.IN_PROGRESS
        self._update_index(commitment, "IN_PROGRESS")
        
        return CommitmentResult(True, commitment, info=["承诺执行中"])
    
    def fulfill_commitment(self, commitment_id: str, evidence: List[str] = None) -> CommitmentResult:
        """履行承诺"""
        commitment = self.commitments.get(commitment_id)
        
        if not commitment:
            return CommitmentResult(False, errors=[f"承诺不存在：{commitment_id}"])
        
        if commitment.state != CommitmentState.IN_PROGRESS:
            return CommitmentResult(
                False,
                errors=[f"承诺状态不是 IN_PROGRESS: {commitment.state.value}"]
            )
        
        commitment.state = CommitmentState.FULFILLED
        commitment.fulfilled_at = datetime.now().isoformat()
        commitment.fulfillment_evidence = evidence or []
        self._update_index(commitment, "FULFILLED")
        
        return CommitmentResult(
            True, commitment,
            info=["承诺已履行", f"履行时间：{commitment.fulfilled_at}"]
        )
    
    def violate_commitment(self, commitment_id: str, reason: str) -> CommitmentResult:
        """标记承诺违反"""
        commitment = self.commitments.get(commitment_id)
        
        if not commitment:
            return CommitmentResult(False, errors=[f"承诺不存在：{commitment_id}"])
        
        if commitment.state not in [CommitmentState.ACCEPTED, CommitmentState.IN_PROGRESS]:
            return CommitmentResult(
                False,
                errors=[f"承诺状态不允许违反：{commitment.state.value}"]
            )
        
        commitment.state = CommitmentState.VIOLATED
        commitment.violation_reason = reason
        self._update_index(commitment, "VIOLATED")
        
        return CommitmentResult(
            False, commitment,
            errors=[f"承诺已违反：{reason}"]
        )
    
    def cancel_commitment(self, commitment_id: str) -> CommitmentResult:
        """取消承诺"""
        commitment = self.commitments.get(commitment_id)
        
        if not commitment:
            return CommitmentResult(False, errors=[f"承诺不存在：{commitment_id}"])
        
        commitment.state = CommitmentState.CANCELLED
        self._update_index(commitment, "CANCELLED")
        
        return CommitmentResult(True, commitment, info=["承诺已取消"])
    
    def _update_index(self, commitment: Commitment, new_state: str):
        """更新索引"""
        # 从旧状态索引中移除
        old_state = commitment.state.value
        if old_state in self.commitment_index['by_state']:
            if commitment.commitment_id in self.commitment_index['by_state'][old_state]:
                self.commitment_index['by_state'][old_state].remove(commitment.commitment_id)
        
        # 添加到新状态索引
        if new_state not in self.commitment_index['by_state']:
            self.commitment_index['by_state'][new_state] = []
        self.commitment_index['by_state'][new_state].append(commitment.commitment_id)
    
    def get_commitment(self, commitment_id: str) -> Optional[Commitment]:
        """获取承诺"""
        return self.commitments.get(commitment_id)
    
    def get_commitments_by_debtor(self, debtor: str, state: CommitmentState = None) -> List[Commitment]:
        """按承诺方获取承诺"""
        ids = self.commitment_index['by_debtor'].get(debtor, [])
        commitments = [self.commitments[id] for id in ids if id in self.commitments]
        
        if state:
            commitments = [c for c in commitments if c.state == state]
        
        return commitments
    
    def get_commitments_by_creditor(self, creditor: str, state: CommitmentState = None) -> List[Commitment]:
        """按受诺方获取承诺"""
        ids = self.commitment_index['by_creditor'].get(creditor, [])
        commitments = [self.commitments[id] for id in ids if id in self.commitments]
        
        if state:
            commitments = [c for c in commitments if c.state == state]
        
        return commitments
    
    def get_commitments_by_state(self, state: CommitmentState) -> List[Commitment]:
        """按状态获取承诺"""
        ids = self.commitment_index['by_state'].get(state.value, [])
        return [self.commitments[id] for id in ids if id in self.commitments]
    
    def validate_commitment(self, commitment: Commitment) -> CommitmentResult:
        """验证承诺"""
        result = CommitmentResult(True, commitment, [], [], [])
        
        # 1. 检查必填字段
        if not commitment.debtor:
            result.errors.append("缺少承诺方（debtor）")
            result.success = False
        
        if not commitment.creditor:
            result.errors.append("缺少受诺方（creditor）")
            result.success = False
        
        if not commitment.description:
            result.warnings.append("承诺描述为空")
        
        # 2. 检查截止日期
        if commitment.due_date:
            try:
                due = datetime.fromisoformat(commitment.due_date)
                if due < datetime.now():
                    result.warnings.append(f"承诺已过期：{commitment.due_date}")
            except ValueError:
                result.errors.append(f"截止日期格式错误：{commitment.due_date}")
                result.success = False
        
        # 3. 检查承诺内容
        has_content = any([
            commitment.action,
            commitment.resource,
            commitment.constraint,
            commitment.quality,
        ])
        
        if not has_content:
            result.warnings.append("承诺内容为空（缺少 action/resource/constraint/quality）")
        
        return result
    
    def get_commitment_stats(self) -> Dict:
        """获取承诺统计"""
        stats = {
            'total': len(self.commitments),
            'by_state': {},
            'by_type': {},
            'by_debtor': {},
        }
        
        # 按状态统计
        for state in CommitmentState:
            count = len(self.get_commitments_by_state(state))
            stats['by_state'][state.value] = count
        
        # 按类型统计
        for type_ in CommitmentType:
            ids = self.commitment_index['by_type'].get(type_.value, [])
            stats['by_type'][type_.value] = len(ids)
        
        # 按承诺方统计
        for debtor, ids in self.commitment_index['by_debtor'].items():
            stats['by_debtor'][debtor] = len(ids)
        
        return stats


# ==================== 便捷函数 ====================

def create_commitment_manager() -> CommitmentManager:
    """创建承诺管理器"""
    return CommitmentManager()


# ==================== 主函数（CLI 测试） ====================

if __name__ == '__main__':
    print("=" * 60)
    print("Ontology Commitment 测试")
    print("=" * 60)
    
    # 创建承诺管理器
    manager = create_commitment_manager()
    
    # 创建承诺
    print("\n📝 创建承诺:")
    
    cmt1 = manager.create_commitment(
        type=CommitmentType.ACTION,
        description="完成 Ontology 阶段四开发",
        debtor="self_evolution",
        creditor="User",
        action="实现跨技能通信系统",
        due_date="2026-04-05",
        context={"phase": "4", "priority": "high"}
    )
    
    cmt2 = manager.create_commitment(
        type=CommitmentType.QUALITY,
        description="保证知识图谱性能",
        debtor="knowledge-graph",
        creditor="self_evolution",
        quality="查询延迟 < 100ms",
        due_date="2026-04-05"
    )
    
    cmt3 = manager.create_commitment(
        type=CommitmentType.RESOURCE,
        description="提供记忆数据库访问",
        debtor="memorycoreclaw",
        creditor="self_evolution",
        resource="memory.db",
        constraint="只读访问"
    )
    
    # 验证承诺
    print("\n🔍 验证承诺:")
    for cmt in [cmt1, cmt2, cmt3]:
        result = manager.validate_commitment(cmt)
        status = "✅" if result.success else "❌"
        print(f"   {status} {cmt.commitment_id}: {result}")
    
    # 承诺生命周期
    print("\n🔄 承诺生命周期:")
    
    # 接受
    result = manager.accept_commitment(cmt1.commitment_id)
    print(f"   接受：{result}")
    
    # 开始执行
    result = manager.start_commitment(cmt1.commitment_id)
    print(f"   开始：{result}")
    
    # 履行
    result = manager.fulfill_commitment(cmt1.commitment_id, [
        "core/commitment.py 已创建",
        "测试通过"
    ])
    print(f"   履行：{result}")
    
    # 查询承诺
    print("\n📊 查询承诺:")
    
    commitments = manager.get_commitments_by_debtor("self_evolution")
    print(f"   self_evolution 的承诺：{len(commitments)} 个")
    
    commitments = manager.get_commitments_by_creditor("User")
    print(f"   User 收到的承诺：{len(commitments)} 个")
    
    # 统计
    print("\n📈 承诺统计:")
    stats = manager.get_commitment_stats()
    print(f"   总承诺数：{stats['total']}")
    print(f"   按状态：{stats['by_state']}")
    print(f"   按类型：{stats['by_type']}")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)
