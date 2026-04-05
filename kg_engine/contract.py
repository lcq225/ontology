# -*- coding: utf-8 -*-
"""
Skill Contract - 技能契约管理器

功能：
- 技能契约定义
- 契约注册和验证
- 权限检查
- 依赖管理

版本：v2.0
日期：2026-03-29
"""

import yaml
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

# 添加技能目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class SkillContract:
    """技能契约"""
    skill_name: str
    version: str = "1.0"
    description: str = ""
    
    # 读取的实体类型
    reads: List[str] = field(default_factory=list)
    
    # 写入的实体类型
    writes: List[str] = field(default_factory=list)
    
    # 前置条件
    preconditions: List[str] = field(default_factory=list)
    
    # 后置条件
    postconditions: List[str] = field(default_factory=list)
    
    # 依赖的技能
    depends_on: List[str] = field(default_factory=list)
    
    # 提供的服务
    provides: List[str] = field(default_factory=list)
    
    # 元数据
    author: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'skill_name': self.skill_name,
            'version': self.version,
            'description': self.description,
            'reads': self.reads,
            'writes': self.writes,
            'preconditions': self.preconditions,
            'postconditions': self.postconditions,
            'depends_on': self.depends_on,
            'provides': self.provides,
            'author': self.author,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SkillContract':
        """从字典创建"""
        return cls(
            skill_name=data.get('skill_name', ''),
            version=data.get('version', '1.0'),
            description=data.get('description', ''),
            reads=data.get('reads', []),
            writes=data.get('writes', []),
            preconditions=data.get('preconditions', []),
            postconditions=data.get('postconditions', []),
            depends_on=data.get('depends_on', []),
            provides=data.get('provides', []),
            author=data.get('author', ''),
            created_at=data.get('created_at', datetime.now().isoformat()),
            updated_at=data.get('updated_at', datetime.now().isoformat()),
        )
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'SkillContract':
        """从 YAML 文件加载"""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    def to_yaml(self, yaml_path: str):
        """保存到 YAML 文件"""
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, indent=2, allow_unicode=True)


