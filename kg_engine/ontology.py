# -*- coding: utf-8 -*-
"""
Ontology 本体层 - 知识图谱的"大脑"

定义领域本体结构，支持类层次、属性继承、关系推理
"""
import json
import os
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum


class RelationType(Enum):
    """本体关系类型（参考 Schema.org + 自定义）"""
    # 层次关系
    INSTANCE_OF = "rdfs:instanceOf"      # 实例
    SUBCLASS_OF = "rdfs:subClassOf"      # 子类
    
    # 属性关系
    HAS_PROPERTY = "hasProperty"          # 有属性
    PROPERTY_OF = "propertyOf"             # 属于
    
    # 语义关系
    SAME_AS = "owl:sameAs"                 # 等价
    SIMILAR_TO = "similarTo"               # 相似
    RELATED_TO = "relatedTo"               # 相关
    
    # 因果关系
    CAUSES = "causes"                      # 导致
    DEPENDS_ON = "dependsOn"              # 依赖于
    
    # 时序关系
    BEFORE = "before"                      # 之前
    AFTER = "after"                        # 之后
    DURING = "during"                      # 期间
    
    # 组织关系
    PART_OF = "partOf"                     # 属于
    HAS_PART = "hasPart"                   # 包含
    
    # 因果/影响
    AFFECTS = "affects"                    # 影响
    ENABLES = "enables"                    # 使能


@dataclass
class OntologyClass:
    """本体类"""
    name: str
    label: str                              # 显示标签
    description: str = ""                   # 描述
    parent: Optional[str] = None            # 父类
    properties: Dict[str, Any] = field(default_factory=dict)  # 属性定义
    aliases: List[str] = field(default_factory=list)  # 别名
    
    def get_all_parents(self) -> List[str]:
        """获取所有父类（递归）"""
        parents = []
        if self.parent:
            parents.append(self.parent)
        return parents


@dataclass
class OntologyProperty:
    """本体属性"""
    name: str
    label: str
    domain: str                             # 所属类
    range: str                              # 值类型
    description: str = ""
    is_inverse: Optional[str] = None       # 反属性