@dataclass
class ContractValidationResult:
    """契约验证结果"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    
    def __bool__(self):
        return self.valid
    
    def __str__(self):
        status = "✅ 通过" if self.valid else "❌ 失败"
        lines = [f"契约验证：{status}"]
        
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


class ContractManager:
    """技能契约管理器"""
    
    def __init__(self, contracts_dir: str = None):
        """
        初始化契约管理器
        
        Args:
            contracts_dir: 契约文件目录（可选）
        """
        self.contracts_dir = Path(contracts_dir) if contracts_dir else None
        self.contracts: Dict[str, SkillContract] = {}
        self._load_contracts()
    
    def _load_contracts(self):
        """加载契约文件"""
        if not self.contracts_dir or not self.contracts_dir.exists():
            return
        
        for yaml_file in self.contracts_dir.glob("*.yaml"):
            try:
                contract = SkillContract.from_yaml(str(yaml_file))
                self.register_contract(contract)
                print(f"✅ 加载契约：{contract.skill_name}")
            except Exception as e:
                print(f"❌ 加载契约失败 {yaml_file}: {e}")
    
    def register_contract(self, contract: SkillContract):
        """
        注册契约
        
        Args:
            contract: 技能契约
        """
        self.contracts[contract.skill_name] = contract
    
    def get_contract(self, skill_name: str) -> Optional[SkillContract]:
        """
        获取契约
        
        Args:
            skill_name: 技能名称
        
        Returns:
            技能契约或 None
        """
        return self.contracts.get(skill_name)
    
    def validate_contract(self, contract: SkillContract) -> ContractValidationResult:
        """
        验证契约
        
        Args:
            contract: 技能契约
        
        Returns:
            验证结果
        """
        result = ContractValidationResult(True, [], [], [])
        
        # 1. 检查必填字段
        if not contract.skill_name:
            result.errors.append("缺少必填字段：skill_name")
            result.valid = False
        
        # 2. 检查 reads 和 writes 至少有一个
        if not contract.reads and not contract.writes:
            result.warnings.append("技能既不读取也不写入任何实体类型")
        
        # 3. 检查依赖的技能是否已注册
        for dep_skill in contract.depends_on:
            if dep_skill not in self.contracts:
                result.warnings.append(f"依赖的技能未注册：{dep_skill}")
        
        # 4. 检查循环依赖
        cycle = self._detect_cycle(contract.skill_name, set())
        if cycle:
            result.errors.append(f"检测到循环依赖：{' -> '.join(cycle)}")
            result.valid = False
        
        # 5. 检查权限冲突
        for skill_name, other_contract in self.contracts.items():
            if skill_name == contract.skill_name:
                continue
            
            # 检查写入冲突
            common_writes = set(contract.writes) & set(other_contract.writes)
            if common_writes:
                result.info.append(f"与技能 {skill_name} 共同写入：{common_writes}")
        
        return result
    
    def _detect_cycle(self, skill_name: str, visited: Set[str], path: List[str] = None) -> Optional[List[str]]:
        """检测循环依赖"""
        if path is None:
            path = []
        
        if skill_name in visited:
            # 找到循环
            cycle_start = path.index(skill_name)
            return path[cycle_start:] + [skill_name]
        
        visited.add(skill_name)
        path.append(skill_name)
        
        contract = self.contracts.get(skill_name)
        if contract:
            for dep in contract.depends_on:
                cycle = self._detect_cycle(dep, visited, path)
                if cycle:
                    return cycle
        
        path.pop()
        return None
    
    def check_permission(self, skill_name: str, action: str, entity_type: str) -> bool:
        """
        检查权限
        
        Args:
            skill_name: 技能名称
            action: 操作类型（read/write）
            entity_type: 实体类型
        
        Returns:
            是否允许
        """
        contract = self.contracts.get(skill_name)
        if not contract:
            return False
        
        if action == 'read':
            return entity_type in contract.reads or '*' in contract.reads
        
        elif action == 'write':
            return entity_type in contract.writes or '*' in contract.writes
        
        return False
    
    def get_dependencies(self, skill_name: str, recursive: bool = True) -> Set[str]:
        """
        获取依赖的技能
        
        Args:
            skill_name: 技能名称
            recursive: 是否递归获取
        
        Returns:
            依赖的技能集合
        """
        dependencies = set()
        contract = self.contracts.get(skill_name)
        
        if not contract:
            return dependencies
        
        for dep in contract.depends_on:
            dependencies.add(dep)
            
            if recursive:
                sub_deps = self.get_dependencies(dep, recursive=True)
                dependencies.update(sub_deps)
        
        return dependencies
    
    def get_dependents(self, skill_name: str) -> Set[str]:
        """
        获取依赖此技能的其他技能
        
        Args:
            skill_name: 技能名称
        
        Returns:
            依赖此技能的技能集合
        """
        dependents = set()
        
        for name, contract in self.contracts.items():
            if skill_name in contract.depends_on:
                dependents.add(name)
        
        return dependents
    
    def list_contracts(self) -> List[str]:
        """列出所有已注册的契约"""
        return list(self.contracts.keys())
    
    def export_contracts(self, output_path: str):
        """导出所有契约到 YAML 文件"""
        output = {
            'contracts': [c.to_dict() for c in self.contracts.values()],
            'exported_at': datetime.now().isoformat(),
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(output, f, indent=2, allow_unicode=True)
        
        print(f"✅ 导出契约到：{output_path}")


# ==================== 便捷函数 ====================

def create_contract_manager(contracts_dir: str = None) -> ContractManager:
    """创建契约管理器"""
    return ContractManager(contracts_dir)


def quick_validate_contract(contract_data: Dict) -> ContractValidationResult:
    """快速验证契约"""
    contract = SkillContract.from_dict(contract_data)
    manager = ContractManager()
    return manager.validate_contract(contract)


# ==================== 示例契约 ====================

def create_self_evolution_contract() -> SkillContract:
    """创建 self_evolution 技能契约示例"""
    return SkillContract(
        skill_name="self_evolution",
        version="1.0",
        description="自我进化引擎 - 周期性审视、经验学习、错误改善",
        reads=[
            "Task",
            "Project",
            "Knowledge",
            "Experience",
            "Decision",
            "Skill",
        ],
        writes=[
            "Knowledge",
            "Experience",
            "Decision",
            "Task",
            "Skill",
        ],
        preconditions=[
            "MemoryCoreClaw 已初始化",
            "记忆数据库可访问",
        ],
        postconditions=[
            "新知识已记录",
            "经验教训已保存",
            "技能效用已更新",
        ],
        depends_on=[
            "memorycoreclaw",
        ],
        provides=[
            "经验记录",
            "错误学习",
            "技能优化",
        ],
        author="老 K",
    )


def create_memorycoreclaw_contract() -> SkillContract:
    """创建 memorycoreclaw 技能契约示例"""
    return SkillContract(
        skill_name="memorycoreclaw",
        version="2.0",
        description="类人脑长期记忆系统 - 支持分层记忆、遗忘曲线、情境记忆",
        reads=[
            "Knowledge",
            "Experience",
            "Decision",
            "Person",
            "Event",
        ],
        writes=[
            "Knowledge",
            "Experience",
            "Decision",
            "Person",
            "Event",
            "Relation",
        ],
        preconditions=[
            "SQLite 数据库可访问",
            "Embedding 模型可用",
        ],
        postconditions=[
            "记忆已持久化",
            "向量索引已更新",
        ],
        depends_on=[],
        provides=[
            "记忆存储",
            "向量搜索",
            "关系管理",
        ],
        author="老 K",
    )


# ==================== 主函数（CLI 测试） ====================

if __name__ == '__main__':
    print("=" * 60)
    print("Skill Contract 测试")
    print("=" * 60)
    
    # 创建契约管理器
    manager = ContractManager()
    
    # 创建示例契约
    se_contract = create_self_evolution_contract()
    mem_contract = create_memorycoreclaw_contract()
    
    # 注册契约
    manager.register_contract(se_contract)
    manager.register_contract(mem_contract)
    
    print(f"\n📋 已注册契约：{manager.list_contracts()}")
    
    # 验证契约
    print("\n" + "=" * 60)
    print("验证 self_evolution 契约")
    print("=" * 60)
    result = manager.validate_contract(se_contract)
    print(result)
    
    # 检查权限
    print("\n" + "=" * 60)
    print("权限检查")
    print("=" * 60)
    
    tests = [
        ("self_evolution", "read", "Knowledge"),
        ("self_evolution", "write", "Knowledge"),
        ("self_evolution", "write", "Person"),
        ("memorycoreclaw", "write", "Knowledge"),
    ]
    
    for skill, action, entity in tests:
        allowed = manager.check_permission(skill, action, entity)
        status = "✅ 允许" if allowed else "❌ 拒绝"
        print(f"   {skill}.{action}({entity}): {status}")
    
    # 获取依赖
    print("\n" + "=" * 60)
    print("依赖关系")
    print("=" * 60)
    deps = manager.get_dependencies("self_evolution")
    print(f"self_evolution 依赖：{deps}")
    
    dependents = manager.get_dependents("memorycoreclaw")
    print(f"memorycoreclaw 被依赖：{dependents}")
    
    # 导出契约
    print("\n" + "=" * 60)
    print("导出契约")
    print("=" * 60)
    manager.export_contracts("contracts_export.yaml")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)