class OntologyManager:
    """
    本体管理器 - 管理领域本体定义
    
    提供：
    - 类层次结构
    - 属性定义
    - 关系推理规则
    - 本体查询
    """
    
    # 默认本体路径
    DEFAULT_ONTOLOGY_PATH = os.path.join(
        os.path.dirname(__file__), 
        'ontology.json'
    )
    
    def __init__(self, ontology_path: Optional[str] = None):
        """
        初始化本体管理器
        
        Args:
            ontology_path: 本体定义文件路径
        """
        self.classes: Dict[str, OntologyClass] = {}
        self.properties: Dict[str, OntologyProperty] = {}
        self.instances: Dict[str, Dict[str, Any]] = {}
        
        # 加载默认本体或自定义本体
        if ontology_path and os.path.exists(ontology_path):
            self.load(ontology_path)
        else:
            self._init_default_ontology()
    
    def _init_default_ontology(self) -> None:
        """初始化默认本体（通用领域）"""
        
        # ========== 类定义 ==========
        
        # 人物类
        self.add_class(OntologyClass(
            name="Person",
            label="人物",
            description="人，包括 Agent 和真实用户"
        ))
        
        # 组织类
        self.add_class(OntologyClass(
            name="Organization",
            label="组织",
            description="组织、团队、公司",
            parent="Entity"
        ))
        
        # 项目类
        self.add_class(OntologyClass(
            name="Project",
            label="项目",
            description="具体项目或任务"
        ))
        
        # 技术类
        self.add_class(OntologyClass(
            name="Technology",
            label="技术",
            description="技术、技能、工具",
            parent="Entity"
        ))
        
        # 系统类
        self.add_class(OntologyClass(
            name="System",
            label="系统",
            description="软件系统、平台"
        ))
        
        # 知识类
        self.add_class(OntologyClass(
            name="Knowledge",
            label="知识",
            description="知识、经验、教训",
            parent="Entity"
        ))
        
        # 决策类
        self.add_class(OntologyClass(
            name="Decision",
            label="决策",
            description="重要决策记录"
        ))
        
        # 事件类
        self.add_class(OntologyClass(
            name="Event",
            label="事件",
            description="发生的事件"
        ))
        
        # 实体基类
        self.add_class(OntologyClass(
            name="Entity",
            label="实体",
            description="所有实体的基类"
        ))
        
        # ========== 属性定义 ==========
        
        self.add_property(OntologyProperty(
            name="uses",
            label="使用",
            domain="Person",
            range="Technology"
        ))
        
        self.add_property(OntologyProperty(
            name="worksAt",
            label="工作于",
            domain="Person",
            range="Organization"
        ))
        
        self.add_property(OntologyProperty(
            name="responsibleFor",
            label="负责",
            domain="Person",
            range="Project"
        ))
        
        self.add_property(OntologyProperty(
            name="dependsOn",
            label="依赖于",
            domain="Project",
            range="Technology"
        ))
        
        self.add_property(OntologyProperty(
            name="relatesTo",
            label="关联",
            domain="Entity",
            range="Entity"
        ))
        
        self.add_property(OntologyProperty(
            name="learnedFrom",
            label="学自",
            domain="Knowledge",
            range="Event"
        ))
        
        self.add_property(OntologyProperty(
            name="supersedes",
            label="取代",
            domain="Decision",
            range="Decision"
        ))
    
    def add_class(self, cls: OntologyClass) -> None:
        """添加本体类"""
        self.classes[cls.name] = cls
    
    def add_property(self, prop: OntologyProperty) -> None:
        """添加本体属性"""
        self.properties[prop.name] = prop
    
    def add_instance(self, instance_id: str, class_name: str, 
                    properties: Dict[str, Any]) -> None:
        """
        添加实例
        
        Args:
            instance_id: 实例ID
            class_name: 所属类
            properties: 属性字典
        """
        self.instances[instance_id] = {
            'class': class_name,
            'properties': properties
        }
    
    def get_class(self, name: str) -> Optional[OntologyClass]:
        """获取类"""
        return self.classes.get(name)
    
    def get_property(self, name: str) -> Optional[OntologyProperty]:
        """获取属性"""
        return self.properties.get(name)
    
    def get_parent_classes(self, class_name: str) -> List[str]:
        """获取类的所有父类（递归）"""
        parents = []
        cls = self.get_class(class_name)
        
        while cls and cls.parent:
            parents.append(cls.parent)
            cls = self.get_class(cls.parent)
        
        return parents
    
    def is_subclass_of(self, child: str, parent: str) -> bool:
        """检查是否是子类"""
        return parent in self.get_parent_classes(child)
    
    def get_class_instances(self, class_name: str) -> List[str]:
        """获取类的所有实例"""
        return [
            inst_id for inst_id, inst_data in self.instances.items()
            if inst_data['class'] == class_name
            or self.is_subclass_of(inst_data['class'], class_name)
        ]
    
    def infer_relations(self, entity: str, known_relations: List[Dict]) -> List[Dict]:
        """
        推理额外关系（基于本体规则）
        
        Args:
            entity: 实体名
            known_relations: 已有关系列表
            
        Returns:
            list: 推理出的关系
        """
        inferred = []
        
        # 规则1：如果 A 使用 B，B 是技术，则 A 掌握技术
        for rel in known_relations:
            if rel.get('type') == 'uses':
                inferred.append({
                    'from': entity,
                    'type': 'masters',
                    'to': rel['to'],
                    'inferred': True,
                    'rule': 'uses → masters'
                })
        
        # 规则2：如果 A 负责 B，B 是项目，则 A 参与项目
        for rel in known_relations:
            if rel.get('type') == 'responsibleFor':
                inferred.append({
                    'from': entity,
                    'type': 'participatesIn',
                    'to': rel['to'],
                    'inferred': True,
                    'rule': 'responsibleFor → participatesIn'
                })
        
        return inferred
    
    def normalize_relation_type(self, relation: str) -> str:
        """
        规范化关系类型（支持别名）
        
        Args:
            relation: 原始关系名
            
        Returns:
            str: 规范化后的关系名
        """
        # 别名映射
        aliases = {
            '使用': 'uses',
            '运用': 'uses',
            '掌握': 'uses',
            '工作于': 'worksAt',
            '属于': 'worksAt',
            '负责': 'responsibleFor',
            '管理': 'responsibleFor',
            '依赖于': 'dependsOn',
            '依赖': 'dependsOn',
            '关联': 'relatesTo',
            '相关': 'relatesTo',
            '取代': 'supersedes',
            '替换': 'supersedes',
            '导致': 'causes',
            '影响': 'affects',
            '包含': 'hasPart',
            '属于': 'partOf',
        }
        
        return aliases.get(relation, relation)
    
    def query_ontology(self, query: str) -> Dict[str, Any]:
        """
        本体查询
        
        Args:
            query: 查询语句
            
        Returns:
            dict: 查询结果
        """
        # 简单的本体查询解析
        # 格式：类名 + 属性 + 值
        # 例如："项目 依赖于 技术"
        
        parts = query.split()
        if len(parts) >= 2:
            result = {
                'classes': [c for c in self.classes.keys() 
                           if any(p in c.lower() for p in parts)],
                'properties': [p for p in self.properties.keys()
                               if any(p in p.lower() for p in parts)]
            }
            return result
        
        return {'classes': list(self.classes.keys())}
    
    def to_schema_dot(self) -> str:
        """
        导出为 Graphviz DOT 格式（本体类图）
        
        Returns:
            str: DOT 代码
        """
        lines = [
            'digraph Ontology {',
            '  rankdir=BT;',
            '  node [shape=box, style=filled];',
            ''
        ]
        
        # 添加类节点
        for name, cls in self.classes.items():
            color = {
                'Person': '#e1f5fe',
                'Organization': '#f3e5f5',
                'Project': '#e8f5e9',
                'Technology': '#fff3e0',
                'System': '#e0f7fa',
                'Knowledge': '#fce4ec',
                'Decision': '#f9fbe7',
                'Entity': '#eeeeee'
            }.get(name, '#ffffff')
            
            lines.append(f'  "{name}" [label="{cls.label}", fillcolor="{color}"];')
        
        # 添加继承关系
        for name, cls in self.classes.items():
            if cls.parent:
                lines.append(f'  "{cls.parent}" -> "{name}" [arrowhead=empty];')
        
        lines.append('}')
        return '\n'.join(lines)
    
    def load(self, path: str) -> None:
        """从文件加载本体"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 加载类
        for cls_data in data.get('classes', []):
            self.add_class(OntologyClass(**cls_data))
        
        # 加载属性
        for prop_data in data.get('properties', []):
            self.add_property(OntologyProperty(**prop_data))
    
    def save(self, path: str) -> None:
        """保存本体到文件"""
        data = {
            'classes': [
                {
                    'name': c.name,
                    'label': c.label,
                    'description': c.description,
                    'parent': c.parent,
                    'properties': c.properties,
                    'aliases': c.aliases
                }
                for c in self.classes.values()
            ],
            'properties': [
                {
                    'name': p.name,
                    'label': p.label,
                    'domain': p.domain,
                    'range': p.range,
                    'description': p.description,
                    'is_inverse': p.is_inverse
                }
                for p in self.properties.values()
            ]
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# 全局本体管理器实例
_ontology_manager: Optional[OntologyManager] = None


def get_ontology_manager() -> OntologyManager:
    """获取本体管理器单例"""
    global _ontology_manager
    if _ontology_manager is None:
        _ontology_manager = OntologyManager()
    return _ontology_manager


def create_ontology_manager(ontology_path: Optional[str] = None) -> OntologyManager:
    """
    创建本体管理器（工厂函数）
    
    Args:
        ontology_path: 自定义本体文件路径
        
    Returns:
        OntologyManager: 本体管理器
    """
    return OntologyManager(ontology_path)